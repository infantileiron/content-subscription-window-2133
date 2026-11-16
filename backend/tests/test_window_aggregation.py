import unittest
from types import SimpleNamespace
from src.services.windows import build_window,snapshot_for_cluster,gap_list
from src.constants.enums import GAP_INSUFFICIENT,GAP_ZERO_READING
WEEKS=['2026-W44','2026-W45','2026-W46','2026-W47']
def reader(i,code):return SimpleNamespace(id=i,code=code)
def rec(rid,week,count,comp,night,source='pipeline',updated='2026-11-16T08:00:00+00:00',ridx=None):
 return SimpleNamespace(id=ridx if ridx is not None else rid*10+WEEKS.index(week),
                        reader_id=rid,week=week,reading_count=count,completion=comp,
                        night_share=night,source=source,updated_at=updated)
def four(rid,counts,comp=.5,night=.4,**kw):
 return [rec(rid,w,c,comp,night,ridx=rid*100+i,**kw) for i,(w,c) in enumerate(zip(WEEKS,counts))]
class AggregationTests(unittest.TestCase):
 def test_weighted_metrics_use_reading_weights(self):
  readers=[reader(1,'SL-001')]
  records=four(1,[10,0,30,0],comp=.8,night=.2)
  # 只在有阅读的周产生贡献
  out=build_window(readers,records,'2026-W47')
  p=out['profiles'][0]
  self.assertEqual(p['status'],'qualified');self.assertEqual(p['total_reading'],40)
  self.assertAlmostEqual(p['weighted_completion'],.8,places=6)
  self.assertAlmostEqual(p['weighted_night_share'],.2,places=6)
 def test_weighted_values_vary_by_week(self):
  readers=[reader(1,'SL-001')]
  records=[rec(1,WEEKS[0],10,.2,.1,ridx=1),rec(1,WEEKS[1],30,.8,.5,ridx=2),
           rec(1,WEEKS[2],0,.9,.9,ridx=3),rec(1,WEEKS[3],0,.1,.1,ridx=4)]
  out=build_window(readers,records,'2026-W47');p=out['profiles'][0]
  # (10*.2+30*.8)/40 = 26/40 ; (10*.1+30*.5)/40=16/40
  self.assertAlmostEqual(p['weighted_completion'],.65,places=6)
  self.assertAlmostEqual(p['weighted_night_share'],.4,places=6)
 def test_insufficient_weeks_go_to_gap_without_zero_fill(self):
  readers=[reader(1,'SL-001'),reader(2,'SL-002')]
  records=four(1,[5,5,5,5])+[rec(2,WEEKS[-1],7,.5,.5,ridx=99),rec(2,WEEKS[-2],3,.5,.5,ridx=98)]
  out=build_window(readers,records,'2026-W47')
  by={p['code']:p for p in out['profiles']}
  self.assertEqual(by['SL-001']['status'],'qualified')
  gap=by['SL-002']
  self.assertEqual(gap['status'],'gap');self.assertEqual(gap['gap_reason'],GAP_INSUFFICIENT)
  self.assertEqual(gap['present_weeks'],2);self.assertEqual(gap['missing_weeks'],WEEKS[:2])
  self.assertIsNone(gap['weighted_completion']);self.assertIsNone(gap['total_reading'] or None)
  self.assertEqual([g['code'] for g in gap_list(out)],['SL-002'])
  self.assertNotIn('SL-002',[r['code'] for r in snapshot_for_cluster(out)])
 def test_all_zero_reading_is_gap_not_zero_filled_qualified(self):
  readers=[reader(1,'SL-001')]
  records=four(1,[0,0,0,0])
  out=build_window(readers,records,'2026-W47');p=out['profiles'][0]
  self.assertEqual(p['status'],'gap');self.assertEqual(p['gap_reason'],GAP_ZERO_READING)
  self.assertEqual(snapshot_for_cluster(out),[])
 def test_latest_source_per_week_wins(self):
  readers=[reader(1,'SL-001')]
  base=four(1,[10,10,10,10],comp=.4,source='pipeline',updated='2026-11-10T08:00:00+00:00')
  # 同周更晚来源覆盖该周
  base.append(rec(1,WEEKS[-1],50,.9,.9,source='correction',updated='2026-11-17T08:00:00+00:00',ridx=777))
  out=build_window(readers,base,'2026-W47');p=out['profiles'][0]
  last=[d for d in p['weeks'] if d and d['week']==WEEKS[-1]][0]
  self.assertEqual(last['source'],'correction');self.assertEqual(last['reading_count'],50)
  self.assertEqual(p['total_reading'],80)
 def test_reconciliation_matches_detail_and_is_deterministic(self):
  readers=[reader(i,f'SL-{i:03}') for i in range(1,4)]
  records=four(1,[1,2,3,4])+four(2,[5,5,5,5])+four(3,[2,2,2,2])
  a=build_window(readers,records,'2026-W47');b=build_window(readers,records,'2026-W47')
  rec_a=a['reconciliation']
  self.assertTrue(rec_a['matched']);self.assertTrue(rec_a['reading_matched'])
  self.assertEqual(rec_a['reader_total'],3);self.assertEqual(rec_a['qualified'],3);self.assertEqual(rec_a['gaps'],0)
  self.assertEqual(rec_a['total_reading'],sum([10,20,8]))
  self.assertEqual(a['input_checksum'],b['input_checksum'])
 def test_week_detail_preserves_order_and_none_slots(self):
  readers=[reader(1,'SL-001')]
  records=[rec(1,w,5,.5,.5,ridx=i) for i,w in enumerate(WEEKS[2:])]
  out=build_window(readers,records,'2026-W47');weeks=out['profiles'][0]['weeks']
  self.assertEqual([d['week'] if d else None for d in weeks],
                   [None,None,WEEKS[2],WEEKS[3]])
if __name__=='__main__':unittest.main()
