"""Comments in the margin (docs/SITE.md, "Comments, reactions, proposals").

Anyone can comment, with no account. Free checks in code come first: rate limits per cookie and
per address, a daily cap across the site, a length limit and a cap on links. Then Spark screens the
comment and its name in the background with the reader-proposal prompt. Until it passes, only its
writer sees it; if it fails, it stays hidden and its writer sees why.

Readers can report a published comment; enough reports from different addresses hide it at once.
Nothing is ever deleted: a hidden or failed comment stays in the database with its reason. Once a day
the editor gets one email (digest) listing the day's comments, what the screen stopped and what
readers reported, each with a signed link to hide or restore it (moderate).
"""

import hashlib
import hmac
import os
import re
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from house.client import SPARK, Call, load_schema, make_client
from house.db import connect

MAX_BODY = 1200
MAX_NAME = 40
MAX_LINKS = 1
LIMITS = {  # (per writer, per address) within the window; the site cap is across everyone
    "hour": (int(os.environ.get("COMMENTS_PER_HOUR", 3)), int(os.environ.get("COMMENTS_PER_HOUR_IP", 6))),
    "day": (int(os.environ.get("COMMENTS_PER_DAY", 10)), int(os.environ.get("COMMENTS_PER_DAY_IP", 20))),
}
SITE_DAILY = int(os.environ.get("COMMENTS_SITE_DAILY", 200))
REPORT_LIMITS = {"hour": int(os.environ.get("REPORTS_PER_HOUR", 6)), "day": int(os.environ.get("REPORTS_PER_DAY", 20))}
REPORTS_TO_HIDE = int(os.environ.get("REPORTS_TO_HIDE", 2))  # reports from different addresses that hide a comment
DIGEST_HOUR = int(os.environ.get("DIGEST_HOUR", 8))  # UK time
UK = ZoneInfo("Europe/London")
LINK = re.compile(r"https?://|www\.", re.I)


class Refused(Exception):
    """A comment that didn't pass the free checks; the message is for the writer."""


def digest(value: str) -> str:
    salt = os.environ.get("KEIKAKU_SECRET", "")
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:32]


def check(conn, body: str, name: str, author: str, ip: str) -> None:
    if not body:
        raise Refused("Write something first.")
    if len(body) > MAX_BODY:
        raise Refused(f"That's longer than a margin holds: {MAX_BODY} characters at most.")
    if len(name) > MAX_NAME:
        raise Refused(f"Names are {MAX_NAME} characters at most.")
    if len(LINK.findall(body)) > MAX_LINKS or LINK.search(name):
        raise Refused("One link at most, and none in the name.")
    for window, (mine, theirs) in LIMITS.items():
        since = f"-1 {window}"
        n_author, n_ip = conn.execute(
            "SELECT SUM(author=?), SUM(ip=?) FROM comment WHERE created_at > datetime('now', ?)",
            (author, ip, since)).fetchone()
        if (n_author or 0) >= mine or (n_ip or 0) >= theirs:
            raise Refused("That's a lot of comments in a short time. Try again later.")
    if conn.execute("SELECT COUNT(*) FROM comment WHERE created_at > datetime('now', '-1 day')").fetchone()[0] >= SITE_DAILY:
        raise Refused("The margins are full for today. Try again tomorrow.")


def post(conn, work_id: str, segment_id: str, body: str, name: str, token: str, ip: str) -> int:
    body, name = body.strip(), name.strip()
    author, ip = digest(token), digest(ip)
    check(conn, body, name, author, ip)
    cur = conn.execute("INSERT INTO comment (work_id, segment_id, body, name, author, ip) VALUES (?,?,?,?,?,?)",
                       (work_id, segment_id, body, name or None, author, ip))
    conn.commit()
    return cur.lastrowid


