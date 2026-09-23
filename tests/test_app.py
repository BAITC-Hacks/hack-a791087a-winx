"""One reproducible user journey, no layout/snapshot tests and no API calls."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class ApplicationSmokeTest(unittest.TestCase):
    def test_baseline_and_offline_explanation(self):
        root = Path(__file__).resolve().parents[1]
        with patch.dict(os.environ, {"DEMO_MODE": "1", "OPENAI_API_KEY": "", "OPENAI_MODEL": ""}):
            with patch("openai.OpenAI", side_effect=AssertionError("No API in demo")):
                app = AppTest.from_file(str(root / "app.py")).run(timeout=20)
                self.assertFalse(app.exception)
                self.assertEqual(app.title[0].value, "Аким на 5 часов")
                self.assertEqual([metric.value for metric in app.metric], ["100", "52.5577", "2"])
                self.assertEqual(len(app.dataframe[0].value), 5)
                self.assertEqual(len(app.dataframe[1].value), 14)
                app.button[0].click().run(timeout=20)
                self.assertFalse(app.exception)
                self.assertTrue(any("52.5577" in item.value for item in app.markdown))
                self.assertTrue(any("demo" in item.value for item in app.caption))


if __name__ == "__main__":
    unittest.main()
