import unittest
from datetime import datetime, timezone, timedelta
from freshness import published_last_hour, timestamp_class

NOW = datetime(2026,10,28,18,0,tzinfo=timezone.utc)

class FreshnessTests(unittest.TestCase):
    def test_recent_employer_publication(self):
        self.assertTrue(published_last_hour({'ats':'ashby','published':NOW-timedelta(minutes=20)},NOW))
        self.assertTrue(published_last_hour({'ats':'greenhouse','published':NOW-timedelta(minutes=60)},NOW))
        self.assertTrue(published_last_hour({'ats':'smartrecruiters','published':NOW},NOW))
    def test_old_or_future_publications_rejected(self):
        self.assertFalse(published_last_hour({'ats':'ashby','published':NOW-timedelta(minutes=61)},NOW))
        self.assertFalse(published_last_hour({'ats':'ashby','published':NOW+timedelta(seconds=1)},NOW))
    def test_unknown_posting_dates_rejected(self):
        self.assertFalse(published_last_hour({'ats':'lever','published':NOW},NOW))
        self.assertFalse(published_last_hour({'ats':'remoteok','published':NOW},NOW))
        self.assertFalse(published_last_hour({'ats':'greenhouse','published':None},NOW))
        self.assertFalse(published_last_hour({'ats':'ashby','published':NOW.replace(tzinfo=None)},NOW))
    def test_republication_label(self):
        self.assertIn('republication',timestamp_class({'ats':'ashby'}))
