import logging
import os

import httpx
from fastapi import HTTPException

API_URL = "https://api.github.com"
log = logging.getLogger(__name__)

MAX_PAGES = 10  # search returns at most 1000 results (10 pages of 100)

NOT_FOUND = "Repository not found. Check the name, or it may be private (only public repos can be read)."


def get_repo_info(owner, repo):
    with _client() as client:
        r = _get(client, f"/repos/{owner}/{repo}", {})
    return {
        "full_name": r["full_name"],
        "description": r["description"],
        "url": r["html_url"],
        "stars": r["stargazers_count"],
        "forks": r["forks_count"],
        "open_issues_and_prs": r["open_issues_count"],  # GitHub counts open PRs as issues here
        "language": r["language"],
        "created_at": r["created_at"],
        "last_push": r["pushed_at"],
        "archived": r["archived"],
    }


def get_merged_prs(owner, repo, since, until):
    with _client() as client:
        query = f"repo:{owner}/{repo} is:pr is:merged merged:{since}..{until}"
        items = []
        for page in range(1, MAX_PAGES + 1):
            data = _get(client, "/search/issues", {"q": query, "per_page": 100, "page": page})
            items += data["items"]
            if not data["items"] or len(items) >= data["total_count"]:
                break

        prs = []
        for item in items:
            reviews = _get(client, f"/repos/{owner}/{repo}/pulls/{item['number']}/reviews", {"per_page": 100})
            prs.append({
                "author": item["user"]["login"] if item["user"] else "ghost",
                "created_at": item["created_at"],
                # a merged PR is closed at the moment it is merged, so closed_at is a safe fallback
                "merged_at": item["pull_request"].get("merged_at") or item["closed_at"],
                "reviews": [
                    {"author": r["user"]["login"], "state": r["state"], "submitted_at": r["submitted_at"]}
                    for r in reviews
                    if r["user"] and r["state"] != "PENDING"
                ],
            })

    return {"prs": prs, "complete": len(items) >= data["total_count"]}


def _client():
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
    return httpx.Client(base_url=API_URL, headers=headers, timeout=20)


def _get(client, path, params):
    try:
        resp = client.get(path, params=params)
    except httpx.HTTPError as e:
        log.warning("GitHub request %s failed: %s", path, type(e).__name__)
        raise HTTPException(502, "Could not reach GitHub")
    # GitHub answers 404 (and search answers 422) for repos that don't exist or are private
    if resp.status_code in (404, 422):
        raise HTTPException(404, NOT_FOUND)
    if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
        raise HTTPException(503, "GitHub rate limit reached, try again in a few minutes")
    if resp.status_code != 200:
        log.warning("GitHub returned HTTP %s for %s", resp.status_code, path)
        raise HTTPException(502, f"GitHub returned HTTP {resp.status_code}")
    return resp.json()
