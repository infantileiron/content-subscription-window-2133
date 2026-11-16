import os
os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('REDIS_URL','redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET','test-secret-3107')
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from src.config import database as db_mod
from src.models import entities
from src.utils.security import hash_password
import src.routes.api as api_mod

@pytest.fixture()
def session_factory():
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},
                      poolclass=StaticPool)
 entities.Base.metadata.create_all(engine)
 factory=sessionmaker(bind=engine,expire_on_commit=False)
 db_mod.engine=engine;db_mod.Session=factory
 yield factory
 entities.Base.metadata.drop_all(engine)

@pytest.fixture(autouse=True)
def freeze_clock(monkeypatch):
 # 固定“今天”为锚点周 W47 结束后的周一，使 W47 始终是最近完整自然周
 import src.services.weeks as weeks
 import src.services.window_ops as ops
 frozen=lambda *a,**k:'2026-W47'
 monkeypatch.setattr(weeks,'latest_complete_week',frozen)
 monkeypatch.setattr(ops,'latest_complete_week',frozen)
 yield

@pytest.fixture(autouse=True)
def bind_worker_session(session_factory,tmp_path):
 import src.worker as worker
 from pathlib import Path
 worker.Session=session_factory
 worker.ARTIFACT_DIR=tmp_path/'artifacts'
 yield
 worker.Session=db_mod.Session
 worker.ARTIFACT_DIR=Path(os.environ.get('ARTIFACT_DIR','/artifacts'))

@pytest.fixture()
def s(session_factory):
 with session_factory() as session:yield session

class FakeRedis:
 def __init__(self):self.queues={}
 def rpush(self,k,v):self.queues.setdefault(k,[]).append(v)
 def blpop(self,keys,timeout=3):
  for k in keys:
   if self.queues.get(k):return k,self.queues[k].pop(0)
  return None
 def ping(self):return True

class _FakeRedisModule:
 def __init__(self):self._inst=FakeRedis()
 def from_url(self,*a,**k):return self._inst
 def __call__(self,*a,**k):return self._inst

@pytest.fixture()
def client(session_factory,monkeypatch):
 fake_mod=_FakeRedisModule();monkeypatch.setattr(api_mod.redis,'Redis',fake_mod)
 from src.main import app
 def override_db():
  with session_factory() as session:yield session
 app.dependency_overrides[db_mod.db]=override_db
 with TestClient(app) as c:
  with session_factory() as session:
   for role in ('admin','analyst','viewer'):
    session.add(entities.User(email=role+'@demo.local',role=role,password=hash_password('Demo123!')))
   session.commit()
  c.fake_redis=fake_mod._inst;yield c
 app.dependency_overrides.clear()

def login(client,role='analyst'):
 r=client.post('/auth/login',json={'email':role+'@demo.local','password':'Demo123!'})
 return {'Authorization':'Bearer '+r.json()['token']}

def make_reader(session,code):
 r=entities.Reader(code=code,weekly_reading=10,completion=.5,night_share=.4,note='');session.add(r);session.commit();return r

def weekly_payload(code,week,count,comp,night,source='weekly-pipeline'):
 return {'code':code,'week':week,'reading_count':count,'completion':comp,
         'night_share':night,'source':source,'note':'测试'}
