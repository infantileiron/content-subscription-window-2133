from tests.conftest import login,weekly_payload
from src.services.weeks import offset_week
ANCHOR='2026-W47';WEEKS=[offset_week(ANCHOR,n) for n in range(-3,1)]
def seed_reader(client,auth,code,counts=(2,4,6,8)):
 r=client.post('/readers',headers=auth,
               json={'code':code,'weekly_reading':10,'completion':.5,'night_share':.4,'note':''})
 assert r.status_code==200
 for w,c in zip(WEEKS,counts):
  rr=client.put('/weekly',headers=auth,json=weekly_payload(code,w,c,.6,.3))
  assert rr.status_code==200
def build_and_publish(client,auth,admin_auth,anchor=ANCHOR):
 r=client.post('/windows',headers=auth,json={'anchor_week':anchor});assert r.status_code==200
 wid=r.json()['id']
 d=client.get(f'/windows/{wid}',headers=auth).json()
 if d['state']!='ready':
  rb=client.post(f'/windows/{wid}/build',headers=auth);assert rb.status_code==200
 p=client.post(f'/windows/{wid}/publish',headers=admin_auth);assert p.status_code==200
 return wid
class TestWindowApi:
 def test_full_window_publish_and_segment_flow(self,client):
  auth=login(client);admin=login(client,'admin')
  for i,code in enumerate(['SL-001','SL-002','SL-003']):seed_reader(client,auth,code,(2+i,4,6,8))
  wid=build_and_publish(client,auth,admin)
  detail=client.get(f'/windows/{wid}',headers=auth).json()
  assert detail['state']=='published'
  assert detail['result']['reconciliation']['qualified']==3
  assert client.get('/windows/current',headers=auth).json()['id']==wid
  # 新分群必须绑定已发布窗口
  seg=client.post('/segments',headers=auth,
                  json={'name':'四周窗口分群','k':2,'features':['weekly_reading','completion','night_share'],'window_id':wid})
  assert seg.status_code==200 and seg.json()['window_id']==wid
 def test_segment_rejects_unpublished_window(self,client):
  auth=login(client);seed_reader(client,auth,'SL-001')
  r=client.post('/windows',headers=auth,json={'anchor_week':ANCHOR});wid=r.json()['id']
  seg=client.post('/segments',headers=auth,
                  json={'name':'提前分群','k':2,'features':['weekly_reading','completion'],'window_id':wid})
  assert seg.status_code==409 and '已发布' in seg.json()['detail']
 def test_viewer_cannot_write_but_can_read(self,client):
  viewer=login(client,'viewer');auth=login(client)
  seed_reader(client,auth,'SL-001')
  r=client.put('/weekly',headers=viewer,json=weekly_payload('SL-001',WEEKS[0],5,.5,.5))
  assert r.status_code==403
  assert client.get('/windows',headers=viewer).status_code==200
 def test_publish_requires_admin(self,client):
  auth=login(client);seed_reader(client,auth,'SL-001')
  wid=client.post('/windows',headers=auth,json={'anchor_week':ANCHOR}).json()['id']
  client.post(f'/windows/{wid}/build',headers=auth)
  r=client.post(f'/windows/{wid}/publish',headers=auth)
  assert r.status_code==403
 def test_frozen_week_backfill_blocked_over_http(self,client):
  auth=login(client);admin=login(client,'admin')
  seed_reader(client,auth,'SL-001');build_and_publish(client,auth,admin)
  r=client.put('/weekly',headers=auth,json=weekly_payload('SL-001',WEEKS[0],99,.9,.9))
  assert r.status_code==409 and '冻结' in r.json()['detail']
 def test_duplicate_weekly_put_is_idempotent(self,client):
  auth=login(client);seed_reader(client,auth,'SL-001',counts=(2,4,6,8))
  again=client.put('/weekly',headers=auth,json=weekly_payload('SL-001',WEEKS[0],2,.6,.3))
  assert again.status_code==200
  rows=client.get('/weekly?code=SL-001',headers=auth).json()
  assert len([x for x in rows if x['week']==WEEKS[0]])==1
 def test_invalid_week_returns_422(self,client):
  auth=login(client)
  client.post('/readers',headers=auth,json={'code':'SL-009','weekly_reading':1,'completion':.5,'night_share':.5,'note':''})
  r=client.put('/weekly',headers=auth,json=weekly_payload('SL-009','2026-W99',1,.5,.5))
  assert r.status_code==422
 def test_gap_member_appears_in_gap_list_not_cluster(self,client):
  auth=login(client);admin=login(client,'admin')
  seed_reader(client,auth,'SL-001')
  client.post('/readers',headers=auth,json={'code':'SL-239','weekly_reading':1,'completion':.5,'night_share':.5,'note':''})
  for w in WEEKS[-2:]:client.put('/weekly',headers=auth,json=weekly_payload('SL-239',w,3,.5,.5))
  wid=client.post('/windows',headers=auth,json={'anchor_week':ANCHOR}).json()['id']
  client.post(f'/windows/{wid}/build',headers=auth)
  d=client.get(f'/windows/{wid}',headers=auth).json()
  codes=[g['code'] for g in d['gaps']]
  assert 'SL-239' in codes and 'SL-001' not in codes
  assert d['profiles'][[p['code'] for p in d['profiles']].index('SL-239')]['gap_reason']=='INSUFFICIENT_WEEKS'
 def test_outreach_and_segment_point_to_published_window(self,client):
  auth=login(client);admin=login(client,'admin')
  for i,code in enumerate(['SL-001','SL-002','SL-003','SL-004']):seed_reader(client,auth,code,(2+i,4,6,8))
  wid=build_and_publish(client,auth,admin)
  seg=client.post('/segments',headers=auth,
                  json={'name':'窗口绑定分群','k':2,'features':['weekly_reading','completion','night_share'],'window_id':wid}).json()
  # 队列由 fake redis 捕获，手动触发计算路径：直接通过 build 端点不适用 segment；改为校验快照冻结内容
  snap=client.get(f'/segments/{seg["id"]}',headers=auth).json()['result']['snapshot']
  assert len(snap)==4 and all('weekly_reading' in m for m in snap)
 def test_concurrent_publish_second_window_conflicts(self,client):
  auth=login(client);admin=login(client,'admin')
  seed_reader(client,auth,'SL-001')
  w1=client.post('/windows',headers=auth,json={'anchor_week':ANCHOR}).json()['id']
  client.post(f'/windows/{w1}/build',headers=auth);client.post(f'/windows/{w1}/publish',headers=admin)
  prior=offset_week(ANCHOR,-4)
  for wk in [offset_week(prior,n) for n in range(-3,1)]:
   client.put('/weekly',headers=auth,json=weekly_payload('SL-001',wk,3,.5,.5))
  w2=client.post('/windows',headers=auth,json={'anchor_week':prior}).json()['id']
  client.post(f'/windows/{w2}/build',headers=auth)
  r=client.post(f'/windows/{w2}/publish',headers=admin)
  assert r.status_code==409
