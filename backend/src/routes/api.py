import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.exc import IntegrityError
from src.config.database import db
from src.models.entities import User,Reader,Segment,Outreach,Audit,WeeklyRecord,Window,WindowProfile
from src.schemas.business import Login,ReaderInput,SegmentInput,OutreachInput,WeeklyInput,WindowInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.controllers.business import ensure_segment
from src.services.window_ops import upsert_weekly,create_window,run_window_build,publish_window,current_published,enqueue_window
from src.services.windows import snapshot_for_cluster,gap_list
router=APIRouter()
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
@router.get('/readers')
def readers(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Reader).order_by(Reader.id).all()]
@router.post('/readers')
def create(data:ReaderInput,u=Depends(editor),s=Depends(db)):
 r=Reader(**data.model_dump());s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'会员编号重复')
 audit(s,u,'录入阅读档案 '+r.code);return dump(r)
@router.put('/readers/{i}')
def edit(i:int,data:ReaderInput,u=Depends(editor),s=Depends(db)):
 r=s.get(Reader,i)
 if not r:raise HTTPException(404,'会员档案不存在')
 for k,v in data.model_dump().items():setattr(r,k,v)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'会员编号重复')
 audit(s,u,'修订档案 '+str(i));return dump(r)
@router.get('/weekly')
def weekly(u=Depends(current),s=Depends(db),code:str|None=None,week:str|None=None):
 q=s.query(WeeklyRecord,Reader.code).join(Reader,WeeklyRecord.reader_id==Reader.id)
 if code:q=q.filter(Reader.code==code)
 if week:q=q.filter(WeeklyRecord.week==week)
 return [{**dump(r),'code':c} for r,c in q.order_by(WeeklyRecord.week,WeeklyRecord.reader_id,WeeklyRecord.source).all()]
@router.put('/weekly')
def put_weekly(data:WeeklyInput,u=Depends(editor),s=Depends(db)):
 payload=data.model_dump();code=payload.pop('code')
 r,action=upsert_weekly(s,code,payload);s.commit();audit(s,u,action)
 return {**dump(r),'code':code}
@router.get('/windows')
def windows(u=Depends(current),s=Depends(db)):
 return [dict(dump(w),gap_count=len(gap_list(w.result)) if w.result else None) for w in s.query(Window).order_by(Window.id.desc()).all()]
@router.get('/windows/current')
def current_window(u=Depends(current),s=Depends(db)):
 w=current_published(s)
 if not w:raise HTTPException(404,'尚无已发布窗口')
 return dump(w)
@router.post('/windows')
def new_window(data:WindowInput,u=Depends(editor),s=Depends(db)):
 w,created=create_window(s,data.anchor_week)
 s.commit()
 try:enqueue_window(redis.Redis.from_url(os.environ['REDIS_URL']),w.id)
 except redis.RedisError:
  w.state='failed';w.error='队列暂不可用，请稍后重试';s.commit();raise HTTPException(503,w.error)
 audit(s,u,('创建' if created else '重新计算')+'四周窗口 '+w.anchor_week);return dump(w)
@router.post('/windows/{i}/build')
def rebuild(i:int,u=Depends(editor),s=Depends(db)):
 w=s.get(Window,i)
 if not w:raise HTTPException(404,'窗口不存在')
 if w.state=='published':raise HTTPException(409,'已发布窗口冻结，不能重新计算')
 run_window_build(s,i);s.commit();audit(s,u,'手动重算窗口 '+str(i));return dump(w)
@router.post('/windows/{i}/publish')
def do_publish(i:int,u=Depends(admin),s=Depends(db)):
 w,changed=publish_window(s,i)
 s.commit()
 if changed:audit(s,u,'发布四周窗口 '+w.anchor_week)
 return dump(w)
@router.get('/windows/{i}')
def window_detail(i:int,u=Depends(current),s=Depends(db)):
 w=s.get(Window,i)
 if not w:raise HTTPException(404,'窗口不存在')
 profiles=s.query(WindowProfile).filter_by(window_id=i).order_by(WindowProfile.reader_id).all()
 return dict(dump(w),profiles=[dump(p) for p in profiles],gaps=gap_list(w.result) if w.result else [])
@router.get('/windows/{i}/export')
def export_window(i:int,u=Depends(current),s=Depends(db)):
 w=s.get(Window,i)
 if not w:raise HTTPException(404,'窗口不存在')
 return Response(json.dumps(dump(w),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="reader-window-{i}.json"'})
@router.get('/segments')
def segments(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Segment).order_by(Segment.id.desc()).all()]
@router.post('/segments')
def train(data:SegmentInput,u=Depends(editor),s=Depends(db)):
 w=s.get(Window,data.window_id)
 if not w:raise HTTPException(404,'所选窗口不存在')
 if w.state!='published':raise HTTPException(409,'窗口发布前的新分群只能引用已发布的上一版完整窗口')
 rows=snapshot_for_cluster(w.result)
 if not rows:raise HTTPException(422,'当前窗口没有满足四周的合格会员，无法分群')
 r=Segment(name=data.name,k=data.k,features=data.features,window_id=w.id,result={'snapshot':rows,'window_id':w.id,'anchor_week':w.anchor_week});s.add(r);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('reader:segments',r.id)
 except redis.RedisError:r.state='failed';r.error='队列暂不可用，请稍后重试';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交分群 '+str(r.id)+' 基于窗口 '+w.anchor_week);return dump(r)
@router.get('/segments/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_segment(s,i))
@router.get('/segments/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_segment(s,i)
 if r.state!='done':raise HTTPException(409,'仅成功分群可导出')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="reader-segments-{i}.json"'})
@router.get('/outreaches')
def outreaches(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Outreach).order_by(Outreach.id.desc()).all()]
@router.post('/outreaches')
def outreach(data:OutreachInput,u=Depends(editor),s=Depends(db)):
 r=ensure_segment(s,data.segment_id)
 if r.state!='done':raise HTTPException(409,'分群完成后才能制定触达方案')
 members=[m['code'] for m in r.result['members'] if m['cluster_id']==data.cluster_id]
 if not members:raise HTTPException(422,'该版本没有所选群组')
 o=Outreach(**data.model_dump(),members=members);s.add(o);s.commit();audit(s,u,'起草触达方案 '+str(o.id));return dump(o)
@router.post('/outreaches/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=s.get(Outreach,i)
 if not r:raise HTTPException(404,'触达方案不存在')
 if r.status!='draft':raise HTTPException(409,'已签核方案不可重复签核')
 r.status='approved';s.commit();audit(s,u,'签核触达方案 '+str(i));return dump(r)
@router.get('/outreaches/{i}/export')
def export_outreach(i:int,u=Depends(current),s=Depends(db)):
 r=s.get(Outreach,i)
 if not r:raise HTTPException(404,'触达方案不存在')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="reader-outreach-{i}.json"'})
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]
