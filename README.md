# Review Load Insights

A small service that answers one question about a public GitHub repo: **who does the code
reviews, and is it slowing pull requests down?**

You give it a repo and a date range. It pulls the merged PRs and their reviews from GitHub,
computes a few review metrics, and can ask an LLM to explain what stands out.

## Running it

You need Python 3.11+ and a GitHub token (read-only access to public repos is enough, create one
at https://github.com/settings/personal-access-tokens). An OpenAI key is optional, it's only
used for the explanation endpoint.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GITHUB_TOKEN=your_token
export OPENAI_API_KEY=your_key
uvicorn app.main:app --reload
```

Then open http://localhost:8000. Note for Mac: the built-in `python3` is 3.9, which is too old,
so install 3.12 from python.org first.

Other options:
- Docker: `docker build -t loop-insights .` then
  `docker run -p 8000:8000 -e GITHUB_TOKEN -e OPENAI_API_KEY loop-insights`
- Tests: `pip install -r requirements-dev.txt`, then `python -m pytest` (no network or keys needed)
- Optional env vars: `OPENAI_MODEL` (default `gpt-5.6`), `DB_PATH` (default `queries.sqlite3`)

## API

```bash
curl 'localhost:8000/v1/repos/fastapi/fastapi/review-load?since=2026-10-01&until=2026-10-07'
curl 'localhost:8000/v1/repos/fastapi/fastapi/review-load/narrative?since=2026-10-01&until=2026-10-07'
curl 'localhost:8000/v1/history'
```

- `/review-load` returns the metrics plus basic repo info (stars, forks, language, link).
- `/review-load/narrative` returns the same metrics plus an LLM summary, a hypothesis, a
  confidence score and the evidence it used.
- `since` / `until` are inclusive UTC dates. If left out, the last 30 days are used.
- `/v1/history` lists past searches, `/healthz` is a health check, `/docs` has the OpenAPI docs.

Errors: `404` repo not found or private, `422` bad repo name or dates, `502` GitHub or OpenAI
failed, `503` rate limited or a key is missing.

## The metric

All numbers are about PRs **merged** in the period:

- `total_reviews`, `top_reviewers`, `top_authors`: who reviews and who ships
- `top_reviewer_share`: share of all reviews done by the busiest reviewer
- `unreviewed_share`: share of PRs merged with no review at all
- `median_hours_to_first_review`, `median_hours_to_merge`: how long PRs wait
- `complete`: false if there were more than 1,000 PRs (GitHub search limit)

Why this one: reviewing is invisible work. If one or two people do most of the reviews, PRs
queue up behind them and nobody else learns that code. Putting "who reviews" next to "how long
PRs wait" lets the service point at a likely cause instead of just showing a leaderboard.

A few details: an author commenting on their own PR doesn't count as a review, draft reviews are
ignored, I use medians because a few stale PRs would wreck an average, and an empty period
returns `null` rather than a fake `0`.

## Architecture

```
app/main.py       endpoints, input checks, cache lookups
app/github.py     GitHub REST calls
app/metrics.py    the math (pure function, tested)
app/narrative.py  OpenAI call + evidence check (tested)
app/db.py         SQLite cache and search history
app/static/       a single HTML page
```

A request is validated, then checked against a SQLite cache (same repo and dates in the last
hour means no GitHub call). On a miss, `github.py` makes one call for repo info, one search call
for PRs merged in the period, and one call per PR for its reviews. `metrics.py` turns that into
the numbers. For the narrative, the LLM only gets the computed numbers as named facts (never PR
text, which anyone can write, so no prompt injection), and has to answer in a fixed structure
via the OpenAI Responses API. Every fact it cites is then checked against our data: made-up
ones are dropped, the value shown is ours, not the model's, and confidence is capped at 0.2 if
nothing checkable is left. Answers are cached too.

Security: tokens only come from env vars and are never logged, repo names are checked against
GitHub's naming rules before being used in a URL or search, SQL is parameterized, and the page
only uses `textContent`.

## Trade-offs

- REST over GraphQL because it's easier to read. The cost is one call per PR for reviews, so a
  busy month can take a while on the first request (the cache helps after that).
- The cache is per exact repo and date range, and lives for an hour.
- The LLM explains the numbers but doesn't browse GitHub itself (e.g. via MCP). That would be
  easy to wire up, but the model would be doing the counting, the evidence couldn't be checked,
  and it would read untrusted PR text.
- Bots count like people, and only the first 100 reviews per PR are read.
- No auth or rate limiting on this API, so it's meant to run locally or on an internal network.

## Extras

The web page (date picker, search history, repo info card with a GitHub link), the SQLite cache
for both GitHub data and LLM answers, tests, a Dockerfile, and a health check.

## What I'd do next

- Store PRs and reviews in their own tables with a background sync, so any date range is
  answered from the database (or switch to GraphQL to cut the number of calls).
- A small eval set for the narrative: fixed inputs with checks to run before changing the
  prompt or the model.
- Weekly trends and an option to filter out bots.
- More tests around input validation and the GitHub client.

## Use of AI

I used an AI coding assistant to build the UI, review and clean up the code, and help write
the backend, then simplified it in several rounds. I made the design decisions and reviewed
everything.
