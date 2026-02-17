import time


class Scanner:
    def __init__(self, cleanup_seconds: int = 3600):
        self._state = {}
        self.cleanup_seconds = cleanup_seconds

    def process_item(self, item_id, detection_result):
        is_dump = detection_result.get("is_dump", False)
        now = time.time()

        self._cleanup(now)

        prev = self._state.get(item_id, {"in_dump": False, "last_seen": now})
        was_in_dump = prev["in_dump"]

        if is_dump and not was_in_dump:
            self._state[item_id] = {"in_dump": True, "last_seen": now}
            return detection_result

        if not is_dump and was_in_dump:
            self._state[item_id] = {"in_dump": False, "last_seen": now}
            return None

        self._state[item_id] = {"in_dump": is_dump, "last_seen": now}
        return None

    def _cleanup(self, now: float):
        stale_items = [
            item_id
            for item_id, data in self._state.items()
            if now - data["last_seen"] > self.cleanup_seconds
        ]

        for item_id in stale_items:
            del self._state[item_id]
