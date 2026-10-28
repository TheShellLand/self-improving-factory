import json
import unittest
from core.executor import ExecutorCore, SignalPulse
from core.observer import ObserverModule


class TestSignalingContract(unittest.TestCase):
    def test_signal_pulse_initialization(self):
        pulse = SignalPulse()
        self.assertIsInstance(pulse.signal_id, str)
        self.assertIsInstance(pulse.timestamp, float)
        self.assertEqual(json.loads(pulse.to_json())["signal_id"], pulse.signal_id)

    def test_core_blueprints_instantiation(self):
        self.assertEqual(ExecutorCore("/var/run/docker.sock")._registry, {})
        self.assertTrue(ObserverModule().process_telemetry({"signal_id": "123"}))
