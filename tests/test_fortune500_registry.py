import unittest
from unittest.mock import Mock,patch
import fortune500_registry as f
from career_discovery import career_links

class Fortune2026Tests(unittest.TestCase):
    def test_exact_500_with_domains(self):
        csv_rows=["rank,company,domain"]
        for i in range(1,501):
            csv_rows.append(str(i)+",Example "+str(i)+",company"+str(i)+".example")
        response=Mock(content=("\n".join(csv_rows)+"\n").encode())
        session=Mock()
        session.get.return_value=response
        rows=f.load_fortune500(session)
        self.assertEqual(len(rows),500)
        self.assertEqual(rows[0]["url"],"https://company1.example/")
        self.assertEqual(rows[-1]["fortune_rank"],500)
    def test_reject_incomplete_source(self):
        response=Mock(content=b"rank,company,domain\n1,Company,example.com\n")
        session=Mock()
        session.get.return_value=response
        with self.assertRaisesRegex(ValueError,"Expected exactly 500"):
            f.load_fortune500(session)
    def test_career_anchor_discovery(self):
        html='<a href="/careers/">Careers</a><a href="/products">Products</a><a href="https://unrelated.example/jobs">jobs</a>'
        self.assertEqual(career_links(html,"https://example.com/"),["https://example.com/careers/"])
    def test_no_fabricated_career_link(self):
        self.assertEqual(career_links('<p>No careers link</p>',"https://example.com/"),[])

if __name__=="__main__":
    unittest.main()
