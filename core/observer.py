"""Validate and optionally persist internal telemetry."""
from core.signals import SignalPulse


class ObserverModule:
    def __init__(self, vault=None):
        self.vault = vault

    def process_telemetry(self, pulse_data):
        pulse = SignalPulse.model_validate(pulse_data)
        pulse.to_json()
        if self.vault is not None:
            self.vault.record(pulse)
        return True
