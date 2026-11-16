import re
from datetime import date,timedelta,datetime,timezone
WEEK_RE=re.compile(r'^(\d{4})-W(\d{2})$')
def now_iso():
 return datetime.now(timezone.utc).isoformat()
def week_key(d:date)->str:
 y,w,_=d.isocalendar();return f'{y:04d}-W{w:02d}'
def parse_week(key:str):
 m=WEEK_RE.match(key or '')
 if not m:raise ValueError('周号格式应为 YYYY-Www，例如 2026-W45')
 y,w=int(m.group(1)),int(m.group(2))
 try:date.fromisocalendar(y,w,1)
 except ValueError:raise ValueError('周号超出该年ISO自然周范围')
 return y,w
def week_range(key:str):
 y,w=parse_week(key);monday=date.fromisocalendar(y,w,1);return monday,monday+timedelta(days=6)
def offset_week(key:str,n:int)->str:
 y,w=parse_week(key);monday=date.fromisocalendar(y,w,1)+timedelta(weeks=n);return week_key(monday)
def window_weeks(anchor_week:str,size:int):
 parse_week(anchor_week)
 if size<=0:raise ValueError('窗口周数必须为正整数')
 return [offset_week(anchor_week,n) for n in range(-(size-1),1)]
def latest_complete_week(today:date|None=None)->str:
 today=today or date.today()
 return week_key(today-timedelta(days=today.isoweekday()))
def label(key:str)->str:
 start,end=week_range(key);return f'{key}（{start.isoformat()} 至 {end.isoformat()}）'