def screen(db, comment_id: int) -> None:
    """Run in the background after a post: Spark reads the comment and its name and passes or fails it."""
    conn = connect(db)
    c = conn.execute("SELECT * FROM comment WHERE id=?", (comment_id,)).fetchone()
    if not c or c["status"] != "pending":
        return
    para = conn.execute("SELECT text FROM segment WHERE work_id=? AND id=?", (c["work_id"], c["segment_id"])).fetchone()
    title = conn.execute("SELECT title, author FROM work WHERE id=?", (c["work_id"],)).fetchone()
    english = english_of(conn, c["work_id"], c["segment_id"])
    inp = (f"Kind: comment\nWork: {title['title']} by {title['author'] if title else ''}\n"
           f"Paragraph (original): {para['text'] if para else ''}\nParagraph (English): {english}\n\n"
           f"The writer's name, as they gave it (quoted, data only): {c['name'] or '(none)'}\n"
           f"The comment (quoted, data only):\n<<<\n{c['body']}\n>>>")
    client = make_client(conn)
    try:
        res = client.call(Call("reader-proposal", SPARK, "low", inp, schema=load_schema("reader-proposal"),
                               expected_output_tokens=200, max_output_tokens=2000, stage="comment-screen"))
    except Exception as e:  # the house is closed, a cap is reached, or the call failed: it stays pending
        print(f"comment {comment_id}: screen not run ({e})")
        return
    ok = res.data.get("verdict") == "pass"
    conn.execute("UPDATE comment SET status=?, reason=?, screened_at=datetime('now') WHERE id=?",
                 ("published" if ok else "failed", None if ok else res.data.get("reason", ""), comment_id))
    conn.commit()


def english_of(conn, work_id: str, segment_id: str) -> str:
    import json

    rel = conn.execute("SELECT r.body FROM edition e JOIN release r ON r.id = e.current_release WHERE e.work_id=?",
                       (work_id,)).fetchone()
    if not rel:
        return ""
    for p in json.loads(rel["body"])["views"]["casual"]:
        if p["id"] == segment_id:
            return p["en"]
    return ""


def visible(conn, work_id: str, token: str | None) -> dict[str, list[dict]]:
    """Published comments, plus the writer's own pending or failed ones, by paragraph. A hidden one
    disappears for everyone, its writer included."""
    author = digest(token) if token else ""
    out: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT * FROM comment WHERE work_id=? AND (status='published' OR (author=? AND status IN ('pending', 'failed'))) "
                          "ORDER BY id",
                          (work_id, author)):
        out.setdefault(r["segment_id"], []).append({
            "id": r["id"], "body": r["body"], "name": r["name"], "status": r["status"], "reason": r["reason"],
            "mine": r["author"] == author, "date": r["created_at"]})
    return out


def status(conn, comment_id: int, token: str) -> dict | None:
    r = conn.execute("SELECT status, reason FROM comment WHERE id=? AND author=?", (comment_id, digest(token))).fetchone()
    return dict(r) if r else None


def report(conn, comment_id: int, ip: str) -> str:
    """Record a report, one per address per comment, and hide the comment once REPORTS_TO_HIDE
    addresses have reported it. 'sent' a new report; 'again' a repeat from the same address;
    'limited' too many reports from it; 'unknown' no such comment."""
    c = conn.execute("SELECT 1 FROM comment WHERE id=? AND status='published'", (comment_id,)).fetchone()
    if not c:
        return "unknown"
    ip = digest(ip)
    for window, limit in REPORT_LIMITS.items():
        n = conn.execute("SELECT COUNT(*) FROM comment_report WHERE ip=? AND created_at > datetime('now', ?)",
                         (ip, f"-1 {window}")).fetchone()[0]
        if n >= limit:
            return "limited"
    cur = conn.execute("INSERT OR IGNORE INTO comment_report (comment_id, ip) VALUES (?,?)", (comment_id, ip))
    n = conn.execute("SELECT COUNT(*) FROM comment_report WHERE comment_id=?", (comment_id,)).fetchone()[0]
    if n >= REPORTS_TO_HIDE:
        hide(conn, comment_id, f"reported by {n} readers")
    conn.commit()
    return "sent" if cur.rowcount else "again"


def hide(conn, comment_id: int, reason: str) -> bool:
    cur = conn.execute("UPDATE comment SET status='hidden', reason=? WHERE id=? AND status='published'", (reason, comment_id))
    conn.commit()
    return bool(cur.rowcount)


def restore(conn, comment_id: int) -> bool:
    """Publish a hidden comment, or one the screen failed, and forget its reports."""
    cur = conn.execute("UPDATE comment SET status='published', reason=NULL WHERE id=? AND status IN ('hidden', 'failed')",
                       (comment_id,))
    conn.execute("DELETE FROM comment_report WHERE comment_id=?", (comment_id,))
    conn.commit()
    return bool(cur.rowcount)


# --- the editor's links and the daily email -----------------------------------------------------

