from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from src.constants.enums import WINDOW_SIZE
from src.models.entities import Reader,WeeklyRecord,Window,WindowProfile
from src.services.weeks import parse_week,now_iso,latest_complete_week,window_weeks
from src.services.windows import build_window
QUEUE_WINDOWS='reader:windows'
def _frozen_weeks(s):
 rows=s.query(Window).filter(Window.state=='published',Window.result.isnot(None)).all()
 return {w for row in rows for w in row.window_weeks}
def upsert_weekly(s,code,data):
 reader=s.query(Reader).filter_by(code=code).first()
 if not reader:raise HTTPException(404,'会员不存在，请先建档')
 parse_week(data['week'])
 if data['week'] in _frozen_weeks(s):
  raise HTTPException(409,'该自然周已随窗口发布并冻结，旧周补报不能改写已更新周')
 existing=s.query(WeeklyRecord).filter_by(reader_id=reader.id,week=data['week'],source=data['source']).first()
 ts=now_iso()
 if existing:
  existing.reading_count=data['reading_count'];existing.completion=data['completion']
  existing.night_share=data['night_share'];existing.note=data.get('note','');existing.updated_at=ts
  action='修订周阅读 '+code+' '+data['week']+'/'+data['source']
 else:
  existing=WeeklyRecord(reader_id=reader.id,week=data['week'],
                        reading_count=data['reading_count'],completion=data['completion'],
                        night_share=data['night_share'],source=data['source'],
                        note=data.get('note',''),updated_at=ts)
  s.add(existing);action='录入周阅读 '+code+' '+data['week']+'/'+data['source']
 try:s.flush()
 except IntegrityError:s.rollback();raise HTTPException(409,'同一会员、同一周、同一来源只能有一条记录')
 return existing,action
def create_window(s,anchor_week,size=WINDOW_SIZE):
 parse_week(anchor_week)
 if anchor_week>latest_complete_week():
  raise HTTPException(422,'锚点周必须是已经结束的完整自然周')
 w=s.query(Window).filter_by(anchor_week=anchor_week).first()
 if w:return w,False
 w=Window(anchor_week=anchor_week,window_weeks=[],state='building',created_at=now_iso())
 s.add(w);s.flush();return w,True
def run_window_build(s,window_id):
 w=s.get(Window,window_id)
 if not w:raise HTTPException(404,'窗口不存在')
 if w.state=='published':return w,False
 weeks=window_weeks(w.anchor_week,WINDOW_SIZE)
 readers=s.query(Reader).order_by(Reader.id).all()
 records=s.query(WeeklyRecord).filter(WeeklyRecord.week.in_(weeks)).all()
 result=build_window(readers,records,w.anchor_week,WINDOW_SIZE)
 w.window_weeks=[x['week'] for x in result['window_weeks']];w.result=result
 w.state='ready';w.error='';w.published_at=None
 existing={p.reader_id:p for p in s.query(WindowProfile).filter_by(window_id=w.id).all()}
 for p in result['profiles']:
  row=existing.pop(p['reader_id'],None)
  if row is None:
   row=WindowProfile(window_id=w.id,reader_id=p['reader_id']);s.add(row)
  row.code=p['code'];row.status=p['status'];row.total_reading=p['total_reading']
  row.weighted_completion=p['weighted_completion'];row.weighted_night_share=p['weighted_night_share']
  row.weeks=p['weeks'];row.gap_reason=p['gap_reason']
 for stale in existing.values():s.delete(stale)
 s.flush();return w,True
def publish_window(s,window_id):
 w=s.get(Window,window_id)
 if not w:raise HTTPException(404,'窗口不存在')
 if w.state=='published':return w,False
 if w.state!='ready':raise HTTPException(409,'窗口尚未完成四周画像计算，不能发布')
 lock=s.query(Window).filter_by(state='published')
 if s.get_bind().dialect.name!='sqlite':lock=lock.with_for_update()
 current=lock.first()
 if current and current.id!=w.id:raise HTTPException(409,'已有发布窗口 #%d，同版窗口竞争下仅允许一次发布'%current.id)
 w.state='published';w.published_at=now_iso();s.flush();return w,True
def current_published(s):
 return s.query(Window).filter_by(state='published').order_by(Window.id.desc()).first()
def enqueue_window(redis_client,window_id):
 redis_client.rpush(QUEUE_WINDOWS,window_id)
