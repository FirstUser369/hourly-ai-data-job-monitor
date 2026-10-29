import unittest
from unittest.mock import Mock,patch
import fortune500_registry as f
from career_discovery import career_links, missing_fortune_ranks

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
    def test_two_missing_domains_keep_entire_fortune_roster(self):
        csv_rows=["rank,company,domain"]
        for i in range(1,501):
            domain="" if i in (177,499) else "company"+str(i)+".example"
            csv_rows.append(str(i)+",Example "+str(i)+","+domain)
        response=Mock(content=("\n".join(csv_rows)+"\n").encode())
        session=Mock()
        session.get.return_value=response
        rows=f.load_fortune500(session)
        self.assertEqual(len(rows),500)
        self.assertEqual(sum(not x["url"] for x in rows),2)
        self.assertEqual(rows[176]["domain_status"],"missing_or_invalid")
        self.assertEqual(rows[498]["domain_status"],"missing_or_invalid")
        self.assertEqual(rows[0]["domain_status"],"available")
    def test_partial_source_preserves_available_ranks(self):
        response=Mock(content=b"rank,company,domain\n1,Company,example.com\n")
        session=Mock()
        session.get.return_value=response
        rows=f.load_fortune500(session)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["fortune_rank"],1)
    def test_duplicate_rank_prefers_usable_homepage(self):
        csv_rows=["rank,company,domain"]
        for i in range(1,501):
            csv_rows.append(str(i)+",Employer "+str(i)+",company"+str(i)+".example")
        csv_rows.append("160,Employer 160,")
        response=Mock(content=("\n".join(csv_rows)+"\n").encode())
        session=Mock()
        session.get.return_value=response
        rows=f.load_fortune500(session)
        self.assertEqual(len(rows),500)
        self.assertEqual(rows[159]["url"],"https://company160.example/")
    def test_missing_rank_is_not_fabricated(self):
        lines=["rank,company,domain"]
        for i in range(1,501):
            if i==333:
                continue
            lines.append(str(i)+",Employer "+str(i)+",company"+str(i)+".example")
        response=Mock(content=("\n".join(lines)+"\n").encode())
        session=Mock()
        session.get.return_value=response
        rows=f.load_fortune500(session)
        self.assertEqual(len(rows),499)
        self.assertNotIn(333,[x["fortune_rank"] for x in rows])
    def test_missing_rank_reporting_with_duplicate_rank_source(self):
        records=[{"fortune_rank":i} for i in range(1,501) if i!=160]
        records.append({"fortune_rank":159})
        self.assertEqual(missing_fortune_ranks(records),[160])
        self.assertEqual(missing_fortune_ranks([]),list(range(1,501)))
        self.assertEqual(missing_fortune_ranks([{"fortune_rank":i} for i in range(1,501)]),[])

    def test_career_anchor_discovery(self):
        html='<a href="/careers/">Careers</a><a href="/products">Products</a><a href="https://unrelated.example/jobs">jobs</a>'
        self.assertEqual(career_links(html,"https://example.com/"),["https://example.com/careers/"])
    def test_no_fabricated_career_link(self):
        self.assertEqual(career_links('<p>No careers link</p>',"https://example.com/"),[])

if __name__=="__main__":
    unittest.main()