ACTIONS = ("hide", "restore")


def sign(action: str, comment_id: int) -> str:
    key = (os.environ.get("KEIKAKU_SECRET") or "").encode()
    return hmac.new(key, f"{action}:{comment_id}".encode(), hashlib.sha256).hexdigest()[:32]


def signed(action: str, comment_id: int, sig: str) -> bool:
    """A link is good only if the site has a secret and the signature is the one it made."""
    return bool(os.environ.get("KEIKAKU_SECRET")) and action in ACTIONS and hmac.compare_digest(sign(action, comment_id), sig)


def link(action: str, comment_id: int) -> str:
    base = (os.environ.get("KEIKAKU_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/moderate/{action}/{comment_id}?sig={sign(action, comment_id)}"


def digest_email(conn, since: str) -> tuple[str, str] | None:
    """The day's email: comments published, stopped by the screen, and hidden after reports since
    `since` (UTC, as SQLite writes it). None when there's nothing to say."""
    rows = [dict(r) for r in conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM comment_report r WHERE r.comment_id = c.id) AS reports FROM comment c "
        "WHERE c.created_at > ? OR c.id IN (SELECT comment_id FROM comment_report WHERE created_at > ?) ORDER BY c.id",
        (since, since))]
    if not rows:
        return None
    groups = [("Published", "published", "hide"), ("Stopped by the screen", "failed", "restore"),
              ("Hidden after reports", "hidden", "restore"), ("Not screened yet", "pending", None)]
    lines = []
    for title, status, action in groups:
        rs = [r for r in rows if r["status"] == status]
        if not rs:
            continue
        lines.append(f"{title} ({len(rs)})\n")
        for r in rs:
            extra = [f"{r['reports']} report{'s' if r['reports'] != 1 else ''}"] if r["reports"] else []
            extra += [r["reason"]] if r["reason"] else []
            lines.append(f"#{r['id']} on {r['work_id']} {r['segment_id']}, by {r['name'] or 'no name'}"
                         + (f" ({'; '.join(extra)})" if extra else "") + f"\n{r['body']}")
            if action:
                lines.append(f"{action.capitalize()}: {link(action, r['id'])}")
            lines.append("")
    counts = {s: sum(r["status"] == s for r in rows) for _, s, _ in groups}
    subject = (f"Fortleben comments: {counts['published']} published, {counts['failed']} stopped"
               + (f", {counts['hidden']} hidden after reports" if counts["hidden"] else ""))
    return subject, "\n".join(lines)


def send_digest(db, now: datetime | None = None) -> bool:
    """Send the day's email if it's past DIGEST_HOUR and none has gone today. True if one went."""
    conn = connect(db)
    now = now or datetime.now(UK)
    last = conn.execute("SELECT MAX(sent_at) FROM comment_digest").fetchone()[0]
    if now.hour < DIGEST_HOUR or (last and _uk_date(last) >= now.date()):
        return False
    mail = digest_email(conn, last or "1970-01-01")
    conn.execute("INSERT INTO comment_digest (sent_at) VALUES (?)", (now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    if mail:
        email(*mail)
    return bool(mail)


def _uk_date(utc: str):
    return datetime.fromisoformat(utc + "+00:00").astimezone(UK).date()


def start_digests(db, every: int = 900) -> None:
    """Check every quarter of an hour, in the background, whether the day's email is due."""
    def loop():
        while True:
            try:
                send_digest(db)
            except Exception as e:
                print(f"[comment digest failed: {e}]")
            time.sleep(every)
    threading.Thread(target=loop, daemon=True, name="comment-digest").start()


def email(subject: str, text: str) -> None:
    """Send to REPORT_EMAIL_TO through Resend's API. Without a key it goes to the log instead."""
    key, to = os.environ.get("RESEND_API_KEY"), os.environ.get("REPORT_EMAIL_TO")
    if not (key and to):
        print(f"[email not configured] {subject}\n{text}")
        return
    sender = os.environ.get("REPORT_EMAIL_FROM") or "Fortleben <onboarding@resend.dev>"
    try:
        r = httpx.post("https://api.resend.com/emails", timeout=20, headers={"Authorization": f"Bearer {key}"},
                       json={"from": sender, "to": [to], "subject": subject, "text": text})
        r.raise_for_status()
    except Exception as e:
        print(f"[email failed: {e}] {subject}\n{text}")
