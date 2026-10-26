import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path as FilePath

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import FileResponse

from app import db, github, metrics, narrative

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Review Load Insights")

Owner = Path(pattern=r"^[A-Za-z0-9-]{1,39}$")
Repo = Path(pattern=r"^[A-Za-z0-9._-]{1,100}$")


def build_report(owner, repo, since, until):
    if not os.environ.get("GITHUB_TOKEN"):
        raise HTTPException(503, "GITHUB_TOKEN is not set - see README")

    today = datetime.now(timezone.utc).date()
    if until is None:
        until = today
    if since is None:
        since = until - timedelta(days=29)  # last 30 days

    if since > until:
        raise HTTPException(422, "'since' must be on or before 'until'")
    if until > today:
        raise HTTPException(422, "'until' cannot be in the future")
    if (until - since).days > 365:
        raise HTTPException(422, "The period cannot be longer than one year")

    # same repo + dates asked in the last hour? use the saved data instead of calling GitHub
    name = f"{owner}/{repo}".lower()
    data = db.find(name, since, until)
    if data is None:
        repo_info = github.get_repo_info(owner, repo)  # also gives a clean 404 for unknown or private repos
        data = github.get_merged_prs(owner, repo, since, until)
        data["repo_info"] = repo_info
        db.save(name, since, until, data)

    report = {
        "repo": f"{owner}/{repo}",
        "since": since,
        "until": until,
        "complete": data["complete"],
        "repo_info": data.get("repo_info"),
    }
    report.update(metrics.compute(data["prs"]))
    return report


@app.get("/v1/repos/{owner}/{repo}/review-load")
def review_load(owner: str = Owner, repo: str = Repo, since: date | None = None, until: date | None = None):
    return build_report(owner, repo, since, until)


@app.get("/v1/repos/{owner}/{repo}/review-load/narrative")
def review_load_narrative(owner: str = Owner, repo: str = Repo, since: date | None = None, until: date | None = None):
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(503, "Narrative is disabled: OPENAI_API_KEY is not set")
    report = build_report(owner, repo, since, until)

    # same repo + dates explained in the last hour? reuse that answer, no OpenAI call
    name = report["repo"].lower()
    explanation = db.find_narrative(name, report["since"], report["until"])
    if explanation is None:
        explanation = narrative.explain(report)
        db.save_narrative(name, report["since"], report["until"], explanation)

    return {"narrative": explanation, "metrics": report}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/v1/history")
def history():
    return db.history()


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(FilePath(__file__).parent / "static" / "index.html")
