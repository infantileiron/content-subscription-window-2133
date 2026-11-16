import pytest
from src.models.entities import Reader,WeeklyRecord,Window,WindowProfile
from src.services.window_ops import upsert_weekly,create_window,run_window_build,publish_window,current_published
from src.services.weeks import offset_week
from tests.conftest import make_reader,weekly_payload
ANCHOR='2026-W47';WEEKS=[offset_week(ANCHOR,n) for n in range(-3,1)]
def fill_four(session,code,counts,**kw):
 for w,c in zip(WEEKS,counts):
  row,action=upsert_weekly(session,code,weekly_payload(code,w,c,.6,.3,**kw));session.commit()
 return row
class TestWindowService:
 def test_build_idempotent_no_duplicate_profiles(self,s):
  make_reader(s,'SL-001');make_reader(s,'SL-002')
  fill_four(s,'SL-001',[2,4,6,8]);fill_four(s,'SL-002',[1,1,1,1])
  w,_=create_window(s,ANCHOR);s.commit()
  run_window_build(s,w.id);run_window_build(s,w.id);s.commit()
  assert s.query(WindowProfile).filter_by(window_id=w.id).count()==2
  assert s.query(WindowProfile).filter_by(window_id=w.id,reader_id=1).count()==1
 def test_gap_members_persisted_and_excluded_from_cluster_snapshot(self,s):
  make_reader(s,'SL-001');make_reader(s,'SL-002')
  fill_four(s,'SL-001',[2,4,6,8])
  upsert_weekly(s,'SL-002',weekly_payload('SL-002',WEEKS[-1],3,.5,.5));s.commit()
  w,_=create_window(s,ANCHOR);s.commit();run_window_build(s,w.id);s.commit()
  gaps=[p for p in s.query(WindowProfile).filter_by(window_id=w.id) if p.status=='gap']
  assert len(gaps)==1 and gaps[0].gap_reason=='INSUFFICIENT_WEEKS'
  assert w.result['reconciliation']['gaps']==1 and w.result['reconciliation']['matched'] is True
 def test_create_window_idempotent_same_anchor(self,s):
  w1,c1=create_window(s,ANCHOR);s.commit()
  w2,c2=create_window(s,ANCHOR);s.commit()
  assert w1.id==w2.id and c1 is True and c2 is False
  assert s.query(Window).count()==1
 def test_duplicate_weekly_same_source_updates_not_inserts(self,s):
  make_reader(s,'SL-001')
  upsert_weekly(s,'SL-001',weekly_payload('SL-001',WEEKS[0],5,.5,.5));s.commit()
  upsert_weekly(s,'SL-001',weekly_payload('SL-001',WEEKS[0],9,.7,.2));s.commit()
  rows=s.query(WeeklyRecord).all()
  assert len(rows)==1 and rows[0].reading_count==9 and rows[0].completion==.7
 def test_distinct_sources_keep_rows_latest_wins_in_window(self,s):
  make_reader(s,'SL-001')
  upsert_weekly(s,'SL-001',weekly_payload('SL-001',WEEKS[0],5,.5,.5,source='pipeline'));s.commit()
  upsert_weekly(s,'SL-001',weekly_payload('SL-001',WEEKS[0],8,.8,.8,source='correction'));s.commit()
  assert s.query(WeeklyRecord).count()==2
  w,_=create_window(s,ANCHOR);s.commit();run_window_build(s,w.id);s.commit()
  p=s.query(WindowProfile).filter_by(window_id=w.id,reader_id=1).first()
  first=p.weeks[0]
  assert first['source']=='correction' and first['reading_count']==8
 def test_frozen_week_rejects_backfill_after_publish(self,s):
  make_reader(s,'SL-001');fill_four(s,'SL-001',[2,4,6,8])
  w,_=create_window(s,ANCHOR);s.commit();run_window_build(s,w.id);s.commit()
  publish_window(s,w.id);s.commit()
  with pytest.raises(Exception) as ei:
   upsert_weekly(s,'SL-001',weekly_payload('SL-001',WEEKS[0],99,.9,.9));s.commit()
  assert '冻结' in ei.value.detail
  # 数据未被改写
  assert s.query(WeeklyRecord).filter_by(week=WEEKS[0]).one().reading_count==2
 def test_future_week_as_anchor_rejected(self,s):
  with pytest.raises(Exception) as ei:create_window(s,'2099-W01')
  assert ei.value.status_code==422
 def test_publish_only_one_window_at_a_time(self,s):
  make_reader(s,'SL-001');fill_four(s,'SL-001',[2,4,6,8])
  w1,_=create_window(s,ANCHOR);run_window_build(s,w1.id);s.commit()
  prior=offset_week(ANCHOR,-4)
  prior_weeks=[offset_week(prior,n) for n in range(-3,1)]
  for wk in prior_weeks:
   upsert_weekly(s,'SL-001',weekly_payload('SL-001',wk,3,.5,.5));s.commit()
  w2,_=create_window(s,prior);run_window_build(s,w2.id);s.commit()
  publish_window(s,w1.id);s.commit()
  with pytest.raises(Exception) as ei:publish_window(s,w2.id)
  assert ei.value.status_code==409
  assert current_published(s).id==w1.id
 def test_republish_same_window_is_idempotent(self,s):
  make_reader(s,'SL-001');fill_four(s,'SL-001',[2,4,6,8])
  w,_=create_window(s,ANCHOR);run_window_build(s,w.id);s.commit()
  publish_window(s,w.id);first=w.published_at;s.commit()
  _,changed=publish_window(s,w.id);s.commit()
  assert changed is False and w.published_at==first
 def test_build_after_interruption_recovers_same_result(self,s):
  make_reader(s,'SL-001');fill_four(s,'SL-001',[2,4,6,8])
  w,_=create_window(s,ANCHOR);s.commit()
  # 模拟中断：窗口停留在 building，无画像
  assert w.state=='building' and s.query(WindowProfile).count()==0
  run_window_build(s,w.id);s.commit()
  checksum=w.result['input_checksum']
  # 再次恢复执行
  run_window_build(s,w.id);s.commit()
  assert w.state=='ready' and w.result['input_checksum']==checksum
  assert s.query(WindowProfile).count()==1
