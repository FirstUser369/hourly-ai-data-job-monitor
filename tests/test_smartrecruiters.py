import unittest
from unittest.mock import patch
import monitor

class SmartRecruitersTests(unittest.TestCase):
    def test_detail_job_description_and_public_url(self):
        listing={'content':[{'id':'744000100','name':'Applied AI Engineer','location':{'city':'Boston','country':'us'}}]}
        detail={'id':'744000100','name':'Applied AI Engineer','location':{'city':'Boston','region':'Massachusetts','country':'us'},
                'applyUrl':'https://jobs.smartrecruiters.com/Vericast/744000100-applied-ai-engineer',
                'releasedDate':'2026-10-28T10:00:00Z',
                'jobAd':{'sections':{'jobDescription':{'text':'<p>Build RAG pipelines with Python.</p>'},
                                     'qualifications':{'text':'<p>3 years experience</p>'}}}}
        with patch.object(monitor,'get',side_effect=[listing,detail]) as mocked:
            jobs=list(monitor.fetch({'ats':'smartrecruiters','slug':'Vericast','company':'Vericast'}))
        self.assertEqual(len(jobs),1)
        self.assertIn('RAG pipelines',jobs[0]['description'])
        self.assertTrue(monitor.eligible(jobs[0]))
        self.assertTrue(jobs[0]['url'].startswith('https://jobs.smartrecruiters.com/'))
        self.assertEqual(mocked.call_count,2)

if __name__=='__main__': unittest.main()
