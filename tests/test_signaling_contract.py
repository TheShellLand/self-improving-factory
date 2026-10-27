import unittest
import os
import sys

# Ensure project roots and core components are visible in the import registry
sys.path.append(os.getcwd())

from core.executor import ExecutorCore, SignalPulse
from core.observer import ObserverModule
from core.gatekeeper import GatekeeperVault

class TestSignalingContract(unittest.TestCase):
    def test_signal_pulse_initialization(self):
        """Verify that a pulse correctly initializes with valid types."""
        pulse = SignalPulse()
        self.assertIsInstance(pulse.signal_id, str)
        self.assertIsInstance(pulse.timestamp, float)

    def test_core_blueprints_instantiation(self):
        """Ensure the key architecture components initialize without errors."""
        try:
            executor = ExecutorCore("/var/run/docker.sock")
            observer = ObserverModule()
            gatekeeper = GatekeeperVault("./root/brain")
            
            # Basic logic checks for presence of core descriptors or initialization values
            self.assertEqual(len(executor._registry), 0) # Registry should be empty initially
            print("Blueprint instantiation checks passed.")
        except Exception as e:
             raise ValueError(f"Tests failed with expected initial architecture state but got {e}")

if __name__ == "__main__":
    unittest.main()
