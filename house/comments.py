"""Comments in the margin (docs/SITE.md, "Comments, reactions, proposals").

Anyone can comment, with no account. Free checks in code come first: rate limits per cookie and
per address, a daily cap across the site, a length limit and a cap on links. Then Spark screens the
comment and its name in the background with the reader-proposal prompt. Until it passes, only its
writer sees it. A report emails the editor through Resend, with its own rate limit; the editor
removes a comment by deleting it.
"""

import hashlib
import os
import re

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
    """Published comments, plus the writer's own pending or failed ones, by paragraph."""
    author = digest(token) if token else ""
    out: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT * FROM comment WHERE work_id=? AND (status='published' OR author=?) ORDER BY id",
                          (work_id, author)):
        out.setdefault(r["segment_id"], []).append({
            "id": r["id"], "body": r["body"], "name": r["name"], "status": r["status"], "reason": r["reason"],
            "mine": r["author"] == author, "date": r["created_at"]})
    return out


def status(conn, comment_id: int, token: str) -> dict | None:
    r = conn.execute("SELECT status, reason FROM comment WHERE id=? AND author=?", (comment_id, digest(token))).fetchone()
    return dict(r) if r else None


def report(conn, comment_id: int, ip: str) -> str:
    """Record a report, one per address per comment. 'sent' means the editor should be emailed;
    'again' a repeat from the same address; 'limited' too many reports from it; 'unknown' no such comment."""
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
    conn.commit()
    return "sent" if cur.rowcount else "again"


def email_report(db, comment_id: int) -> None:
    conn = connect(db)
    c = conn.execute("SELECT * FROM comment WHERE id=?", (comment_id,)).fetchone()
    n = conn.execute("SELECT COUNT(*) FROM comment_report WHERE comment_id=?", (comment_id,)).fetchone()[0]
    email(f"Fortleben: comment {comment_id} reported ({n} report{'s' if n > 1 else ''})",
          f"On {c['work_id']} / {c['segment_id']}, by {c['name'] or 'no name'}, {c['created_at']}:\n\n"
          f"{c['body']}\n\nTo remove it: DELETE FROM comment WHERE id={comment_id};")


def email(subject: str, text: str) -> None:
    """Send to REPORT_EMAIL_TO through Resend's API. Without a key it goes to the log instead."""
    key, to = os.environ.get("RESEND_API_KEY"), os.environ.get("REPORT_EMAIL_TO")
    if not (key and to):
        print(f"[report email not configured] {subject}\n{text}")
        return
    sender = os.environ.get("REPORT_EMAIL_FROM") or "Fortleben <onboarding@resend.dev>"
    try:
        r = httpx.post("https://api.resend.com/emails", timeout=20, headers={"Authorization": f"Bearer {key}"},
                       json={"from": sender, "to": [to], "subject": subject, "text": text})
        r.raise_for_status()
    except Exception as e:
        print(f"[report email failed: {e}] {subject}\n{text}")
