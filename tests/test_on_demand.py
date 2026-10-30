import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from on_demand import assess_new, source_time, safe_link, NOW
from strict_jobs import recent_employer_post, verify_application

class OnDemandTests(unittest.TestCase):
    def test_recent_employer_post_since_checkpoint(self):
        checkpoint=NOW-timedelta(hours=12)
        recent=NOW-timedelta(hours=1)
        job={"ats":"greenhouse","published":recent}
        self.assertIn("Employer publication",assess_new(job,checkpoint,None))
        self.assertIn("Employer publication",assess_new(job,checkpoint,("seen",recent.isoformat())))

    def test_no_stale_jobs_even_if_never_discovered(self):
        old=NOW-timedelta(days=10)
        checkpoint=NOW-timedelta(days=3)
        self.assertIsNone(assess_new({"ats":"ashby","published":old},checkpoint,None))
        self.assertIsNone(assess_new({"ats":"greenhouse","published":NOW+timedelta(hours=1)},checkpoint,None))

    def test_source_dates_must_be_since_previous_run(self):
        checkpoint=NOW-timedelta(hours=3)
        for ats in ("himalayas","jobicy","workingnomads","remoteok","arbeitnow",
                    "github_ml_tracker","greenhouse","ashby"):
            with self.subTest(ats=ats):
                self.assertIsNotNone(source_time({"ats":ats,"published":NOW-timedelta(minutes=20)},checkpoint))
                self.assertIsNone(source_time({"ats":ats,"published":NOW-timedelta(hours=4)},checkpoint))
                self.assertIsNone(source_time({"ats":ats,"published":None},checkpoint))

    def test_github_ages_and_unknown_dates(self):
        checkpoint=NOW-timedelta(minutes=80)
        self.assertIsNotNone(source_time({"ats":"github_zapply","github_reported_age_minutes":22},checkpoint))
        self.assertIsNone(source_time({"ats":"github_zapply","github_reported_age_minutes":80},checkpoint))
        self.assertIsNone(source_time({"ats":"github_zapply","github_reported_age_minutes":60},checkpoint))
        self.assertIsNone(source_time({"ats":"github_applyguy","tracker_reported_posted":NOW.strftime("%Y-%m-%d")},checkpoint))

    def test_himalayas_expiry_excludes_closed(self):
        checkpoint=NOW-timedelta(hours=3)
        job={"ats":"himalayas","published":NOW-timedelta(minutes=20),"expiry":NOW-timedelta(minutes=1)}
        self.assertIsNone(source_time(job,checkpoint))
        job["expiry"]=NOW+timedelta(hours=2)
        self.assertIn("updated",source_time(job,checkpoint)[1])

    def test_strict_48_hour_cutoff(self):
        self.assertTrue(recent_employer_post({"ats":"ashby","published":NOW-timedelta(hours=47)},NOW))
        self.assertFalse(recent_employer_post({"ats":"ashby","published":NOW-timedelta(hours=49)},NOW))
        self.assertFalse(recent_employer_post({"ats":"ashby","published":NOW+timedelta(minutes=2)},NOW))

    def test_closed_and_generic_careers_pages_rejected(self):
        job={"ats":"greenhouse","url":"https://job-boards.greenhouse.io/firm/jobs/123"}
        client=Mock()
        response=Mock(status_code=200,url=job["url"],text="This job is no longer available")
        client.get.return_value=response
        self.assertFalse(verify_application(job,client)[0])
        response.text="Open position: Data Engineer. Apply now."
        response.url="https://firm.example/careers"
        self.assertFalse(verify_application(job,client)[0])
        response.url=job["url"]
        self.assertTrue(verify_application(job,client)[0])
        response.status_code=404
        self.assertFalse(verify_application(job,client)[0])

    def test_invalid_application_url(self):
        self.assertFalse(verify_application({"ats":"greenhouse","url":"javascript:alert(1)"})[0])
        self.assertFalse(verify_application({"ats":"github_tracker","url":"https://example.com/role"})[0])

    def test_link_safety(self):
        self.assertEqual(safe_link("https://example.org/apply"),"https://example.org/apply")
        self.assertEqual(safe_link("javascript:alert(1)"),"")
        self.assertEqual(safe_link("http://example.org/apply"),"")

if __name__=="__main__":
    unittest.main()
