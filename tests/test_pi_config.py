import os
import unittest
from unittest.mock import patch

from core.config import PiAgentConfig


class TestPiAgentConfig(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_defaults(self):
        config = PiAgentConfig()
        self.assertEqual(config.executable, "pi")
        self.assertEqual(config.max_events, 10000)
        self.assertIsNone(config.model)
        self.assertIsNone(config.provider)
        self.assertEqual((config.timeout, config.cleanup_timeout, config.max_record_bytes),
                         (120, 5, 1048576))
        self.assertNotIn("--model", config.argv())
        self.assertNotIn("--provider", config.argv())

    @patch.dict(os.environ, {"SIFH_PI_EXECUTABLE": "/path with spaces/pi",
                            "SIFH_MODEL": "false", "SIFH_PROVIDER": "true",
                            "SIFH_TIMEOUT": "12.5", "SIFH_PI_CLEANUP_TIMEOUT": "2.5",
                            "SIFH_PI_MAX_RECORD_BYTES": "2048"}, clear=True)
    def test_environment_and_overrides(self):
        config = PiAgentConfig()
        self.assertEqual(config.argv()[0], "/path with spaces/pi")
        self.assertEqual(config.argv()[-4:], ["--provider", "true", "--model", "false"])
        self.assertEqual((config.timeout, config.cleanup_timeout, config.max_record_bytes),
                         (12.5, 2.5, 2048))
        config = PiAgentConfig("other", "model", "provider", 3, 1, 512)
        self.assertEqual(config.argv()[0], "other")
        self.assertEqual(config.argv()[-4:], ["--provider", "provider", "--model", "model"])
        self.assertEqual((config.timeout, config.cleanup_timeout, config.max_record_bytes),
                         (3, 1, 512))

    @patch.dict(os.environ, {}, clear=True)
    def test_invalid_settings_fail_before_launch(self):
        cases = {
            "executable": ("", " ", True, "pi\0"),
            "model": ("", " ", False, "model\0"),
            "provider": ("", " ", 1, "provider\0"),
            "timeout": (True, 0, -1, "nan", "inf", "bad"),
            "cleanup_timeout": (True, 0, -1, "nan", "inf", "bad"),
            "max_record_bytes": (True, 0, -1, 1.5, "1.5", "inf"),
            "max_events": (True, 0, -1, 1.5, "1.5", "inf", ""),
        }
        for setting, values in cases.items():
            for value in values:
                with self.subTest(setting=setting, value=value), self.assertRaises(ValueError):
                    PiAgentConfig(**{setting: value})
        for name in ("SIFH_PI_EXECUTABLE", "SIFH_MODEL", "SIFH_PROVIDER", "SIFH_TIMEOUT",
                     "SIFH_PI_CLEANUP_TIMEOUT", "SIFH_PI_MAX_RECORD_BYTES"):
            with self.subTest(name=name), patch.dict(os.environ, {name: ""}):
                with self.assertRaises(ValueError):
                    PiAgentConfig()

    @patch.dict(os.environ, {"OPENAI_API_KEY": " 'exact secret' "}, clear=True)
    def test_credentials_are_exact_and_never_arguments(self):
        config = PiAgentConfig()
        environment = config.environment()
        self.assertEqual(environment["OPENAI_API_KEY"], " 'exact secret' ")
        self.assertNotIn(" 'exact secret' ", config.argv())
        environment["OPENAI_API_KEY"] = "changed"
        self.assertEqual(config.environment()["OPENAI_API_KEY"], " 'exact secret' ")

    @patch.dict(os.environ, {"SIFH_PI_MAX_EVENTS": "12"}, clear=True)
    def test_event_limit_environment_and_override(self):
        self.assertEqual(PiAgentConfig().max_events, 12)
        self.assertEqual(PiAgentConfig(max_events=2).max_events, 2)
