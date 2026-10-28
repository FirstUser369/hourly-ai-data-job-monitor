import unittest
from career_discovery import board_from_url,parse_careers_html,safe_url

class DiscoveryTests(unittest.TestCase):
    def test_ats_url_extraction(self):
        html='<a href="https://jobs.ashbyhq.com/example">Jobs</a><iframe src="https://boards.greenhouse.io/acme"></iframe>'
        boards=parse_careers_html(html,"https://example.com/careers","Acme")
        self.assertEqual({(x["ats"],x["slug"]) for x in boards},{("ashby","example"),("greenhouse","acme")})
    def test_refuse_local_hosts(self):
        self.assertFalse(safe_url("https://127.0.0.1/admin"))
        self.assertFalse(safe_url("http://some-company.com/careers"))
        self.assertIsNone(board_from_url("https://example.com/anything","Example"))
    def test_linked_company(self):
        obj=board_from_url("https://jobs.lever.co/example-team/one-post","Employer")
        self.assertEqual(obj,{"ats":"lever","slug":"example-team","company":"Employer"})
