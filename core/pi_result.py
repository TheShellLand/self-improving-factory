"""Validate model output without applying or trusting proposed code."""
import json
from pathlib import PurePosixPath, PureWindowsPath

from core.coordinator import ExecutionOutcome


class PiResultParser:
    @staticmethod
    def _object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    @staticmethod
    def _constant(value):
        raise ValueError("Non-finite JSON number")

    def parse(self, text):
        """Require one JSON object; never guess JSON from prose or code fences."""
        data = json.loads(text, object_pairs_hook=self._object, parse_constant=self._constant)
        # Also reject numeric overflow (for example 1e999 in observations).
        json.dumps(data, allow_nan=False)
        outcome = ExecutionOutcome.model_validate(data, strict=True)
        if not outcome.summary.strip():
            raise ValueError("A nonempty result summary is required")
        if outcome.file_changes and (not outcome.success or not outcome.commit_message.strip()):
            raise ValueError("File proposals require success and a commit message")
        paths = set()
        for change in outcome.file_changes:
            name = change.filename
            path = PurePosixPath(name)
            if (not name.strip() or "\\" in name or "\x00" in name
                    or path.is_absolute() or PureWindowsPath(name).drive
                    or any(part in ("", ".", "..") for part in name.split("/"))
                    or any(part.casefold() == ".git" for part in path.parts)):
                raise ValueError("Invalid proposal path")
            key = name.casefold()
            if any(key == other or key.startswith(other + "/") or other.startswith(key + "/")
                   for other in paths):
                raise ValueError("Duplicate or overlapping proposal paths")
            paths.add(key)
        return outcome
