from __future__ import annotations

import re


_STORE_PREFIX = re.compile(r"^Mancino Market\s*[-–—]\s*", re.IGNORECASE)


def display_store_name(store_name: str) -> str:
    """Show the store area while retaining the original name as its filter key."""
    return _STORE_PREFIX.sub("", store_name).strip()
