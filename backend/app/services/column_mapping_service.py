"""Export and import column mapping JSON with diff computation."""
from __future__ import annotations


def compute_diff(
    current: dict[str, str], incoming: dict[str, str]
) -> dict[str, dict]:
    """Return {field: {old, new}} for every key that differs."""
    all_keys = set(current) | set(incoming)
    diff = {}
    for k in all_keys:
        old_val = current.get(k)
        new_val = incoming.get(k)
        if old_val != new_val:
            diff[k] = {"old": old_val, "new": new_val}
    return diff
