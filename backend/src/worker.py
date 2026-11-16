import os,time,json,logging
from pathlib import Path
import redis
from src.config.database import Session
from src.models.entities import Segment,Window
from src.services.analysis import cluster
from src.services.window_ops import run_window_build,QUEUE_WINDOWS
SEG_QUEUE='reader:segments'
ARTIFACT_DIR=Path(os.environ.get('ARTIFACT_DIR','/artifacts'))
def redis_client():return redis.Redis.from_url(os.environ['REDIS_URL'])
def _write_artifact(name,payload):
 try:
  ARTIFACT_DIR.mkdir(parents=True,exist_ok=True)
  (ARTIFACT_DIR/name).write_text(json.dumps(payload,ensure_ascii=False))
 except OSError:logging.exception('artifact write failed')
def recover(client):
 with Session() as recovery:
  for pending in recovery.query(Segment).filter(Segment.state.in_(['queued','running'])).all():
   pending.state='queued';client.rpush(SEG_QUEUE,pending.id)
  for w in recovery.query(Window).filter(Window.state.in_(['building','failed'])).all():
   w.state='building';client.rpush(QUEUE_WINDOWS,w.id)
  recovery.commit()
def handle_window(payload):
 with Session() as s:
  w=s.get(Window,payload)
  if not w or w.state in ('ready','published'):return
  try:
   run_window_build(s,w.id);_write_artifact('window-'+str(w.id)+'.json',w.result);s.commit()
  except Exception:
   s.rollback();w=s.get(Window,payload)
   if w:w.state='failed';w.error='窗口计算失败，请修订后重新计算';s.commit()
   logging.exception('window build failed')
def handle_segment(payload):
 with Session() as s:
  row=s.get(Segment,payload)
  if not row or row.state!='queued':return
  snapshot=row.result['snapshot'];row.state='running';s.commit()
  try:
   row.result={**cluster(snapshot,row.features,row.k),'snapshot':snapshot};row.state='done'
   _write_artifact(str(row.id)+'.json',row.result)
  except Exception as e:row.state='failed';row.error=str(e)
  s.commit()
def dispatch(queue,payload):
 if queue==QUEUE_WINDOWS:handle_window(payload)
 else:handle_segment(payload)
def main():
 client=redis_client();recover(client)
 while True:
  Path('/tmp/heartbeat').touch()
  try:
   item=client.blpop([QUEUE_WINDOWS,SEG_QUEUE],timeout=3)
   if not item:continue
   queue=item[0].decode() if isinstance(item[0],bytes) else item[0]
   dispatch(queue,int(item[1]))
  except Exception:logging.exception('worker');time.sleep(2)
if __name__=='__main__':main()
