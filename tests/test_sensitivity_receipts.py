from pathlib import Path
import tempfile
import unittest

from research.src.write_sensitivity_execution import source_sha256_lf


class SourceReceiptTests(unittest.TestCase):
    def test_newline_portability_does_not_ignore_code_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            first=Path(directory)/'first.py';second=Path(directory)/'second.py'
            code=b'def value():\n    return 1\n'
            first.write_bytes(code);second.write_bytes(code.replace(b'\n',b'\r\n'))
            self.assertEqual(source_sha256_lf(first),source_sha256_lf(second))
            second.write_bytes(code.replace(b'return 1',b'return 2'))
            self.assertNotEqual(source_sha256_lf(first),source_sha256_lf(second))
            second.write_bytes(code.replace(b'return 1',b'return 1 '))
            self.assertNotEqual(source_sha256_lf(first),source_sha256_lf(second))
