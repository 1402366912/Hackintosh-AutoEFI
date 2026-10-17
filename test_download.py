# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Hackintosh AutoEFI contributors
"""Download integrity and cache tests. No external network requests."""
from pathlib import Path
import hashlib
import io
import tempfile
import unittest
from unittest.mock import patch
import build


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data) if length is None else length)}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name)
        self.data = b'fixture ISO bytes, not a boot image'
        self.sha = hashlib.sha256(self.data).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_download_is_cached_and_offline_reused(self):
        with patch.object(build, 'urlopen', return_value=Response(self.data)) as request:
            first = build.obtain_iso(self.cache, url='https://example.invalid/iso', expected=self.sha)
            self.assertEqual(first.read_bytes(), self.data)
            self.assertEqual(build.obtain_iso(self.cache, expected=self.sha), first)
            self.assertEqual(request.call_count, 1)
        self.assertFalse(list(self.cache.glob('*.part')))

    def test_wrong_hash_does_not_leave_an_installable_iso(self):
        with patch.object(build, 'urlopen', return_value=Response(b'corrupt')):
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                build.obtain_iso(self.cache, expected=self.sha)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_truncated_transfer_is_rejected_and_partial_removed(self):
        with patch.object(build, 'urlopen', return_value=Response(self.data, len(self.data)+10)):
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                build.obtain_iso(self.cache, expected=self.sha)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_existing_corrupt_cache_is_preserved_and_rejected(self):
        target = self.cache/build.ISO_NAME
        target.write_bytes(b'bad cache')
        with patch.object(build, 'urlopen') as request:
            with self.assertRaisesRegex(ValueError, 'Cached ISO SHA256 mismatch'):
                build.obtain_iso(self.cache, expected=self.sha)
            request.assert_not_called()
        self.assertEqual(target.read_bytes(), b'bad cache')

    def test_network_failure_does_not_create_cached_iso(self):
        with patch.object(build, 'urlopen', side_effect=OSError('network unavailable')):
            with self.assertRaisesRegex(OSError, 'network unavailable'):
                build.obtain_iso(self.cache, expected=self.sha)
        self.assertEqual(list(self.cache.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
