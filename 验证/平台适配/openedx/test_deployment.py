import tempfile
from pathlib import Path
import unittest

from collect_versions import prepare_output


class DeploymentOutputTest(unittest.TestCase):
    def test_new_and_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'new'
            self.assertEqual(prepare_output(target), target)
            self.assertEqual(prepare_output(target), target)

    def test_refuse_nonempty_directory_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            marker = target / 'committed.json'
            marker.write_bytes(b'unchanged')
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                prepare_output(target)
            self.assertEqual(marker.read_bytes(), b'unchanged')

    def test_refuse_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'file'
            target.write_bytes(b'unchanged')
            with self.assertRaises(ValueError):
                prepare_output(target)
            self.assertEqual(target.read_bytes(), b'unchanged')


if __name__ == '__main__':
    unittest.main()
