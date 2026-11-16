import hashlib,json
from src.constants.enums import WINDOW_SIZE,GAP_INSUFFICIENT,GAP_ZERO_READING
from src.services.weeks import window_weeks,label
def _checksum(rows):
 payload=json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':'))
 return hashlib.sha256(payload.encode()).hexdigest()
def build_window(readers,records,anchor_week,size=WINDOW_SIZE):
 weeks=window_weeks(anchor_week,size);week_set=set(weeks)
 in_window=[r for r in records if r.week in week_set]
 grouped={}
 for r in in_window:grouped.setdefault(r.reader_id,[]).append(r)
 profiles=[];qualified=0;gaps=0;reconcile_total=0
 source_tally={}
 for reader in sorted(readers,key=lambda x:x.id):
  chosen={}
  for r in grouped.get(reader.id,[]):
   cur=chosen.get(r.week)
   if cur is None or (r.updated_at,r.id)>(cur.updated_at,cur.id):chosen[r.week]=r
  detail=[dict(week=w,
               reading_count=chosen[w].reading_count,
               completion=chosen[w].completion,
               night_share=chosen[w].night_share,
               source=chosen[w].source,
               updated_at=chosen[w].updated_at) if w in chosen else None for w in weeks]
  present=[d for d in detail if d]
  if len(present)<size:
   reason=GAP_INSUFFICIENT;gaps+=1
   profiles.append(dict(reader_id=reader.id,code=reader.code,status='gap',weeks=detail,
                        present_weeks=len(present),total_reading=None,
                        weighted_completion=None,weighted_night_share=None,gap_reason=reason,
                        missing_weeks=[w for w in weeks if w not in chosen]))
   continue
  total=sum(d['reading_count'] for d in present)
  if total<=0:
   gaps+=1
   profiles.append(dict(reader_id=reader.id,code=reader.code,status='gap',weeks=detail,
                        present_weeks=size,total_reading=0,
                        weighted_completion=None,weighted_night_share=None,
                        gap_reason=GAP_ZERO_READING,missing_weeks=[]))
   continue
  wc=round(sum(d['reading_count']*d['completion'] for d in present)/total,6)
  wn=round(sum(d['reading_count']*d['night_share'] for d in present)/total,6)
  qualified+=1;reconcile_total+=total
  for d in present:source_tally[d['source']]=source_tally.get(d['source'],0)+d['reading_count']
  profiles.append(dict(reader_id=reader.id,code=reader.code,status='qualified',weeks=detail,
                       present_weeks=size,total_reading=total,
                       weighted_completion=wc,weighted_night_share=wn,gap_reason=None,
                       missing_weeks=[]))
 checksum_input=sorted([dict(reader_id=r.reader_id,week=r.week,source=r.source,
                             reading_count=r.reading_count,completion=r.completion,
                             night_share=r.night_share,updated_at=r.updated_at) for r in in_window],
                       key=lambda d:(d['reader_id'],d['week'],d['updated_at'],d['source']))
 detail_sum=sum(d['reading_count'] for p in profiles if p['status']=='qualified' for d in p['weeks'])
 return dict(anchor_week=anchor_week,size=size,
             window_weeks=[dict(week=w,label=label(w)) for w in weeks],
             gap_policy='不足四周或四周零阅读的会员进入缺口清单，不补零、不参与聚类',
             profiles=profiles,
             reconciliation=dict(reader_total=len(readers),qualified=qualified,gaps=gaps,
                                 matched=qualified+gaps==len(readers),
                                 total_reading=reconcile_total,
                                 detail_reading_sum=detail_sum,
                                 reading_matched=reconcile_total==detail_sum,
                                 source_reading=source_tally),
             input_checksum=_checksum(checksum_input))
def snapshot_for_cluster(result):
 return [dict(id=p['reader_id'],code=p['code'],
              weekly_reading=p['total_reading'],
              completion=p['weighted_completion'],
              night_share=p['weighted_night_share']) for p in result['profiles'] if p['status']=='qualified']
def gap_list(result):return [dict(code=p['code'],gap_reason=p['gap_reason'],
                                  present_weeks=p['present_weeks'],
                                  missing_weeks=p['missing_weeks'],
                                  total_reading=p['total_reading']) for p in result['profiles'] if p['status']=='gap']
