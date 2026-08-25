from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from cpr_contract import PRICE_ADJUSTMENT_POLICY
from nse_cpr_scanner import (
    download_bhavcopy,
    read_bhavcopy_manifest,
    write_bhavcopy_manifest,
)


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"SYMBOL,OPEN,HIGH,LOW,CLOSE\nAAA,1,2,0.5,1.5\n"):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(response=self)


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        return FakeResponse(503 if self.calls < 3 else 200)


class ActionableHardeningTests(unittest.TestCase):
    def test_download_retries_transient_server_error(self):
        session = FakeSession()
        frame = download_bhavcopy("https://example.test/{date}.csv", "20260813", session=session, retries=2, backoff_seconds=0)
        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(session.calls, 3)

    def test_cache_manifest_records_incompleteness_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_bhavcopy_manifest(
                end_date="20260813",
                requested_sessions=3,
                cached_dates=["20260813", "20260812"],
                attempted_dates=["20260813", "20260812", "20260811"],
                output_dir=output,
            )
            manifest = read_bhavcopy_manifest(output)
            self.assertFalse(manifest["complete"])
            self.assertEqual(manifest["missing_dates"], ["20260811"])
            self.assertEqual(manifest["price_adjustment_policy"], PRICE_ADJUSTMENT_POLICY)


if __name__ == "__main__":
    unittest.main()
