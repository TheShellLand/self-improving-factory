"""Check local pi RPC transport without sending a model prompt."""
import asyncio
import time

from core.pi_client import PiClient


class PiTransportCheck:
    async def run(self):
        started = time.monotonic()
        state = await PiClient().perform_action("get_state")
        if not isinstance(state, dict):
            raise RuntimeError("pi returned invalid state")
        print(f"pi RPC state query succeeded in {time.monotonic() - started:.3f}s")


if __name__ == "__main__":
    asyncio.run(PiTransportCheck().run())
