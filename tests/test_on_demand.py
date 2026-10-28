import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from on_demand import assess_new, safe_link, NOW

class OnDemandTests(unittest.TestCase):
    def test_employer_published_after_last_run(self):
        checkpoint=NOW-timedelta(hours=6)
        fresh=NOW-timedelta(minutes=15)
        old=NOW-timedelta(hours=7)
        self.assertIn("Published since",assess_new({"ats":"greenhouse","published":fresh},checkpoint,None))
        self.assertIsNone(assess_new({"ats":"greenhouse","published":old},checkpoint,None))
        self.assertIsNone(assess_new({"ats":"greenhouse","published":fresh},checkpoint,("old_seen",fresh.isoformat())))
    def test_unknown_time_only_if_new(self):
        checkpoint=NOW-timedelta(hours=5)
        job={"ats":"lever","published":None}
        self.assertIn("Newly discovered",assess_new(job,checkpoint,None))
        self.assertIsNone(assess_new(job,checkpoint,("seen",None)))
    def test_tracker_age_comparison(self):
        checkpoint=NOW-timedelta(hours=3)
        recent={"ats":"github_tracker","github_reported_age_minutes":120}
        older={"ats":"github_tracker","github_reported_age_minutes":240}
        self.assertIn("tracker reports posted",assess_new(recent,checkpoint,None))
        self.assertIsNone(assess_new(older,checkpoint,None))
        self.assertIsNone(assess_new(recent,checkpoint,("seen",None)))
    def test_link_safety(self):
        self.assertEqual(safe_link("https://example.org/apply"),"https://example.org/apply")
        self.assertEqual(safe_link("javascript:alert(1)"),"")
        self.assertEqual(safe_link("http://example.org/apply"),"")

if __name__=="__main__":
    unittest.main()
