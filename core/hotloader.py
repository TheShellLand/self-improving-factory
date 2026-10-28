"""Apply persisted configuration updates in insertion order."""
import json
import logging
import threading
from copy import deepcopy
from core.database import connect

logger = logging.getLogger(__name__)


class HotLoaderModule:
    def __init__(self, database_path, poll_interval=5):
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.db_path = database_path
        self.poll_interval = poll_interval
        self._active_config = {}
        self._last_update_id = 0
        self._stop_event = threading.Event()

    def get_active_config(self):
        return deepcopy(self._active_config)

    def _fetch_pending_updates(self):
        with connect(self.db_path) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM knowledge_updates WHERE update_id > ? ORDER BY update_id",
                (self._last_update_id,))]

    def sync_once(self):
        applied = 0
        for update in self._fetch_pending_updates():
            weights = json.loads(update["prompt_weights"])
            if not isinstance(weights, dict):
                raise ValueError("Prompt weights must be a JSON object")
            self._active_config.update(weights)
            self._last_update_id = update["update_id"]
            applied += 1
        return applied

    def start_sync_loop(self):
        while not self._stop_event.is_set():
            try:
                self.sync_once()
            except Exception:
                logger.exception("Could not apply knowledge updates")
            self._stop_event.wait(self.poll_interval)

    def stop(self):
        self._stop_event.set()
