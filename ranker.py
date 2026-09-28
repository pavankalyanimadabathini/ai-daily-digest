"""Rank stories by how relevant they are to AI.

The idea is simple, like grading a quiz: every time one of your keywords
shows up in a story, the story earns points. A keyword in the headline
counts double, because headlines carry the most signal about what a story
is really about. Newer stories get a small freshness bonus so that when
two stories tie, the fresher one wins.
"""

from datetime import datetime, timezone


def score_item(item, keywords):
    """Score one story against the keyword list. Higher is more relevant."""
    title_text = item["title"].lower()
    summary_text = item["summary"].lower()
    score = 0
    for keyword in keywords:
        keyword = keyword.lower().strip()
        if not keyword:
            continue
        # str.count() counts non-overlapping occurrences of the keyword.
        score += 2 * title_text.count(keyword)
        score += 1 * summary_text.count(keyword)
    return score


def _freshness_bonus(item):
    """Small bonus (2 points) for stories published in the last 48 hours.

    This only breaks ties between equally keyword-relevant stories; it can
    never push an irrelevant story above a relevant one.
    """
    published = item.get("published")
    if published is None:
        return 0
    age = datetime.now(timezone.utc) - published
    if age.total_seconds() < 0:
        # A publish date in the future is probably a feed bug; no bonus,
        # but we still keep the story.
        return 0
    return 2 if age.days < 2 else 0


def rank(items, keywords, max_age_days):
    """Filter out old stories, score the rest, return best-first.

    Returns a new list of story dicts (copies, so the caller's data is
    never modified), each with an extra "score" key, sorted by score
    from highest to lowest. Stories with no usable date are treated as
    fresh rather than dropped.
    """
    now = datetime.now(timezone.utc)
    fresh = []
    for item in items:
        published = item.get("published")
        if published is not None:
            age_days = (now - published).total_seconds() / 86400
            if age_days > max_age_days:
                continue  # too old, skip it
        score = score_item(item, keywords) + _freshness_bonus(item)
        ranked_item = dict(item)  # copy, so we never mutate the original
        ranked_item["score"] = score
        fresh.append(ranked_item)
    # Sort by score first, then by publish date (newest wins ties).
    # min datetime used when a story has no date, so dated stories win ties.
    fresh.sort(
        key=lambda s: (s["score"], s.get("published") or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return fresh
