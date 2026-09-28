"""Download and parse AI news RSS feeds.

Think of this file as the "grocery shopper" of the project: it visits each
feed URL from config.yaml, brings back the raw stories, and hands them over
in one clean, uniform shape so the rest of the pipeline never has to care
which website a story came from.
"""

import re
from datetime import datetime, timezone

import feedparser
import requests

# Some sites block requests that look like scripts. A friendly user agent
# keeps us polite and avoids needless 403 errors.
USER_AGENT = "ai-daily-digest/1.0 (personal learning project)"
REQUEST_TIMEOUT = 20  # seconds; we never wait forever on a slow site


def fetch_feed(url):
    """Download one RSS feed and return the parsed feed.

    Returns None when the feed cannot be downloaded or parsed. Returning
    None (instead of crashing) is deliberate: one broken feed should never
    kill the whole run, because news sites go down all the time.
    """
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # Network error, timeout, 404, 500, ... just warn and move on.
        print(f"  [warn] could not download feed: {url} ({exc})")
        return None

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        # "bozo" is feedparser's funny word for "this feed looked odd".
        # If it still gave us entries we use them; if there are zero
        # entries, the feed is useless to us.
        print(f"  [warn] feed had errors and no entries: {url}")
        return None
    return parsed


def _to_datetime(published_parsed):
    """Convert feedparser's time tuple into a timezone-aware datetime.

    Returns None when the feed did not include a date. We keep such
    stories anyway and treat them as fresh, because silently dropping
    them would lose news for no good reason.
    """
    if not published_parsed:
        return None
    try:
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def extract_items(parsed_feed, source_name):
    """Turn one parsed feed into a list of simple story dicts.

    Every story looks like this:

        {
            "title": "Some AI headline",
            "link": "https://example.com/story",
            "summary": "A paragraph or two of summary text...",
            "published": datetime(...),   # or None when the feed gave no date
            "source": "Hugging Face Blog",
        }

    Uniform dicts like this keep the ranker and the drafter simple: they
    never need to know feedparser exists.
    """
    stories = []
    for entry in parsed_feed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            # A story without a title or a link is useless to us; skip it.
            continue
        # Feeds call the summary field different names; try both.
        summary = entry.get("summary") or entry.get("description") or ""
        published = _to_datetime(
            entry.get("published_parsed") or entry.get("updated_parsed")
        )
        stories.append(
            {
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
                "source": source_name,
            }
        )
    return stories


def fetch_all(feeds):
    """Fetch every feed from the config.

    Returns a tuple (stories, error_count): the combined list of story
    dicts from all feeds that worked, plus how many feeds failed.
    """
    stories = []
    errors = 0
    for feed in feeds:
        name = feed.get("name") or feed.get("url")
        url = feed.get("url")
        print(f"  fetching {name} ...")
        if not url:
            print("  [warn] feed entry has no url, skipping")
            errors += 1
            continue
        parsed = fetch_feed(url)
        if parsed is None:
            errors += 1
            continue
        found = extract_items(parsed, name)
        print(f"    found {len(found)} stories")
        stories.extend(found)
    return stories, errors
