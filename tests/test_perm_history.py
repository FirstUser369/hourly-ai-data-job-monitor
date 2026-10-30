import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from openpyxl import Workbook
import perm_history as perm

class PermHistoryTests(unittest.TestCase):
    def test_company_name_variants(self):
        self.assertEqual(perm.normalize("  Example Robotics, LLC "),"EXAMPLE ROBOTICS")
        self.assertEqual(perm.normalize("Example Robotics Inc."),"EXAMPLE ROBOTICS")
        self.assertNotEqual(perm.normalize("Example Robotics Europe"),perm.normalize("Example Robotics"))

    def test_dedup_certifications_and_separate_fiscal_years(self):
        batches=[
            ("FY2024-old",[("Acme LLC","CERTIFIED","P-001","2024-05-01"),
                           ("Acme LLC","DENIED","P-002","2024-05-05")]),
            ("FY2024-new",[("Acme Inc","CERTIFIED","P-001","2024-05-01")]),
            ("FY2025",[("Acme Inc","CERTIFIED","P-003","2025-06-01")]),
            ("FY2026-Q3",[("Other Company","DENIED","P-004","2026-03-01")])]
        index={"employers":perm.aggregate_batches(batches)}
        acme=perm.lookup("Acme Corp",index)
        self.assertEqual(acme["perm_certified_3yr"],2)
        self.assertEqual(acme["perm_cases_3yr"],3)
        self.assertEqual(acme["perm_latest_determination"],"2025-06-01")
        self.assertEqual(perm.lookup("Other Company",index)["perm_certified_3yr"],0)
        self.assertEqual(perm.lookup("Unknown Company",index)["perm_status"],"Unknown")

    def test_missing_case_numbers_not_collapsed(self):
        rows=[("Acme","CERTIFIED","","2024-01-01"),
              ("Acme","CERTIFIED","","2024-01-01")]
        result=perm.aggregate_batches([("FY2024-old",rows)])
        self.assertEqual(result["ACME"]["certified"],2)

    def test_read_excel_disclosure_column_names(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"sample.xlsx"
            book=Workbook()
            tab=book.active
            tab.append(["CASE_NUMBER","EMPLOYER_NAME","CASE_STATUS","DECISION_DATE"])
            tab.append(["A-123","Test Data LLC","Certified","2026-04-15"])
            book.save(path)
            rows=list(perm.records_from_workbook(path))
            self.assertEqual(rows[0],("Test Data LLC","CERTIFIED","A-123","2026-04-15"))

    def test_missing_index_means_unknown(self):
        with TemporaryDirectory() as directory:
            self.assertIsNone(perm.load(Path(directory)/"missing.json.gz"))
            self.assertEqual(perm.lookup("Acme",None)["perm_status"],"Unknown")

    def test_exact_match_not_parent_inference(self):
        index={"employers":{"ALPHA":{"display_name":"Alpha","certified":5,
               "determinations":5,"latest_determination":"2026-01-01"}}}
        self.assertEqual(perm.lookup("Alpha Subsidiary",index)["perm_status"],"Unknown")

if __name__=="__main__":
    unittest.main()
