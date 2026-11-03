"""The site: FastAPI serving Jinja templates and static files from site/ (docs/SITE.md).

With --replay it serves the recorded runs in fixtures/ from a fresh database, so it runs from a
clean clone with no key and no network; comments need a key, since each is screened by Spark.
Without --replay it serves the live database, into which the recorded runs are loaded once, so a
fresh server has the shelf from the start and live runs add to it.
The editors' desk (/desk when signed in, /desk/<token> from an invite link; house/desk.py) starts real
runs, so it needs a key (the site's or the person's own) and an open site too.
"""

import hmac
import json
import os
import re
import secrets
import tempfile
from urllib.parse import parse_qs
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException as StarletteHTTPException

from house import accounts, acquire, comments, desk, edition, wishlist
from house.db import ROOT, connect

SITE = ROOT / "site"
COOKIE = "fl_id"  # a reader's comments
SESSION = "fl_session"  # a signed-in person (house/accounts.py)
CSRF = "fl_csrf"  # the token every HTML form that changes something must carry
SESSION_DAYS = 90
MAX_ID = 2**63 - 1  # SQLite's largest integer; a bigger id in an address is no row, not an error
MAX_BODY = 256 * 1024  # no form or desk request comes near this
templates = Jinja2Templates(directory=SITE / "templates")
templates.env.filters["datefmt"] = edition._date


# No other site may frame these pages (the desk's buttons spend), sniff their types, or see their addresses.
SECURITY_HEADERS = {"X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin"}


# Pages with a person's own things on them (or a form for their password) are never kept by a cache.
PRIVATE = re.compile(r"^/(?:desk|login|logout|signup|reset)(?:/|$)")
BROKEN = (b"<!doctype html><meta charset=utf-8><title>Fortleben</title>"
          b"<p>Something went wrong on our side. Try again in a little while.</p>")


