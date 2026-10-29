import unittest
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch
import wide_sources as w
class WideSourcesTests(unittest.TestCase):
    def test_jobicy(self):
        jobs=w.parse_jobicy({"jobs":[{"id":1,"jobTitle":"Data Engineer","companyName":"Firm","jobGeo":"USA","jobDescription":"<p>Spark</p>","url":"https://jobicy.com/jobs/x"}]})
        self.assertEqual(jobs[0]["description"],"Spark")
        self.assertEqual(jobs[0]["source"],"Jobicy")
    def test_nomads(self):
        self.assertEqual(w.parse_nomads([{"url":"https://www.workingnomads.com/job/123","title":"ML Engineer","location":"USA"}])[0]["title"],"ML Engineer")
    def test_simplify(self):
        raw='<table><tr><td>Acme</td><td>Data Scientist</td><td>Boston, MA</td><td><a href="https://jobs.acme.test/apply">Apply</a><a href="https://simplify.jobs/p/1">Simplify</a></td><td>0d</td></tr></table>'
        self.assertEqual(w.parse_simplify(raw)[0]["url"],"https://jobs.acme.test/apply")
    def test_cache_enforces_hour(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/"jobicy.json"
            path.write_text('{"fetched":"2026-10-28T19:55:00+00:00","jobs":[]}')
            session=Mock()
            with patch.object(w,"CACHE",path):
                self.assertEqual(w.jobicy(session,datetime(2026,10,28,20,tzinfo=timezone.utc)),[])
            session.get.assert_not_called()
