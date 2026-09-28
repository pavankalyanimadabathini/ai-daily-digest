#!/usr/bin/env python3
"""ai-daily-digest: turn the latest AI news into LinkedIn post drafts.

The pipeline, in plain words:

    config.yaml  ->  fetch feeds  ->  drop seen + old stories
                 ->  rank by AI keywords  ->  draft top stories
                 ->  save drafts/ + remember seen URLs

Usage:
    python digest.py [--limit N] [--dry-run] [--with-openai] [--config config.yaml]

Flags:
    --limit N      draft the top N stories (default: 1, one draft a day)
    --dry-run      print what WOULD happen without writing drafts or
                   updating the seen list. Safe to try anytime.
    --with-openai  draft with the OpenAI API using the OPENAI_API_KEY
                   environment variable. Falls back to the built-in
                   template when the key is missing or the call fails.
    --config PATH  use a different config file (default: config.yaml)
"""

import argparse
import os
import sys

import yaml

from drafter import openai_draft, save_draft, template_draft
from fetcher import fetch_all
from ranker import rank
from state import load_seen, save_seen


def parse_args(argv=None):
    """Read the command-line flags. See the module docstring for details."""
    parser = argparse.ArgumentParser(
        description="Turn the latest AI news into LinkedIn post drafts."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="how many top stories to draft (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print drafts without writing files or updating state",
    )
    parser.add_argument(
        "--with-openai",
        action="store_true",
        help="draft with the OpenAI API (needs OPENAI_API_KEY set)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="path to the config file (default: config.yaml)",
    )
    return parser.parse_args(argv)


def load_config(path):
    """Read config.yaml. Exits with a clear message when it is broken."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"error: config file is not valid YAML: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(config, dict) or not config.get("feeds"):
        print("error: config must define a non-empty 'feeds' list", file=sys.stderr)
        sys.exit(1)
    return config


def main(argv=None):
    args = parse_args(argv)
    if args.limit < 1:
        print("error: --limit must be at least 1", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    settings = config.get("settings", {}) or {}
    state_file = settings.get("state_file", "state/seen.json")
    drafts_dir = settings.get("drafts_dir", "drafts")
    max_age_days = settings.get("max_age_days", 7)
    keywords = config.get("keywords", []) or []

    print("Step 1/4: fetching feeds ...")
    stories, errors = fetch_all(config["feeds"])
    print(f"  collected {len(stories)} stories ({errors} feeds failed)")

    print("Step 2/4: dropping stories already seen ...")
    seen = load_seen(state_file)
    new_stories = [s for s in stories if s["link"] not in seen]
    print(f"  {len(new_stories)} new stories ({len(stories) - len(new_stories)} already seen)")

    print("Step 3/4: ranking by AI-keyword relevance ...")
    ranked = rank(new_stories, keywords, max_age_days)
    print(f"  {len(ranked)} stories after age filtering")
    top = ranked[: args.limit]
    for item in top:
        print(f"  [score {item['score']}] {item['title'][:80]}")

    if not top:
        print("No fresh stories to draft. Nothing to do.")
        return 0

    # Decide how to draft: OpenAI when asked AND a key is available,
    # otherwise the built-in template (which needs nothing).
    use_openai = False
    api_key = None
    if args.with_openai:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            use_openai = True
        else:
            print("  [warn] --with-openai given but OPENAI_API_KEY is not set; using template.")

    print("Step 4/4: drafting ...")
    drafted = 0
    for item in top:
        if use_openai:
            text = openai_draft(item, api_key)
        else:
            text = template_draft(item)
        if args.dry_run:
            print()
            print("=" * 60)
            print(f"DRAFT (not saved, dry run): {item['title'][:70]}")
            print("=" * 60)
            print(text)
        else:
            path = save_draft(drafts_dir, item, text)
            print(f"  saved {path}")
            drafted += 1

    if args.dry_run:
        print()
        print(f"Dry run complete: would have drafted {len(top)} stories. "
              "No files written, seen list untouched.")
    else:
        # Remember every new story we looked at, not just the drafted ones,
        # so tomorrow's run only considers genuinely fresh stories.
        seen.update(s["link"] for s in new_stories)
        save_seen(state_file, seen)
        print(f"Done: drafted {drafted} stories, remembered {len(new_stories)} seen URLs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
