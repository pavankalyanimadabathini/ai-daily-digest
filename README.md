# ai-daily-digest

Turn the latest AI news into LinkedIn post drafts, automatically, every day.

This is a small Python pipeline for anyone who posts about AI regularly: it
reads a list of AI news RSS feeds, picks the most relevant fresh stories,
and drafts a human-sounding LinkedIn post for each top story. It works with
zero API keys out of the box (template-based drafting), and can optionally
use the OpenAI API for smarter drafts.

## How it works

```
config.yaml
    |
    v
[1. FETCH]   fetcher.py   -- download every RSS feed, parse stories
    |
    v
[2. DEDUPE]  state.py     -- drop stories whose URL is in state/seen.json
    |
    v
[3. RANK]    ranker.py    -- score by AI-keyword hits (title counts double)
    |                        + small freshness bonus, drop stories older
    |                        than max_age_days
    v
[4. DRAFT]   drafter.py   -- template draft (or OpenAI), saved to drafts/
    |
    v
drafts/2026-09-27_some-story-slug.md  +  state/seen.json updated
```

Each module does exactly one job, so the code is easy to read and change.
Every file is heavily commented in plain language.

## Quickstart

```bash
git clone https://github.com/pavankalyanimadabathini/ai-daily-digest.git
cd ai-daily-digest
pip install -r requirements.txt

# See what it would do, without writing anything:
python digest.py --dry-run --limit 3

# Draft today's top story for real:
python digest.py --limit 1
```

Flags:

| Flag | What it does |
| ---- | ------------ |
| `--limit N` | Draft the top N stories (default: 1, one post a day) |
| `--dry-run` | Print drafts without writing files or touching the seen list |
| `--with-openai` | Draft with the OpenAI API (needs `OPENAI_API_KEY` set); falls back to the template on any error |
| `--config PATH` | Use a different config file (default: `config.yaml`) |

## Example output

Real output from a `--dry-run` (The Decoder, September 2026):

```
Worth slowing down for today 📰

"AI agents do more of the work in model development, but humans still make the decisions" (The Decoder)

A research team analyzed 769 task logs from building its own AI model. AI agents
supplied up to 55 percent of method proposals, but humans made more than
85 percent of final decisions.

The pattern I keep seeing: the teams shipping real value are the ones pairing
new models with boring, solid engineering.

Worth a read if AI is anywhere near your work 💡

Link: https://the-decoder.com/ai-agents-do-more-of-the-work-in-model-development-but-humans-still-make-the-decisions/

#AI #MachineLearning #Tech 📈
```

Drafts are saved as markdown files under `drafts/`, named by date and story
slug, for example `drafts/2026-09-27_ai-agents-do-more-of-the-work-in-model-development.md`.
Each file starts with the story title, source, and link, then the draft text.

House style for every draft: conversational and human-sounding, no em dashes,
2 to 4 tasteful emojis placed naturally, slightly fuller content, hashtags at
the end.

## Scheduling

**Option A: cron (your own machine or a server)**

```cron
# Every day at 6:00 AM Phoenix time, draft one post
0 6 * * * cd /path/to/ai-daily-digest && /usr/bin/python3 digest.py --limit 1
```

**Option B: GitHub Actions (free, no server needed)**

This repo ships with `.github/workflows/daily-digest.yml`. Once pushed to
GitHub, it runs every morning at 6:00 AM Phoenix time, drafts one post, and
commits the new file in `drafts/` back to the repo. You can also trigger it
manually from the Actions tab. No secrets are required unless you enable
`--with-openai` (then add `OPENAI_API_KEY` as a repository secret and pass
the flag in the workflow).

## Customizing

- **Feeds:** edit the `feeds` list in `config.yaml`. Every URL there was
  verified to return real RSS; if you add one, test it first with
  `curl -sL -A "Mozilla/5.0" "URL" | head -c 500` and look for RSS/XML tags.
- **Keywords:** edit the `keywords` list in `config.yaml` to match the AI
  topics you care about. Title matches count double.
- **Freshness window:** `settings.max_age_days` controls how old a story can
  be and still qualify (default: 7).
- **Draft style:** tweak the `HOOKS` and `TAKES` lists in `drafter.py`, or
  rewrite `template_draft()` entirely. The OpenAI system prompt in
  `openai_draft()` carries the same style rules.

## Project structure

```
ai-daily-digest/
  digest.py                 CLI entry point (the file you run)
  fetcher.py                downloads + parses RSS feeds
  ranker.py                 scores and sorts stories by keyword relevance
  drafter.py                template + OpenAI drafting, draft file writing
  state.py                  remembers seen URLs in state/seen.json
  config.yaml               feeds, keywords, settings
  requirements.txt          feedparser, pyyaml, requests
  drafts/                   generated LinkedIn drafts (markdown)
  state/                    seen-URL notebook (gitignored, auto-created)
  .github/workflows/        daily-digest.yml: free daily scheduling
```

## Requirements

- Python 3.10+
- `pip install -r requirements.txt`

## License

MIT. See [LICENSE](LICENSE).
