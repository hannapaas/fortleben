"""The public wishlist (/wishlist): works on Aozora Bunko people would like to read in English.

Anyone can paste a link, with no name and no sign-in. A new link goes through the same add as the
desk's (house/acquire.py: a work on Aozora, the rights rule by code, a ruby text file, one small
model call for the English card), so a wished work is a `work` row like any other and the desk can
start it. A link already on the list counts one more person, once per address. Free checks come
first: five links an hour from one address, and ten new links read from Aozora a day across the
whole list, refused ones included, so nobody mirrors Aozora through the form.
"""

from house import acquire, works
from house.comments import digest

ASKS_PER_HOUR = 5  # links one address may paste in an hour, counted or refused
READS_PER_DAY = 10  # new links the wishlist may have read from Aozora in a day, added or refused

EMPTY = "Paste a link first."
TOO_MANY = "That's a lot of links from one place in an hour. Try again later."
FULL_TODAY = "The wishlist has read ten new links from Aozora today. Try again tomorrow."


class Refused(Exception):
    """A link the wishlist won't take; the message is for the person who pasted it."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def people(n: int) -> str:
    return "1 person" if n == 1 else f"{n} people"


def _published(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT work_id FROM edition WHERE current_release IS NOT NULL")}


def entries(conn) -> dict:
    """The list as the page shows it: the works still wanted, most asked first, and the ones
    translated since (each with its edition)."""
    from house import desk  # desk imports this module

    listed = {w["id"]: w for w in desk.eligible_works(conn)}
    published = _published(conn)
    reg = works.registry(conn)
    out = {"wanted": [], "translated": []}
    for r in conn.execute("SELECT * FROM wish ORDER BY count DESC, created_at, work_id"):
        w = listed.get(r["work_id"])
        if not w:  # a work whose text isn't stored here
            continue
        card = reg.get(r["work_id"], {}).get("card_url")
        done = r["work_id"] in published
        out["translated" if done else "wanted"].append({
            "id": w["id"], "title": w["title"], "title_en": w["title_en"], "author_en": w["author_en"],
            "year": w["first_published_year"], "sheets": round(w["sheets"], 1), "blurb": w["blurb"],
            "card_url": card, "count": r["count"], "asked": people(r["count"]),
            "edition_url": f"/read/{w['id']}" if done else None})
    return out


def set_count(conn, work_id: str, count: int) -> None:
    """Put a work on the list with this count, or take it off with 0."""
    if count <= 0:
        conn.execute("DELETE FROM wish WHERE work_id=?", (work_id,))
    else:
        conn.execute("INSERT INTO wish (work_id, count) VALUES (?, ?) ON CONFLICT(work_id) DO UPDATE SET count=excluded.count",
                     (work_id, count))
    conn.commit()


def reads_today(conn) -> int:
    """New links the wishlist has had read from Aozora in the last day, added or refused."""
    return conn.execute("SELECT COUNT(*) FROM event WHERE type IN ('work.added', 'work.refused') "
                        "AND json_extract(payload, '$.via') = 'wishlist' AND created_at >= datetime('now', '-1 day')"
                        ).fetchone()[0]


def ask(conn, url: str, address: str) -> dict:
    """One person asking for the work this link points to. Returns the work, its count and a line
    to show them; Refused says why not."""
    url = (url or "").strip()
    if not url:
        raise Refused(EMPTY)
    ip = digest(address)
    if conn.execute("SELECT COUNT(*) FROM wish_ask WHERE ip=? AND created_at > datetime('now', '-1 hour')",
                    (ip,)).fetchone()[0] >= ASKS_PER_HOUR:
        raise Refused(TOO_MANY, 429)
    ask_id = conn.execute("INSERT INTO wish_ask (ip) VALUES (?)", (ip,)).lastrowid
    conn.commit()
    try:
        _, _, card_url = acquire.aozora_card.card(url)
    except acquire.NotAWork as e:
        raise Refused(str(e)) from None
    if not acquire.find(conn, card_url) and reads_today(conn) >= READS_PER_DAY:
        raise Refused(FULL_TODAY, 429)
    try:
        work_id, _ = acquire.add(conn, url, via="wishlist")
    except acquire.Refused as e:
        raise Refused(str(e)) from None
    if work_id in _published(conn):
        return {"work_id": work_id, "count": None, "edition_url": f"/read/{work_id}",
                "message": "keikaku has translated this one already."}
    before = conn.execute("SELECT 1 FROM wish_ask WHERE ip=? AND work_id=?", (ip, work_id)).fetchone()
    conn.execute("UPDATE wish_ask SET work_id=? WHERE id=?", (work_id, ask_id))
    row = conn.execute("SELECT count FROM wish WHERE work_id=?", (work_id,)).fetchone()
    if row and before:
        conn.commit()
        return {"work_id": work_id, "count": row["count"], "edition_url": None,
                "message": f"You've asked for this one already. That's {people(row['count'])} so far."}
    if row:
        conn.execute("UPDATE wish SET count = count + 1, last_asked_at = datetime('now') WHERE work_id=?", (work_id,))
        conn.commit()
        n = row["count"] + 1
        return {"work_id": work_id, "count": n, "edition_url": None,
                "message": f"Already on the list: that's {people(n)} now."}
    conn.execute("INSERT INTO wish (work_id) VALUES (?)", (work_id,))
    conn.commit()
    return {"work_id": work_id, "count": 1, "edition_url": None, "message": "Added to the list."}
