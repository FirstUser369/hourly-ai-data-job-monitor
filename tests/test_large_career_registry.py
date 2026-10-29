import unittest
from unittest.mock import patch,Mock
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yaml
import career_discovery as c

class LargeRegistryTests(unittest.TestCase):
    def test_registry_has_at_least_100_unique_employers(self):
        rows=yaml.safe_load(Path("career_pages.yml").read_text())["companies"]
        self.assertGreaterEqual(len(rows),100)
        names=[row["company"].casefold() for row in rows]
        self.assertEqual(len(names),len(set(names)))
        for item in rows:
            self.assertTrue(c.safe_url(item["url"]))
    def test_exposed_ats_url_gets_candidate(self):
        found=c.parse_careers_html(
            '<a href="https://jobs.ashbyhq.com/modelcompany">Apply</a>',
            "https://modelcompany.example/careers","Model Company")
        self.assertEqual(found,[{"ats":"ashby","slug":"modelcompany","company":"Model Company"}])
    def test_no_ats_link_does_not_invent_a_board(self):
        self.assertEqual(c.parse_careers_html("<p>Jobs open now</p>",
            "https://example.com/careers","Example"),[])
    def test_inspect_page_reports_no_verified_ats(self):
        fake=Mock()
        fake.url="https://example.com/careers"
        fake.content=b"<html>Company careers page</html>"
        fake.text="<html>Company careers page</html>"
        fake.raise_for_status.return_value=None
        session=Mock()
        session.get.return_value=fake
        with patch.object(c.requests,"Session",return_value=session):
            boards,record=c.inspect_page({"company":"Acme","url":"https://example.com/careers"})
        self.assertEqual(boards,[])
        self.assertEqual(record["status"],"no_public_ats_found")
