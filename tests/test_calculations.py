import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date
import pandas as pd
from utils import cache, data, data_cached, cache_builder


class CalculationTests(unittest.TestCase):
    def test_returns_count_observations_across_holidays(self):
        frame=pd.DataFrame({'Close':[100,101,102,103,104,110]}, index=pd.to_datetime(['2026-09-25','2026-09-28','2026-09-29','2026-09-30','2026-10-08','2026-10-09']))
        self.assertAlmostEqual(.1,data.trailing_return(frame,'2026-10-09',5))
        self.assertTrue(pd.isna(data.trailing_return(frame,'2026-10-09',21)))

    def test_ytd_uses_previous_year_close(self):
        frame=pd.DataFrame({'Close':[100,110,120]},index=pd.to_datetime(['2025-12-31','2026-01-02','2026-01-05']))
        self.assertAlmostEqual(.2,data.trailing_return(frame,'2026-01-05'))
        self.assertTrue(pd.isna(data.trailing_return(frame.iloc[1:],'2026-01-05')))

    def test_cache_builder_uses_actual_csv_date(self):
        cfg={'settings':{'start_date':'2025-01-01','end_date':'2026-12-31','data_root_dir':'missing'}}
        with patch.object(cache_builder,'latest_data_date',return_value=date(2026,9,30)):
            self.assertEqual(date(2026,9,30),cache_builder.default_range(cfg)[1])

    def test_same_end_date_price_correction_invalidates_cache_key(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Path(directory)/'test.csv';f.write_text('Date,Close\n2026-01-01,100\n')
            cfg={'settings':{'data_root_dir':directory},'industries':{}}
            before=data_cached._mk(cfg)
            f.write_text('Date,Close\n2026-01-01,120.5\n')
            self.assertNotEqual(before,data_cached._mk(cfg))
            cfg['industries']={'new':[]}
            self.assertNotEqual(before,data_cached._mk(cfg))

    def test_failed_cache_write_does_not_destroy_previous_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cache,'CACHE_FILE',str(Path(directory)/'cache.pkl')):
            cache._building.clear();cache.record('good',123);cache.flush()
            previous=Path(cache.CACHE_FILE).read_bytes()
            with patch.object(cache.pickle,'dump',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):cache.flush()
            self.assertEqual(previous,Path(cache.CACHE_FILE).read_bytes())
            cache._building.clear()
