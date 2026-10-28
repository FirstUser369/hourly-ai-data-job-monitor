import unittest
from datetime import datetime,timezone,timedelta
from github_watch import parse_zapply,parse_ml_list,reported_minutes,recent_tracker_job

class GitHubWatchTests(unittest.TestCase):
    def test_age_only_precise_minutes(self):
        self.assertEqual(reported_minutes("22m"),22)
        self.assertEqual(reported_minutes("59m"),59)
        self.assertIsNone(reported_minutes("1h"))
        self.assertIsNone(reported_minutes("Today"))
        self.assertIsNone(reported_minutes("Date unknown"))
    def test_markdown_roles_and_links(self):
        markdown = (
            "| **KeyBank** | Quantitative Analytics Associate | Brooklyn, OH | 23m | | [Apply](https://zapply.jobs/l/d/keybank-123) |\n"
            "| **USAA** | Data Scientist Intern | Plano, TX | 22m | | [Apply](https://zapply.jobs/l/d/usaa-123) |\n"
            "| **Old** | Data Engineer | Austin, TX | 1h | | [Apply](https://zapply.jobs/l/d/old-123) |\n"
        )
        jobs=parse_zapply(markdown)
        self.assertEqual(len(jobs),2)
        self.assertEqual(jobs[0]["github_reported_age_minutes"],23)
        self.assertEqual(jobs[0]["title"],"Quantitative Analytics Associate")
        self.assertFalse(jobs[0]["employer_direct"])
    def test_ml_employer_proof(self):
        now=datetime(2026,10,28,19,0,tzinfo=timezone.utc)
        item=dict(active=True,is_usa=True,company="Scopely",title="ML Engineer",
            locations=["Boston, MA"],id="a1",apply_url="https://example.com/apply",
            verification=dict(status="live",via="greenhouse",posted=int((now-timedelta(minutes=15)).timestamp())))
        jobs=parse_ml_list([item])
        self.assertTrue(recent_tracker_job(jobs[0],now))
        self.assertFalse(recent_tracker_job(jobs[0],now+timedelta(hours=2)))
        self.assertEqual(len(parse_ml_list([{**item,"verification":{**item["verification"],"via":"unknown"}}])),0)

if __name__=="__main__":
    unittest.main()
