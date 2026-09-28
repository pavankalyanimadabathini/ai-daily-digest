"""Remember which stories we already saw.

This is the project's little notebook: a tiny JSON file holding the URLs
of every story we have already processed. Before drafting, we check each
story's URL against this notebook so we never write a second draft about
the same story. The file is created automatically on the first real run.
"""

import json
import os


def load_seen(path):
    """Return the set of already-seen URLs.

    Returns an empty set when the file does not exist yet (first run) or
    when it is corrupted. A corrupted notebook is treated as empty rather
    than crashing the program; the worst case is one duplicate draft.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        return set()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def save_seen(path, seen):
    """Write the seen URLs back to disk, sorted so the file is readable."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)
