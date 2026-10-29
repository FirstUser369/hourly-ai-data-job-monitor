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
    def test_experience_priority_and_limit(self):
        rank=lambda desc: assess('Data Engineer',desc)
        top=rank('Requires 3 years of experience building Spark pipelines')
        also_top=rank('Requires 4+ years experience with SQL')
        junior=rank('Requires 2 years experience')
        five=rank('Requires 5+ years of experience')
        unknown=rank('Build data pipelines with SQL')
        self.assertTrue(all(x[0] for x in (top,also_top,junior,five,unknown)))
        self.assertGreater(top[1],junior[1])
        self.assertGreater(also_top[1],five[1])
        self.assertGreater(junior[1],five[1])
        self.assertIn('not specified',unknown[2][-1])
    def test_exclude_six_years_or_more_anywhere(self):
        for desc in ('6 years experience','6+ years of experience','8 years experience',
                     '3 to 6 years of relevant experience','2–7 years professional experience',
                     '3 years of experience and 10 years working with data'):
            with self.subTest(desc=desc):
                self.assertFalse(assess('Machine Learning Engineer',desc)[0])
    def test_range_three_to_four_is_highest(self):
        result=assess('AI Engineer','Requires 3–4 years of experience')
        self.assertTrue(result[0])
        self.assertTrue(any('highest priority' in x for x in result[2]))
    def test_locations(self):
        self.assertTrue(us_eligible('Remote, United States'))
        self.assertTrue(us_eligible('Boston, MA'))
        self.assertFalse(us_eligible('Toronto, Canada','CA'))

if __name__=='__main__':unittest.main()
