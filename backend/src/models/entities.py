from sqlalchemy import Column,Integer,String,Float,JSON,Text,ForeignKey,UniqueConstraint,Index
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True);password=Column(String(200));role=Column(String(20))
class Reader(Base):
 __tablename__='readers'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);weekly_reading=Column(Float);completion=Column(Float);night_share=Column(Float);note=Column(Text,default='')
class WeeklyRecord(Base):
 __tablename__='weekly_records'
 id=Column(Integer,primary_key=True)
 reader_id=Column(Integer,ForeignKey('readers.id'),nullable=False)
 week=Column(String(8),nullable=False)
 reading_count=Column(Integer,nullable=False)
 completion=Column(Float,nullable=False)
 night_share=Column(Float,nullable=False)
 source=Column(String(100),nullable=False,default='manual')
 note=Column(Text,default='')
 updated_at=Column(String(40),nullable=False)
 __table_args__=(UniqueConstraint('reader_id','week','source',name='uq_weekly_reader_week_source'),Index('ix_weekly_reader_week','reader_id','week'))
class Window(Base):
 __tablename__='windows'
 id=Column(Integer,primary_key=True)
 anchor_week=Column(String(8),nullable=False,unique=True)
 window_weeks=Column(JSON,nullable=False)
 state=Column(String(20),nullable=False,default='building')
 result=Column(JSON)
 error=Column(Text,default='')
 published_at=Column(String(40))
 created_at=Column(String(40),nullable=False)
class WindowProfile(Base):
 __tablename__='window_profiles'
 id=Column(Integer,primary_key=True)
 window_id=Column(Integer,ForeignKey('windows.id'),nullable=False)
 reader_id=Column(Integer,nullable=False)
 code=Column(String(60),nullable=False)
 status=Column(String(20),nullable=False)
 total_reading=Column(Integer,default=0)
 weighted_completion=Column(Float)
 weighted_night_share=Column(Float)
 weeks=Column(JSON,nullable=False)
 gap_reason=Column(String(40))
 __table_args__=(UniqueConstraint('window_id','reader_id',name='uq_window_reader'),Index('ix_window_profile_window','window_id'))
class Segment(Base):
 __tablename__='segments'
 id=Column(Integer,primary_key=True);name=Column(String(100));k=Column(Integer);features=Column(JSON);state=Column(String(20),default='queued');result=Column(JSON);error=Column(Text,default='');window_id=Column(Integer,ForeignKey('windows.id'))
class Outreach(Base):
 __tablename__='outreaches'
 id=Column(Integer,primary_key=True);segment_id=Column(Integer,ForeignKey('segments.id'));cluster_id=Column(Integer);title=Column(String(100));note=Column(Text);members=Column(JSON);status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
