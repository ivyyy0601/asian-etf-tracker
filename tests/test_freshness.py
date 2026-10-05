import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from utils import config
from refresh_emerging import build_roster, refresh


class FreshnessTests(unittest.TestCase):
    def test_config_changes_are_visible_without_cache_clear(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'roster.json'
            with patch.object(config, 'EMERGING_CONFIG_FILE', str(path)), patch.object(config, 'CONFIG_FILES', {'Market': str(path)}):
                path.write_text('{"industries": {"old": []}}')
                self.assertIn('old', config.load_emerging_config()['industries'])
                self.assertIn('old', config.load_all_configs()['Market']['industries'])
                path.write_text('{"industries": {"new_industry": []}}')
                self.assertIn('new_industry', config.load_emerging_config()['industries'])
                self.assertIn('new_industry', config.load_all_configs()['Market']['industries'])
                path.unlink()
                self.assertIsNone(config.load_emerging_config())
                self.assertEqual({}, config.load_all_configs())

    def test_older_file_update_invalidates_latest_date(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a.csv', Path(d)/'b.csv'
            a.write_text('Date,Close\n2026-01-01,1\n')
            b.write_text('Date,Close\n2026-01-02,1\n')
            os.utime(b, (2000000000, 2000000000))
            self.assertEqual(date(2026,1,2), config.latest_data_date(d))
            a.write_text('Date,Close\n2026-01-03,1\n')
            self.assertEqual(date(2026,1,3), config.latest_data_date(d))

    def payload(self):
        return {'pageHelp': {'total': 100}, 'result': [dict(FUND_CODE=str(510000+i), CATEGORY='F112',
             LISTING_DATE='2025-01-01', SCALE='10', FUND_ABBR='Test', INDEX_NAME='Index') for i in range(100)]}

    def test_roster_selection_units_and_classification(self):
        payload = self.payload()
        payload['result'][0]['SCALE'] = '9.99'
        payload['result'][1]['LISTING_DATE'] = '2024-12-31'
        payload['result'][2]['CATEGORY'] = 'F211'
        payload['result'][3]['LISTING_DATE'] = '2027-01-01'
        old = {'industries': {'existing': [{'code': '510004'}]}}
        result = build_roster(payload, old, datetime(2026,10,5,tzinfo=timezone.utc))
        self.assertEqual(1.0, result['industries']['existing'][0]['scale_billion_cny'])
        self.assertEqual(96, sum(map(len, result['industries'].values())))
        self.assertEqual(95, len(result['industries']['unclassified']))
        self.assertIsNone(result['scale_as_of'])

    def test_failure_preserves_roster_and_success_is_monthly(self):
        with tempfile.TemporaryDirectory() as d:
            path, status = Path(d)/'roster.json', Path(d)/'status.json'
            initial = '{"industries": {"old": [{"code": "510004"}]}}'
            path.write_text(initial)
            now = datetime(2026,10,5,tzinfo=timezone.utc)
            bad = self.payload(); bad['result'].pop()
            self.assertFalse(refresh(path, status, fetch=lambda: bad, now=now))
            self.assertEqual(initial, path.read_text())
            self.assertEqual('failed', json.loads(status.read_text())['status'])
            self.assertTrue(refresh(path, status, fetch=self.payload, now=now))
            self.assertTrue(list((Path(d)/'roster_backups').glob('*.json')))
            self.assertTrue(refresh(path, status, fetch=lambda: self.fail('should skip'), now=now))


if __name__ == '__main__':
    unittest.main()
