import sqlite3
from typing import List, Dict, Any
import json
import logging
import os
import time
import threading

# Setup basic logger for internal feedback loops
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HotLoader")

class HotLoaderModule:
    """Provides dynamic update capabilities for configuration data and prompt weights without container restarts."""
    def __init__(self, database_path: str, poll_interval: int = 5):
        self.db_path = database_path
        self.poll_interval = poll_interval
        # Operational memory state representing current config/weights as injected by Reflection engine.
        self._active_config: Dict[str, Any] = {}
        self._last_timestamp: float = 0.0
        self._stop_event = threading.Event()
        logger.info("Hot Loader Module Initialized.")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_active_config(self) -> Dict[str, Any]:
        """Returns the current hot-injected configuration/weights."""
        return self._active_config

    def start_sync_loop(self):
        """Polls the vault for new knowledge updates and hot-injects them into active runtime handles."""
        logger.info("Hot Loader Sync Loop Starting.")
        while not self._stop_event.is_set():
            new_updates = self._fetch_pending_updates()
            if new_updates:
                for update in new_updates:
                    # Logic to map prompt weights or rules based on updated values from DB 
                    try:
                        # If it's a JSON string, parse it; otherwise assume dict (depending on driver/schema)
                        weights_raw = update['prompt_weights']
                        if isinstance(weights_raw, str):
                            weights = json.loads(weights_raw)
                        else:
                            weights = weights_raw

                        self._active_config.update(weights)
                        logger.info(f"HOT INJECTION SUCCESS - Version:{update['version_number']} Desc:{update['logic_description']}")
                    except Exception as e:
                        logger.error(f"Failed to hot-inject configuration for version {update.get('version_number')}: {e}")

            # Use a sleep strategy that respects the stop event
            time.sleep(self.poll_interval)

    def _fetch_pending_updates(self) -> List[Dict]:
        """Retrieves updates applied since the last sync pass."""
        updates = []
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                query = "SELECT * FROM knowledge_updates WHERE applied_at > ? ORDER BY applied_at ASC"
                cur.execute(query, (self._last_timestamp,))
                rows = cur.fetchall()
                for row in rows:
                    data = dict(row)
                    # Conversion of types if needed based on SQL behavior
                    if 'prompt_weights' in data and isinstance(data['prompt_weights'], str):
                        # We don't parse it here to keep _fetch for pure retrieval; 
                        # the sync loop handles parsing/logic mapping
                        pass
                    
                    updates.append(data)
                    # Update high-water mark timestamp
                    try:
                        ts = float(data['applied_at'])
                        if ts > self._last_timestamp:
                            self._last_timestamp = ts
                    except (ValueError, TypeError):
                        continue

        except Exception as e:
            logger.error(f"Hot Loader fetch error occurred: {e}")
        return updates

    def stop(self):
        """Stops the synchronization thread."""
        self._stop_event.set()


if __name__ == "__main__":
    hotloader = HotLoaderModule("/root/brain/history_vault.db")
    # Example of how it would be run in a production background thread
    # Thread(target=hotloader.start_sync_loop).start()
    print("Hot Loader Module Active.")
