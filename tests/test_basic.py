"""
Basic tests to verify project setup
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src import __version__  # noqa: E402


class TestBasicSetup(unittest.TestCase):
    """Test basic project setup"""

    def test_version_exists(self) -> None:
        """Test that version is defined"""
        self.assertIsNotNone(__version__)
        self.assertIsInstance(__version__, str)

    def test_version_format(self) -> None:
        """Test that version follows semantic versioning"""
        version_parts = __version__.split(".")
        self.assertEqual(len(version_parts), 3)
        for part in version_parts:
            self.assertTrue(part.isdigit())


if __name__ == "__main__":
    unittest.main()
