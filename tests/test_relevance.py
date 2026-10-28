import unittest
from matching import assess,us_eligible

class RelevanceTests(unittest.TestCase):
    def test_broad_title(self):
        self.assertTrue(assess('Analytics Engineer','Building pipelines with dbt')[0])
        self.assertTrue(assess('MLOps Developer','Python deployment')[0])
        self.assertTrue(assess('Data Scientist','Research and models')[0])
    def test_not_every_job(self):
        self.assertFalse(assess('Marketing Manager','We use machine learning')[0])
        self.assertFalse(assess('Staff ML Engineer','Machine learning')[0])
        self.assertFalse(assess('Software Engineer','We are an AI company')[0])
    def test_missing_years_accepted(self):
        self.assertTrue(assess('Data Engineer','Build Spark and SQL pipelines')[0])
    def test_locations(self):
        self.assertTrue(us_eligible('Remote, United States'))
        self.assertTrue(us_eligible('Boston, MA'))
        self.assertFalse(us_eligible('Toronto, Canada','CA'))

if __name__=='__main__':unittest.main()
