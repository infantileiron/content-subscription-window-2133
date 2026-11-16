from src.models.entities import Reader,WeeklyRecord,Window,WindowProfile,Segment
from src.services.window_ops import create_window
from src.services.weeks import offset_week
ANCHOR='2026-W47';WEEKS=[offset_week(ANCHOR,n) for n in range(-3,1)]
def seed(session_factory):
 with session_factory() as s:
  for idx,code in enumerate(('SL-001','SL-002','SL-003','SL-004')):
   r=s.query(Reader).filter_by(code=code).first()
   if not r:
    r=Reader(code=code,weekly_reading=10,completion=.5,night_share=.4,note='');s.add(r);s.flush()
   for i,w in enumerate(WEEKS):
    if not s.query(WeeklyRecord).filter_by(reader_id=r.id,week=w,source='pipeline').first():
     s.add(WeeklyRecord(reader_id=r.id,week=w,reading_count=4+i+idx,
                        completion=round(.3+idx*.12,3),night_share=round(.2+idx*.15,3),
                        source='pipeline',note='',updated_at='2026-11-16T08:00:00+00:00'))
  w,_=create_window(s,ANCHOR);s.commit();return w.id
class FakeRedis:
 def __init__(self):self.pushed=[]
 def rpush(self,k,v):self.pushed.append((k,v))
 def blpop(self,keys,timeout=3):return None
class TestWorker:
 def test_handle_window_consumes_and_is_idempotent(self,session_factory):
  from src import worker
  wid=seed(session_factory)
  worker.handle_window(wid)
  with session_factory() as s:
   w=s.get(Window,wid);assert w.state=='ready'
   assert w.result['reconciliation']['qualified']==4;checksum=w.result['input_checksum']
  worker.handle_window(wid)
  with session_factory() as s:
   w=s.get(Window,wid)
   assert w.result['input_checksum']==checksum
   assert s.query(WindowProfile).filter_by(window_id=wid).count()==4
 def test_handle_window_marks_failed_then_recovers(self,session_factory,monkeypatch):
  from src import worker
  wid=seed(session_factory)
  def boom(*a,**k):raise RuntimeError('计算中断')
  monkeypatch.setattr(worker,'run_window_build',boom)
  worker.handle_window(wid)
  with session_factory() as s:
   assert s.get(Window,wid).state=='failed'
  monkeypatch.undo()
  worker.handle_window(wid)
  with session_factory() as s:
   assert s.get(Window,wid).state=='ready'
 def test_handle_segment_clusters_published_snapshot(self,session_factory):
  from src import worker
  from src.services.windows import snapshot_for_cluster
  wid=seed(session_factory);worker.handle_window(wid)
  with session_factory() as s:
   w=s.get(Window,wid);w.state='published';w.published_at='2026-11-23T00:00:00+00:00'
   seg=Segment(name='窗口分群',k=2,features=['weekly_reading','completion','night_share'],
               window_id=wid,state='queued',
               result={'snapshot':snapshot_for_cluster(w.result),'window_id':wid,'anchor_week':ANCHOR})
   s.add(seg);s.commit();sid=seg.id
  worker.handle_segment(sid)
  with session_factory() as s:
   seg=s.get(Segment,sid)
   assert seg.state=='done' and seg.result['n']==4 and len(seg.result['members'])==4
 def test_recovery_requeues_failed_window_and_queued_segment(self,session_factory,monkeypatch):
  from src import worker
  wid=seed(session_factory)
  with session_factory() as s:
   s.get(Window,wid).state='failed';s.commit()
   seg=Segment(name='中断分群',k=2,features=['weekly_reading','completion'],window_id=wid,
               state='running',result={'snapshot':[],'window_id':wid,'anchor_week':ANCHOR})
   s.add(seg);s.commit();sid=seg.id
  fake=FakeRedis();monkeypatch.setattr(worker,'redis_client',lambda:fake)
  worker.recover(fake)
  assert ('reader:windows',wid) in fake.pushed
  assert ('reader:segments',sid) in fake.pushed
  with session_factory() as s:
   assert s.get(Window,wid).state=='building'
   assert s.get(Segment,sid).state=='queued'
 def test_dispatch_routes_by_queue(self,session_factory,monkeypatch):
  from src import worker
  seen=[]
  monkeypatch.setattr(worker,'handle_window',lambda x:seen.append(('w',x)))
  monkeypatch.setattr(worker,'handle_segment',lambda x:seen.append(('s',x)))
  worker.dispatch(worker.QUEUE_WINDOWS,7);worker.dispatch(worker.SEG_QUEUE,9)
  assert seen==[('w',7),('s',9)]
