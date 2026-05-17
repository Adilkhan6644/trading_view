from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Dict, List, Tuple

# UTC windows. You can tune these in one place.
SESSION_WINDOWS_UTC: Dict[str, Tuple[time, time]] = {
    "LONDON": (time(7, 0), time(16, 0)),
    "NEW_YORK": (time(12, 0), time(21, 0)),
}


def session_is_open(enabled: bool, sessions: List[str], timezone_name: str = "UTC") -> bool:
    if not enabled:
        return True

    now = datetime.now(timezone.utc).time()

    for session_name in sessions:
        window = SESSION_WINDOWS_UTC.get(session_name.upper())
        if not window:
            continue
        start_time, end_time = window
        if start_time <= now <= end_time:
            return True
    return False
