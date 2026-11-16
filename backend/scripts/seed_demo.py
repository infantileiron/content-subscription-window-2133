import random
from src.config.database import Base,engine,Session
from src.models.entities import User,Reader,WeeklyRecord,Window
from src.utils.security import hash_password
from src.services.weeks import latest_complete_week,offset_week
from src.services.window_ops import create_window,run_window_build,publish_window
def seed():
 Base.metadata.create_all(engine);rng=random.Random(3107)
 anchor=latest_complete_week();weeks=[offset_week(anchor,n) for n in range(-5,1)]
 with Session() as s:
  for role in ('admin','analyst','viewer'):
   email=role+'@demo.local'
   if not s.query(User).filter_by(email=email).first():s.add(User(email=email,role=role,password=hash_password('Demo123!')))
  for i in range(240):
   code=f'SL-{i+1:03}';mode=i//80
   reader=s.query(Reader).filter_by(code=code).first()
   base_reading=[4,14,26][mode];base_comp=[.32,.81,.61][mode];base_night=[.18,.23,.77][mode]
   if not reader:
    reader=Reader(code=code,weekly_reading=float(base_reading),completion=base_comp,night_share=base_night,
                  note='最近完整自然周行为聚合；模拟会员，不含个人联系方式');s.add(reader);s.flush()
   gap_member=code in ('SL-239','SL-240')
   member_weeks=weeks[-2:] if gap_member else weeks
   for wi,wk in enumerate(member_weeks):
    if s.query(WeeklyRecord).filter_by(reader_id=reader.id,week=wk,source='weekly-pipeline').first():continue
    count=max(0,int(round(rng.gauss(base_reading,[1.1,3,4][mode]))))
    comp=round(max(0,min(1,rng.gauss(base_comp,.06))),4)
    night=round(max(0,min(1,rng.gauss(base_night,.08))),4)
    s.add(WeeklyRecord(reader_id=reader.id,week=wk,reading_count=count,completion=comp,night_share=night,
                       source='weekly-pipeline',
                       note=('仅补报两周，演示四周缺口' if gap_member else '上游自然周聚合补报'),
                       updated_at='2026-11-16T08:00:00+00:00'))
  s.flush()
  existing=s.query(Window).filter_by(anchor_week=anchor).first()
  if not existing:
   w,_=create_window(s,anchor);run_window_build(s,w.id);publish_window(s,w.id)
  s.commit()
  print({'users':s.query(User).count(),'readers':s.query(Reader).count(),
         'weekly_records':s.query(WeeklyRecord).count(),
         'windows':s.query(Window).count(),'anchor_week':anchor})
if __name__=='__main__':seed()
