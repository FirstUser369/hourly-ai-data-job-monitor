import unittest
from unittest.mock import Mock
import requests
from career_discovery import board_from_url,parse_careers_html,safe_url,classify_failure,build_review_queue

class DiscoveryTests(unittest.TestCase):
    def test_classify_restricted(self):
        for code in (401,403,406):
            response=Mock(status_code=code)
            error=requests.HTTPError("blocked",response=response)
            self.assertEqual(classify_failure(error),("access_restricted",code))
    def test_classify_rate_limit_and_not_found(self):
        self.assertEqual(classify_failure(requests.HTTPError(response=Mock(status_code=429))),("rate_limited",429))
        self.assertEqual(classify_failure(requests.HTTPError(response=Mock(status_code=404))),("invalid_or_removed_url",404))
    def test_classify_timeout_and_tls(self):
        self.assertEqual(classify_failure(requests.ReadTimeout()),("timeout",None))
        self.assertEqual(classify_failure(requests.exceptions.SSLError()),("tls_error",None))
    def test_review_queue_does_not_invent_ats(self):
        pages=[{"company":"Acme","url":"https://acme.example","failure_category":"access_restricted","http_status":403},
               {"company":"Other","url":"https://other.example","failure_category":"timeout"}]
        queue=build_review_queue(pages)
        self.assertEqual(len(queue),1)
        self.assertEqual(queue[0]["company"],"Acme")
        self.assertNotIn("slug",queue[0])
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
