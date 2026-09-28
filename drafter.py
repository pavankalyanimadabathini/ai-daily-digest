"""Turn a top story into a LinkedIn-style post draft.

Two ways to draft:

1. Template mode (default): fills in a hand-written template. Needs zero
   API keys, costs nothing, and always works. The template rotates through
   a few opening lines and takes so drafts do not all sound identical.

2. OpenAI mode (--with-openai): asks the OpenAI API to write the draft,
   with strict style rules in the prompt. If the API call fails for any
   reason, we quietly fall back to the template so the run still succeeds.

House style, enforced in both modes:
- Conversational and human-sounding, like a person wrote it.
- No em dashes anywhere (we scrub them out of feed text too).
- 2 to 4 tasteful emojis, placed naturally at the ends of lines,
  never replacing words in the middle of a sentence.
"""

import html
import os
import re
from datetime import datetime

import requests

_TAG_RE = re.compile(r"<[^>]+>")        # matches <p>, <a href=...>, etc.
_WHITESPACE_RE = re.compile(r"\s+")     # matches any run of whitespace
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")  # splits after . ! or ?
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")

# A few interchangeable parts so consecutive drafts do not read like
# copies of each other. We pick one based on the story title, which keeps
# the choice stable: the same story always gets the same draft.
HOOKS = [
    "This one caught my eye this morning 👀",
    "Worth slowing down for today 📰",
    "AI moves fast. Stories like this are why I keep a daily reading habit 🧠",
]

TAKES = [
    "What stands out to me is how quickly the practical side of AI is moving from demo to daily use.",
    "The pattern I keep seeing: the teams shipping real value are the ones pairing new models with boring, solid engineering.",
    "My take: the headline matters less than what it signals about where the tooling is headed.",
]


def clean_text(raw):
    """Turn messy feed HTML into plain readable text.

    Feeds often hand us HTML with entities like &amp; and stray tags.
    Steps here: remove tags, convert entities back to normal characters
    (&amp; becomes &), replace em/en dashes with a comma or hyphen
    (house style: no em dashes), and collapse extra whitespace.
    """
    text = _TAG_RE.sub(" ", raw or "")
    text = html.unescape(text)
    text = text.replace("—", ",").replace("–", "-")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def short_summary(summary, max_chars=420):
    """Boil a summary down to its first two sentences, capped by length.

    Two sentences are enough for a LinkedIn post: the reader gets the
    gist, and the link is there for the full story. If the text is still
    too long, we trim it at a word boundary and add an ellipsis.
    """
    sentences = [s.strip() for s in _SENTENCE_RE.split(summary) if s.strip()]
    text = " ".join(sentences[:2]).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "..."
    return text


def _pick(options, seed):
    """Pick one option deterministically from a seed string.

    Using hash() of the title means the same story always picks the same
    hook and take, so re-running the tool never shuffles old drafts.
    """
    return options[abs(hash(seed)) % len(options)]


def template_draft(story):
    """Build a LinkedIn draft from the template. No API keys needed."""
    title = clean_text(story["title"])
    blurb = short_summary(clean_text(story["summary"]))
    hook = _pick(HOOKS, title)
    take = _pick(TAKES, title + "|take")

    lines = [
        hook,
        "",
        f'"{title}" ({story["source"]})',
        "",
        blurb,
        "",
        take,
        "",
        "Worth a read if AI is anywhere near your work 💡",
        "",
        f"Link: {story['link']}",
        "",
        "#AI #MachineLearning #Tech 📈",
    ]
    return "\n".join(lines)


def openai_draft(story, api_key):
    """Draft with the OpenAI API, falling back to the template on error.

    The system prompt carries our house style rules so the model writes
    the way we want. Any failure (no network, bad key, rate limit, ...)
    falls back to template_draft: a slightly plainer draft beats no draft.
    """
    system = (
        "You write LinkedIn post drafts. Rules: conversational and "
        "human-sounding, like a real person wrote it. Never use em dashes. "
        "Use 2 to 4 tasteful emojis placed naturally at the ends of "
        "sentences, never replacing words mid-sentence. Slightly fuller "
        "content, about 120 to 200 words. End with 2 or 3 hashtags. "
        "Do not invent facts beyond the story given."
    )
    user = (
        f"Title: {story['title']}\n"
        f"Source: {story['source']}\n"
        f"Summary: {clean_text(story['summary'])}\n"
        f"Link: {story['link']}"
    )
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        # Enforce the house style even on model output: scrub any em
        # dashes the model may have slipped in.
        return clean_text(text)
    except Exception as exc:  # noqa: BLE001 - any failure means fallback
        print(f"  [warn] OpenAI drafting failed ({exc}); using template instead.")
        return template_draft(story)


def slugify(title, max_len=50):
    """Turn a headline into a file-name-friendly slug.

    Lowercase, non-alphanumeric runs become single hyphens, capped at
    max_len characters. Guaranteed non-empty so we never get ".md".
    """
    slug = _NON_SLUG_RE.sub("-", title.lower()).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "story"


def save_draft(drafts_dir, story, text):
    """Save the draft as a markdown file. Returns the file path.

    File names look like drafts/2026-09-27_openai-releases-new-model.md.
    If that name is taken, we append -2, -3, ... so nothing is overwritten.
    """
    os.makedirs(drafts_dir, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    base = f"{date}_{slugify(story['title'])}"
    path = os.path.join(drafts_dir, base + ".md")
    counter = 2
    while os.path.exists(path):
        path = os.path.join(drafts_dir, f"{base}-{counter}.md")
        counter += 1

    header = (
        f"Story: {clean_text(story['title'])}\n"
        f"Source: {story['source']}\n"
        f"Link: {story['link']}\n"
        f"\n"
        f"---\n"
        f"\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + text + "\n")
    return path