class Guarded:
    """Puts SECURITY_HEADERS on every response, and Cache-Control: no-store on private pages, at the
    ASGI level, so they reach responses no route made too: an unhandled error's 500 is sent from here
    (Starlette's own error page is outside every middleware), and the error is raised on to be logged.
    A redirect to this same site (Starlette's /desk/ → /desk) loses its scheme and host: built from the
    connection, it would say http:// behind Railway's https proxy."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        private = bool(PRIVATE.match(scope.get("path", "")))
        started = False

        async def guarded(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = list(message.get("headers") or [])
                have = {k.lower() for k, _ in headers}
                extra = dict(SECURITY_HEADERS, **({"Cache-Control": "no-store"} if private else {}))
                if private:
                    headers = [(k, v) for k, v in headers if k.lower() != b"cache-control"]
                    have.discard(b"cache-control")
                if 300 <= message["status"] < 400:
                    headers = [(k, _same_site(v, scope)) if k.lower() == b"location" else (k, v) for k, v in headers]
                headers += [(k.lower().encode(), v.encode()) for k, v in extra.items() if k.lower().encode() not in have]
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, guarded)
        except Exception:
            if not started:
                await guarded({"type": "http.response.start", "status": 500,
                               "headers": [(b"content-type", b"text/html; charset=utf-8"),
                                           (b"content-length", str(len(BROKEN)).encode())]})
                await send({"type": "http.response.body", "body": BROKEN})
            raise


def _same_site(location: bytes, scope) -> bytes:
    """An absolute address on the host the request came to, as a path: '/desk?x=1'."""
    host = dict(scope.get("headers") or []).get(b"host", b"")
    for scheme in (b"http://", b"https://"):
        start = scheme + host
        if host and location.startswith(start) and location[len(start):len(start) + 1] in (b"/", b"?", b""):
            return location[len(start):] or b"/"
    return location


class Capped:
    """Reads a request's body before the app does and refuses it with a 413 past MAX_BODY, whether or not
    it said how long it was (a body sent in chunks has no Content-Length). Bodies here are small, so
    holding one in memory up to the cap is cheap; the app gets it whole afterwards."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunks.append(message.get("body", b""))
            size += len(chunks[-1])
            if size > MAX_BODY:
                response = JSONResponse({"error": "That's far more than any form here sends."}, status_code=413,
                                        headers=SECURITY_HEADERS)
                return await response(scope, receive, send)
            if not message.get("more_body"):
                break
        body, given = b"".join(chunks), False

        async def replay():
            nonlocal given
            if not given:
                given = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def create_app(db: str | Path | None = None, replay: bool = False, screen: bool = True) -> FastAPI:
    load_dotenv(ROOT / ".env")
    if replay:
        db = Path(tempfile.mkdtemp(prefix="keikaku-replay-")) / "replay.db"
        edition.load_fixtures(connect(db))
    can_comment = (not replay and bool(os.environ.get("MODEL_API_KEY"))
                   and os.environ.get("HOUSE_OPEN", "true").lower() != "false")
    closed = ("Runs can't start here: this copy of the site serves recorded runs only." if replay else
              "Runs can't start here: this copy of the site has no model key." if not os.environ.get("MODEL_API_KEY") else
              "Runs can't start here: new translations are switched off on this server." if os.environ.get("HOUSE_OPEN", "true").lower() == "false"
              else None)
    if not replay:
        c = connect(db)
        edition.load_fixtures(c)  # the recorded runs, once; a live run on the same work adds a release beside them
        desk.recover(c)  # runs left going by a process that stopped
    app = FastAPI(title="Fortleben", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=SITE / "static"), name="static")

    def conn():
        return connect(db)

    NOINDEX = {"X-Robots-Tag": "noindex"}

    def whole(data) -> bool:
        """The parsed JSON holds only text that can be stored: no lone surrogates from a \\ud800 escape."""
        try:
            json.dumps(data, ensure_ascii=False).encode("utf-8")
            return True
        except UnicodeEncodeError:
            return False

    def plain(message: str, status: int) -> HTMLResponse:
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>Fortleben</title><p>{message}</p>",
                            status_code=status, headers=NOINDEX)

    def known(i: int | None) -> bool:
        return i is not None and 0 < i <= MAX_ID

    def address(request: Request) -> str:
        """The visitor's address, for the rate limits. Behind a proxy (KEIKAKU_TRUST_PROXY=true, as on
        Railway) it's the right-most X-Forwarded-For value, the one the proxy appended itself; anything
        to its left came from the client and could be made up. Otherwise the header is ignored."""
        peer = request.client.host if request.client else ""
        if os.environ.get("KEIKAKU_TRUST_PROXY", "").lower() not in ("true", "1", "yes"):
            return peer
        fwd = ",".join(request.headers.getlist("x-forwarded-for"))  # a header sent twice counts as one list
        return fwd.split(",")[-1].strip() or peer

    # A page that isn't there: a short page for a person in a browser, JSON for desk.js and reader.js.
    def browser(request: Request) -> bool:
        return request.method == "GET" and "text/html" in request.headers.get("accept", "")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and browser(request):
            message = exc.detail if exc.detail and exc.detail != "Not Found" else "There's no page at this address."
            return templates.TemplateResponse(request, "missing.html", {"message": message, "replay": replay},
                                              status_code=404)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def bad_address(request: Request, exc: RequestValidationError):
        if browser(request):  # /read/bansan?edition=abc: no such edition
            return templates.TemplateResponse(request, "missing.html", {"message": "There's no page at this address.",
                                                                        "replay": replay}, status_code=404)
        return JSONResponse({"detail": "That request didn't make sense here."}, status_code=422)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "home.html", {"shelf": edition.shelf(conn()), "replay": replay})

    @app.get("/read/{work_id}", response_class=HTMLResponse)
    def read(request: Request, work_id: str, edition_id: int | None = Query(None, alias="edition")):
        c = conn()
        ed = edition.edition(c, work_id, edition_id) if edition_id is None or known(edition_id) else None
        if not ed:
            raise HTTPException(404, "No edition of that work yet.")
        token = request.cookies.get(COOKIE) or secrets.token_urlsafe(24)
        page = templates.TemplateResponse(request, "read.html", {
            "ed": ed, "labels": edition.LABELS, "replay": replay, "can_comment": can_comment,
            "comments": comments.visible(c, work_id, token)})
        if COOKIE not in request.cookies:
            page.set_cookie(COOKIE, token, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax",
                            secure=https(request))
        return page

    @app.get("/read/{work_id}/analysis", response_class=HTMLResponse)
    def analysis(request: Request, work_id: str, edition_id: int | None = Query(None, alias="edition")):
        ed = edition.edition(conn(), work_id, edition_id) if edition_id is None or known(edition_id) else None
        if not ed or not ed["analysis"]:
            raise HTTPException(404, "No analysis of that work here.")
        return templates.TemplateResponse(request, "analysis.html", {"ed": ed, "analysis": ed["analysis"], "replay": replay})

    @app.post("/read/{work_id}/comments")
    async def post_comment(request: Request, work_id: str, background: BackgroundTasks):
        token = request.cookies.get(COOKIE)
        if not can_comment:
            raise HTTPException(403, "Comments aren't open here.")
        if not token:  # the cookie the read page set never came back
            raise HTTPException(403, "Comments need a cookie from this site. Allow cookies here and reload the page.")
        try:
            data = await request.json()
        except (ValueError, RecursionError):
            data = None
        if not isinstance(data, dict) or not whole(data):
            return JSONResponse({"error": "That comment didn't arrive whole. Try again."}, status_code=400)
        segment, body, name = (v if isinstance(v, str) else "" for v in (data.get("segment"), data.get("body"), data.get("name")))
        c = conn()
        if not c.execute("SELECT 1 FROM segment WHERE work_id=? AND id=?", (work_id, segment)).fetchone():
            raise HTTPException(404, "No such paragraph.")
        try:
            cid = comments.post(c, work_id, segment, body, name, token, address(request))
        except comments.Refused as e:
            return JSONResponse({"error": str(e)}, status_code=429 if e.limited else 400)
        if screen:
            background.add_task(comments.screen, db, cid)
        return {"id": cid, "status": "pending"}

    @app.get("/comments/{comment_id}")
    def comment_status(request: Request, comment_id: int):
        s = known(comment_id) and comments.status(conn(), comment_id, request.cookies.get(COOKIE, ""))
        if not s:
            raise HTTPException(404)
        return s

    @app.post("/comments/{comment_id}/report")
    def report(request: Request, comment_id: int, background: BackgroundTasks):
        result = comments.report(conn(), comment_id, address(request)) if known(comment_id) else "unknown"
        if result == "unknown":
            raise HTTPException(404)
        if result == "limited":
            return JSONResponse({"error": "That's a lot of reports in a short time. Try again later."}, status_code=429)
        return {"ok": True}

    # The editor's links from the daily email. Opening one only asks; the button does it, so a mail
    # scanner that follows links changes nothing.
    @app.get("/moderate/{action}/{comment_id}", response_class=HTMLResponse)
    def moderate_ask(request: Request, action: str, comment_id: int, sig: str = ""):
        if not known(comment_id) or not comments.signed(action, comment_id, sig):
            return plain("That link isn't valid.", 404)
        c = conn().execute("SELECT * FROM comment WHERE id=?", (comment_id,)).fetchone()
        if not c:
            return plain("There's no such comment.", 404)
        page = templates.TemplateResponse(request, "moderate.html", {"c": c, "action": action, "sig": sig, "replay": replay})
        page.headers.update(NOINDEX)
        return page

    @app.post("/moderate/{action}/{comment_id}", response_class=HTMLResponse)
    def moderate(action: str, comment_id: int, sig: str = ""):
        if not known(comment_id) or not comments.signed(action, comment_id, sig):
            return plain("That link isn't valid.", 404)
        done = (comments.hide(conn(), comment_id, "hidden by the editor") if action == "hide"
                else comments.restore(conn(), comment_id))
        return plain(f"Comment {comment_id} is {'hidden' if action == 'hide' else 'published'}." if done
                     else f"Comment {comment_id} was already {'hidden' if action == 'hide' else 'published'}.", 200)

    # --- Who's asking: the session cookie and the forms' CSRF token (house/accounts.py) -------------
    # Every request is resolved to a signed-in person or none. HTML forms that change anything carry
    # a token that must match the fl_csrf cookie, which another site can't read; the desk's JSON
    # requests carry an X-Requested-With header, which a form on another site can't set.

    def https(request: Request) -> bool:
        return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"

    TOO_BIG = "That's far more than any form here sends."

    @app.middleware("http")
    async def who(request: Request, call_next):
        try:
            too_big = int(request.headers.get("content-length") or 0) > MAX_BODY
        except ValueError:
            too_big = True
        sid = request.cookies.get(SESSION)
        static = request.url.path.startswith("/static/")
        request.state.person = accounts.session_person(conn(), sid) if sid and not static and not too_big else None
        csrf = request.cookies.get(CSRF) or ""
        fresh = not (16 <= len(csrf) <= 100)
        if fresh:
            csrf = secrets.token_urlsafe(32)
        request.state.csrf = csrf
        response = (JSONResponse({"error": TOO_BIG}, status_code=413) if too_big else await call_next(request))
        if fresh and not static and not too_big:
            response.set_cookie(CSRF, csrf, max_age=60 * 60 * 24 * SESSION_DAYS, httponly=True, samesite="lax",
                                secure=https(request))
        return response

    # Every body is measured before `who` and the routes see it, a body sent in chunks included.
    app.add_middleware(Capped)
    # Outermost of ours: the security headers (and no-store on private pages) on every response, errors too.
    app.add_middleware(Guarded)

    async def form_of(request: Request) -> dict[str, str] | None:
        """The posted form, one value per field, or None if its CSRF token doesn't match the cookie."""
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode("utf-8", "replace")).items()}
        cookie = request.cookies.get(CSRF) or ""
        if not cookie or not hmac.compare_digest(cookie.encode(), form.get("csrf", "").encode()):
            return None
        return form

    EXPIRED = "That form was out of date. Go back, reload the page and try again."

    def from_desk(request: Request) -> bool:
        return request.headers.get("x-requested-with") == "fetch"

    def sign_in(request: Request, response, person_id: int):
        accounts.end_session(conn(), request.cookies.get(SESSION))
        response.set_cookie(SESSION, accounts.new_session(conn(), person_id), max_age=60 * 60 * 24 * SESSION_DAYS,
                            httponly=True, samesite="lax", secure=https(request))
        return response

    def page(request: Request, template: str, status: int = 200, **ctx) -> HTMLResponse:
        r = templates.TemplateResponse(request, template, {"replay": replay, **ctx}, status_code=status)
        r.headers.update(NOINDEX)
        return r

    # --- The editors' desk. An invite link or a signed-in session gets you in; desk pages are never indexed.
    # Every desk route answers at /desk/... for a signed-in person and at /desk/<token>/... for an invite
    # link; `person_of` turns either into the person, and the desk's functions take their id from there.

    def refused(e: desk.Refused) -> JSONResponse:
        return JSONResponse({"error": str(e)}, status_code=e.code, headers=NOINDEX)

    def error(message: str, status: int) -> JSONResponse:
        return JSONResponse({"error": message}, status_code=status, headers=NOINDEX)

    def person_of(request: Request):
        token = request.path_params.get("token")
        return desk.editor(conn(), token) if token is not None else request.state.person

    def nobody(request: Request) -> JSONResponse:
        if request.path_params.get("token") is not None:
            return error("That invite link isn't valid.", 404)
        return error("Sign in first.", 401)

    def desk_route(method: str, path: str):
        """Register a desk route at /desk<path> and /desk/{token}<path>."""
        def register(fn):
            for prefix in ("/desk", "/desk/{token}"):
                app.add_api_route(prefix + path, fn, methods=[method], include_in_schema=False)
            return fn
        return register

    def json_post(fn):
        """A desk JSON POST: from desk.js only, for a known person, and only while runs can start for them."""
        async def route(request: Request):
            if not from_desk(request):
                return error("That request didn't come from the desk page.", 403)
            person = person_of(request)
            if not person:
                return nobody(request)
            if why := closed_for(person):
                return error(why, 403)
            try:
                data = await request.json()
            except (ValueError, RecursionError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            if not whole(data):
                return error("That request didn't arrive whole. Reload the page and try again.", 400)
            run_id = request.path_params.get("run_id")
            if run_id is not None:
                run_id = int(run_id) if run_id.isascii() and run_id.isdigit() else 0
                if not known(run_id):
                    return error("There's no such run on this desk.", 404)
                request.state.run_id = run_id
            try:
                return JSONResponse(await fn(request, person["id"], data), headers=NOINDEX)
            except desk.Refused as e:
                return refused(e)
        return route

    def desk_page(request: Request, person, status: int = 200, **ctx) -> HTMLResponse:
        if replay:
            return plain(closed, 200)
        who = request.path_params.get("token") or person["id"]
        state = desk.state(conn(), who)
        return retry_cards(page(request, "desk.html", status, desk=state, closed=closed_for(person), **ctx))

    def retry_cards(response):
        """After a page that lists works, try again in the background for any added work whose English
        card call failed (house/acquire.py, at most once an hour per work). Only where the site has a key."""
        if not closed:
            response.background = BackgroundTask(acquire.describe_missing, db)
        return response

    @app.get("/desk", response_class=HTMLResponse)
    def desk_home(request: Request):
        person = request.state.person
        if not person:
            return RedirectResponse("/login", status_code=303, headers=NOINDEX)
        return desk_page(request, person)

    @app.get("/desk/{token}", response_class=HTMLResponse)
    def desk_link(request: Request, token: str):
        if replay:
            return plain(closed, 200)
        person = desk.editor(conn(), token)
        if not person:
            return plain("That invite link isn't valid. Ask whoever sent it for a new one.", 404)
        response = desk_page(request, person)
        me = request.state.person
        return response if me and me["id"] == person["id"] else sign_in(request, response, person["id"])

    @desk_route("POST", "/runs")
    @json_post
    async def desk_start(request, pid, data):
        shown = data.get("estimate")  # what the page showed; the run never holds more
        shown = shown if isinstance(shown, int) and not isinstance(shown, bool) and 0 < shown <= MAX_ID else None
        credit = data.get("credit")
        if credit is not None and not isinstance(credit, str):
            raise desk.Refused("Give the name as text.")
        return {"run_id": desk.start(db, pid, str(data.get("work", "")), data.get("agree") is True,
                                     credit or "", checkpoint=data.get("checkpoint") is not False,
                                     shown=shown)}

    # A work added from a link to Aozora Bunko (house/acquire.py): its row for the list, or why not.
    @desk_route("POST", "/works")
    @json_post
    async def desk_add(request, pid, data):
        url = data.get("url")
        return await run_in_threadpool(desk.add_work, db, pid, str(url or ""))

    @desk_route("GET", "/runs/{run_id}")
    def desk_run(request: Request, run_id: str):
        person = person_of(request)
        rid = int(run_id) if run_id.isascii() and run_id.isdigit() else 0
        run = desk.run_state(conn(), person["id"], rid) if person and known(rid) else None
        if not run:
            return error("There's no such run on this desk.", 404)
        return JSONResponse(run, headers=NOINDEX)

    @desk_route("POST", "/runs/{run_id}/resume")
    @json_post
    async def desk_resume(request, pid, data):
        desk.resume(db, pid, request.state.run_id)
        return {"ok": True}

    # The checkpoint: a note to keikaku, read in the background, or approval in a voice.
    @desk_route("POST", "/runs/{run_id}/steer")
    @json_post
    async def desk_steer(request, pid, data):
        note = data.get("note")
        desk.steer(db, pid, request.state.run_id, note if isinstance(note, str) else "", data.get("voice"))
        return {"ok": True}

    @desk_route("POST", "/runs/{run_id}/approve")
    @json_post
    async def desk_approve(request, pid, data):
        desk.approve(db, pid, request.state.run_id, data.get("voice"))
        return {"ok": True}

    # --- Sign-up, sign-in and keys (house/accounts.py) -----------------------------------------------
    # Anyone can sign up with a name, an email address, a password and their own Meta key; their runs
    # spend that key. So a site with no key of its own still lets them start, unless it's a replay or shut.
    no_site_key = not replay and not os.environ.get("MODEL_API_KEY") and os.environ.get("HOUSE_OPEN", "true").lower() != "false"
    signup_closed = (closed.replace("Runs can't start here", "Sign-up is closed here") if closed and not no_site_key else
                     "Sign-up is closed here: this copy of the site has no secret set, so it can't hold keys."
                     if not os.environ.get("KEIKAKU_SECRET") else None)

    def closed_for(person) -> str | None:
        """Why runs can't start for this person, or None if they can."""
        if closed and no_site_key and accounts.has_key(person):
            return None
        return closed

    def base_url(request: Request) -> str:
        return (os.environ.get("KEIKAKU_BASE_URL") or str(request.base_url)).rstrip("/")

    def signup_page(request: Request, status: int = 200, **ctx) -> HTMLResponse:
        return page(request, "signup.html", status, closed=signup_closed, **ctx)

    @app.get("/signup", response_class=HTMLResponse)
    def signup_form(request: Request):
        return signup_page(request)

    @app.post("/signup", response_class=HTMLResponse)
    async def signup(request: Request):
        if signup_closed:
            return signup_page(request, 403)
        form = await form_of(request)
        if form is None:
            return signup_page(request, 403, error=EXPIRED)
        name, email = form.get("name", ""), form.get("email", "")
        # A form sent back for a typo doesn't count against the address; a sign-up, or a taken address, does.
        if not accounts.allow_signup(address(request), count=False):
            return signup_page(request, 429, name=name, email=email,
                               error="That's a lot of sign-ups from one place in an hour. Try again later.")
        try:
            pid = accounts.signup(conn(), name, email, form.get("password", ""), form.get("key", ""))
        except accounts.Refused as e:
            if str(e) == accounts.TAKEN:
                accounts.allow_signup(address(request))
            return signup_page(request, 400, name=name, email=email, error=str(e))
        accounts.allow_signup(address(request))
        return sign_in(request, RedirectResponse("/desk", status_code=303, headers=NOINDEX), pid)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        if request.state.person:
            return RedirectResponse("/desk", status_code=303, headers=NOINDEX)
        return page(request, "login.html")

    @app.post("/login", response_class=HTMLResponse)
    async def login(request: Request):
        form = await form_of(request)
        if form is None:
            return page(request, "login.html", 403, error=EXPIRED)
        email = form.get("email", "")
        # Only a wrong pair counts against the address and the email address; a sign-in that works doesn't.
        if not accounts.allow_login(address(request), email, count=False):
            return page(request, "login.html", 429, email=email,
                        error="That's a lot of tries in an hour. Try again later.")
        pid = accounts.authenticate(conn(), email, form.get("password", ""))
        if pid is None:
            accounts.allow_login(address(request), email)
            return page(request, "login.html", 400, email=email, error=accounts.NO_MATCH)
        return sign_in(request, RedirectResponse("/desk", status_code=303, headers=NOINDEX), pid)

    @app.post("/logout")
    async def logout(request: Request):
        if await form_of(request) is None:
            return plain(EXPIRED, 403)
        accounts.end_session(conn(), request.cookies.get(SESSION))
        response = RedirectResponse("/", status_code=303, headers=NOINDEX)
        response.delete_cookie(SESSION, httponly=True, samesite="lax", secure=https(request))
        return response

    # A forgotten password: a link by mail, through the same Resend path as the comments email.
    # The page says the same whether or not the address has an account.
    # Without reset mail, the page gives KEIKAKU_CONTACT, an address to write to, if the server has one.
    contact = os.environ.get("KEIKAKU_CONTACT", "").strip()
    contact = contact if re.fullmatch(r"[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+", contact) else ""

    def reset_mail() -> bool:
        """Reset links go by mail only with mail set up and the site's own address to put in them, never one
        taken from the request's Host header, which the asker chooses."""
        return comments.can_send() and bool(os.environ.get("KEIKAKU_BASE_URL"))

    def reset_page(request: Request, status: int = 200, **ctx) -> HTMLResponse:
        return page(request, "reset.html", status, can_mail=reset_mail(), contact=contact, **ctx)

    @app.get("/reset", response_class=HTMLResponse)
    def reset_form(request: Request):
        return reset_page(request)

    @app.post("/reset", response_class=HTMLResponse)
    async def reset_ask(request: Request):
        form = await form_of(request)
        if form is None:
            return reset_page(request, 403, error=EXPIRED)
        email = form.get("email", "").strip().lower()
        if not accounts.allow_reset(address(request), email):
            return reset_page(request, 429, email=email, error="That's a lot of reset requests in an hour. Try again later.")
        if token := accounts.new_reset(conn(), email):
            comments.send(email if reset_mail() else None, "Reset your Fortleben password",
                          f"Someone asked to reset the password for this email address on Fortleben.\n\n"
                          f"To choose a new one, open this link within the hour:\n{base_url(request)}/reset/{token}\n\n"
                          "If it wasn't you, ignore this mail: nothing changes.", private=True)
        # Without reset mail the link went to the server log, and the page doesn't claim it was mailed.
        return reset_page(request, sent=reset_mail())

    @app.get("/reset/{token}", response_class=HTMLResponse)
    def reset_link(request: Request, token: str):
        if accounts.reset_person(conn(), token) is None:
            return reset_page(request, 404, error=accounts.RESET_GONE if reset_mail() else accounts.RESET_DEAD)
        return reset_page(request, token=token)

    @app.post("/reset/{token}", response_class=HTMLResponse)
    async def reset_set(request: Request, token: str):
        form = await form_of(request)
        if form is None:
            return reset_page(request, 403, token=token, error=EXPIRED)
        try:
            pid = accounts.use_reset(conn(), token, form.get("password", ""))
        except accounts.Refused as e:
            gone = str(e) == accounts.RESET_GONE
            return reset_page(request, 404 if gone else 400, token=None if gone else token,
                              error=accounts.RESET_DEAD if gone and not reset_mail() else str(e))
        return sign_in(request, RedirectResponse("/desk", status_code=303, headers=NOINDEX), pid)

    # The desk's own forms: forget the key, add a new one, add an email address and password.
    def back_to_desk(request: Request) -> str:
        token = request.path_params.get("token")
        return f"/desk/{token}" if token is not None else "/desk"

    def no_desk(request: Request):
        if request.path_params.get("token") is not None:
            return plain("That desk link isn't valid.", 404)
        return RedirectResponse("/login", status_code=303, headers=NOINDEX)

    @desk_route("POST", "/key/forget")
    async def forget_key(request: Request):
        person = person_of(request)
        if not person:
            return no_desk(request)
        if await form_of(request) is None:
            return plain(EXPIRED, 403)
        accounts.forget_key(conn(), person["id"])
        return RedirectResponse(back_to_desk(request), status_code=303, headers=NOINDEX)

    @desk_route("POST", "/key")
    async def add_key(request: Request):
        person = person_of(request)
        if not person:
            return no_desk(request)
        form = await form_of(request)
        if form is None:
            return plain(EXPIRED, 403)
        try:
            accounts.set_key(conn(), person["id"], form.get("key", ""))
        except accounts.Refused as e:
            return desk_page(request, person, 400, key_error=str(e))
        return RedirectResponse(back_to_desk(request), status_code=303, headers=NOINDEX)

    @desk_route("POST", "/account")
    async def add_login(request: Request):
        person = person_of(request)
        if not person:
            return no_desk(request)
        form = await form_of(request)
        if form is None:
            return plain(EXPIRED, 403)
        # Its own counter, per person, of wrong current passwords only: a typo in the new email or a
        # sign-in elsewhere doesn't use it up.
        if person["password_hash"] and not accounts.allow_account_change(person["id"], count=False):
            return desk_page(request, person, 429, login_error="That's a lot of tries in an hour. Try again later.",
                             login_email=form.get("email", ""))
        try:
            changed = accounts.set_login(conn(), person["id"], form.get("email", ""), form.get("password", ""),
                                         form.get("current"))
        except accounts.Refused as e:
            if str(e) == accounts.WRONG_CURRENT:
                accounts.allow_account_change(person["id"])
            return desk_page(request, person, 400, login_error=str(e),
                             login_email=form.get("email", ""))
        if changed:  # a new password signs the person out everywhere but here; a new email alone doesn't
            accounts.end_sessions(conn(), person["id"], keep=request.cookies.get(SESSION))
        return RedirectResponse(back_to_desk(request), status_code=303, headers=NOINDEX)

    # --- The public wishlist (house/wishlist.py) ---------------------------------------------------
    # Anyone can paste an Aozora link, with no sign-in; it goes through the desk's add (house/acquire.py),
    # so it needs what a run needs: no replay, a key, an open house.

    def wishlist_page(request: Request, status: int = 200, **ctx) -> HTMLResponse:
        return retry_cards(templates.TemplateResponse(request, "wishlist.html", {
            "replay": replay, "closed": closed, "wishes": wishlist.entries(conn()), **ctx}, status_code=status))

    @app.get("/wishlist", response_class=HTMLResponse)
    def wishlist_view(request: Request):
        return wishlist_page(request)

    @app.post("/wishlist", response_class=HTMLResponse)
    async def wishlist_ask(request: Request):
        if closed:
            return wishlist_page(request, 403)
        form = parse_qs((await request.body()).decode("utf-8", "replace"))
        url = (form.get("url") or [""])[0][:500]
        try:
            ip = address(request)
            said = await run_in_threadpool(lambda: wishlist.ask(conn(), url, ip))  # its own connection, in the worker thread
        except wishlist.Refused as e:
            return wishlist_page(request, e.code, url=url, error=str(e))
        return wishlist_page(request, said=said)

    return app


def serve(db: str | None, replay: bool, host: str, port: int) -> None:
    import uvicorn

    app = create_app(db, replay=replay)
    if not replay:
        comments.start_digests(db)  # the editor's daily comments email
    # The address and scheme come from the connection; X-Forwarded-For is read by `address` only behind a
    # proxy (KEIKAKU_TRUST_PROXY), so uvicorn mustn't rewrite them from headers a client can send.
    uvicorn.run(app, host=host, port=port, proxy_headers=False)
