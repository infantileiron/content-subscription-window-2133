import unittest
from datetime import date
from src.services.weeks import week_key,parse_week,window_weeks,offset_week,latest_complete_week,week_range
class WeekTests(unittest.TestCase):
 def test_iso_week_key(self):
  self.assertEqual(week_key(date(2026,11,16)),'2026-W47')
  self.assertEqual(week_key(date(2026,1,1)),'2026-W01')
  self.assertEqual(week_key(date(2025,12,29)),'2026-W01')
  self.assertEqual(week_key(date(2021,1,1)),'2020-W53')
 def test_parse_roundtrip(self):
  for key in ('2026-W01','2026-W47','2020-W53'):
   y,w=parse_week(key);self.assertEqual((y,w)[1],int(key[-2:]))
 def test_parse_rejects_bad_week(self):
  for bad in ('2026-W54','2026-W00','2026-47','xxxx-W01','2026-W1'):
   with self.assertRaises(ValueError):parse_week(bad)
 def test_window_weeks_are_four_consecutive_mondays(self):
  weeks=window_weeks('2026-W47',4)
  self.assertEqual(weeks,['2026-W44','2026-W45','2026-W46','2026-W47'])
  starts=[week_range(w)[0] for w in weeks]
  self.assertTrue(all(d.weekday()==0 for d in starts))
  self.assertEqual((starts[-1]-starts[0]).days,21)
 def test_offset_across_year_boundary(self):
  self.assertEqual(offset_week('2026-W01',-1),'2025-W52')
  self.assertEqual(offset_week('2020-W53',1),'2021-W01')
 def test_latest_complete_week_ignores_current(self):
  # 2026-11-16 是周一；最近完整自然周为上周一至周日 W46
  self.assertEqual(latest_complete_week(date(2026,11,16)),'2026-W46')
  # 周日当天当前周尚未结束，最近完整周为 W45
  self.assertEqual(latest_complete_week(date(2026,11,15)),'2026-W45')
  # 下周一滚动到 W47
  self.assertEqual(latest_complete_week(date(2026,11,23)),'2026-W47')
if __name__=='__main__':unittest.main()
