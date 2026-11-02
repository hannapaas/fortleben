"""The site: FastAPI serving Jinja templates and static files from site/ (docs/SITE.md).

With --replay it serves the recorded runs in fixtures/ from a fresh database, so it runs from a
clean clone with no key and no network; comments need a key, since each is screened by Spark.
The editors' desk (/desk/<token>, house/desk.py) starts real runs, so it needs a key and an open house too.
"""

import os
import secrets
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from house import comments, desk, edition
from house.db import ROOT, connect

SITE = ROOT / "site"
COOKIE = "fl_id"
templates = Jinja2Templates(directory=SITE / "templates")
templates.env.filters["datefmt"] = edition._date


def create_app(db: str | Path | None = None, replay: bool = False, screen: bool = True) -> FastAPI:
    load_dotenv(ROOT / ".env")
    if replay:
        db = Path(tempfile.mkdtemp(prefix="keikaku-replay-")) / "replay.db"
        edition.load_fixtures(connect(db))
    can_comment = (not replay and bool(os.environ.get("MODEL_API_KEY"))
                   and os.environ.get("HOUSE_OPEN", "true").lower() != "false")
    closed = ("Runs can't start here: this copy of the site serves recorded runs only." if replay else
              "Runs can't start here: this copy of the site has no model key." if not os.environ.get("MODEL_API_KEY") else
              "Runs can't start here: the house is closed." if os.environ.get("HOUSE_OPEN", "true").lower() == "false"
              else None)
    if not replay:
        desk.recover(connect(db))  # runs left going by a process that stopped
    app = FastAPI(title="Fortleben", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=SITE / "static"), name="static")

    def conn():
        return connect(db)

    def address(request: Request) -> str:
        # Railway puts the visitor's address first in X-Forwarded-For.
        fwd = request.headers.get("x-forwarded-for", "")
        return fwd.split(",")[0].strip() or (request.client.host if request.client else "")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "home.html", {"shelf": edition.shelf(conn()), "replay": replay})

    @app.get("/read/{work_id}", response_class=HTMLResponse)
    def read(request: Request, work_id: str):
        c = conn()
        ed = edition.edition(c, work_id)
        if not ed:
            raise HTTPException(404, "No edition of that work yet.")
        token = request.cookies.get(COOKIE) or secrets.token_urlsafe(24)
        page = templates.TemplateResponse(request, "read.html", {
            "ed": ed, "labels": edition.LABELS, "replay": replay, "can_comment": can_comment,
            "comments": comments.visible(c, work_id, token)})
        if COOKIE not in request.cookies:
            page.set_cookie(COOKIE, token, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax",
                            secure=request.url.scheme == "https")
        return page

    @app.post("/read/{work_id}/comments")
    async def post_comment(request: Request, work_id: str, background: BackgroundTasks):
        token = request.cookies.get(COOKIE)
        if not can_comment or not token:
            raise HTTPException(403, "Comments aren't open here.")
        data = await request.json()
        c = conn()
        if not c.execute("SELECT 1 FROM segment WHERE work_id=? AND id=?", (work_id, data.get("segment", ""))).fetchone():
            raise HTTPException(404, "No such paragraph.")
        try:
            cid = comments.post(c, work_id, data["segment"], str(data.get("body", "")), str(data.get("name", "")),
                                token, address(request))
        except comments.Refused as e:
            return JSONResponse({"error": str(e)}, status_code=429)
        if screen:
            background.add_task(comments.screen, db, cid)
        return {"id": cid, "status": "pending"}

    @app.get("/comments/{comment_id}")
    def comment_status(request: Request, comment_id: int):
        s = comments.status(conn(), comment_id, request.cookies.get(COOKIE, ""))
        if not s:
            raise HTTPException(404)
        return s

    @app.post("/comments/{comment_id}/report")
    def report(request: Request, comment_id: int, background: BackgroundTasks):
        result = comments.report(conn(), comment_id, address(request))
        if result == "unknown":
            raise HTTPException(404)
        if result == "limited":
            return JSONResponse({"error": "That's a lot of reports in a short time. Try again later."}, status_code=429)
        if result == "sent":
            background.add_task(comments.email_report, db, comment_id)
        return {"ok": True}

    # The editors' desk. An invite link is the only way in; desk pages are never indexed.
    NOINDEX = {"X-Robots-Tag": "noindex"}

    def plain(message: str, status: int) -> HTMLResponse:
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>Fortleben</title><p>{message}</p>",
                            status_code=status, headers=NOINDEX)

    def refused(e: desk.Refused) -> JSONResponse:
        return JSONResponse({"error": str(e)}, status_code=e.code, headers=NOINDEX)

    @app.get("/desk/{token}", response_class=HTMLResponse)
    def desk_page(request: Request, token: str):
        if replay:
            return plain(closed, 200)
        state = desk.state(conn(), token)
        if not state:
            return plain("That invite link isn't valid. Ask whoever sent it for a new one.", 404)
        page = templates.TemplateResponse(request, "desk.html", {"desk": state, "replay": replay, "closed": closed})
        page.headers.update(NOINDEX)
        return page

    @app.post("/desk/{token}/runs")
    async def desk_start(token: str, request: Request):
        if closed:
            return JSONResponse({"error": closed}, status_code=403, headers=NOINDEX)
        data = await request.json()
        try:
            run_id = desk.start(db, token, str(data.get("work", "")), data.get("agree") is True,
                                str(data.get("credit") or ""))
        except desk.Refused as e:
            return refused(e)
        return JSONResponse({"run_id": run_id}, headers=NOINDEX)

    @app.get("/desk/{token}/runs/{run_id}")
    def desk_run(token: str, run_id: int):
        run = desk.run_state(conn(), token, run_id)
        if not run:
            raise HTTPException(404, "No such run on this desk.", headers=NOINDEX)
        return JSONResponse(run, headers=NOINDEX)

    @app.post("/desk/{token}/runs/{run_id}/resume")
    def desk_resume(token: str, run_id: int):
        if closed:
            return JSONResponse({"error": closed}, status_code=403, headers=NOINDEX)
        try:
            desk.resume(db, token, run_id)
        except desk.Refused as e:
            return refused(e)
        return JSONResponse({"ok": True}, headers=NOINDEX)

    return app


def serve(db: str | None, replay: bool, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(create_app(db, replay=replay), host=host, port=port)
