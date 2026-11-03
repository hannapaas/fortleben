"""Adding a work from a link to Aozora Bunko: read its card, apply the rights rule, keep its ruby text.

Everything comes from the card (house/lang/ja/aozora_card.py): the title, the author, the people
credited and their 没年, the 初出 and the ruby zip. The rule is works.eligible() and it is applied by
code: a year that can't be read is a refusal, never a guess. The text is kept in the data folder
(sources/<work id>.txt) and the record in the `work` table; the fetched pages aren't kept. One
small model call gives the English title, the romanised author and a one-line blurb; if it fails
the work is added with the Japanese ones.
"""

import io
import zipfile
from datetime import date
from urllib.parse import urljoin, urlsplit

import httpx

from house import events, works
from house.client import SPARK, Call, load_schema, make_client
from house.db import dumps
from house.lang.ja import aozora, aozora_card
from house.lang.ja.aozora_card import NotAWork

MAX_BYTES = 5_000_000  # a card is ~10 KB and a ruby zip rarely 1 MB; anything past this isn't a card
MAX_TEXT = 10_000_000  # the text inside the zip, unpacked
REDIRECTS = 2
TIMEOUT = 20
OPENING = 400  # characters of the text the model sees

NO_RUBY = "keikaku needs Aozora's ruby text file for this work, and this card has none."
UNKNOWN = "keikaku couldn't tell when this was first published (or when the author died), so it can't translate it."
SPLIT = "Aozora splits this work across several cards, and keikaku only translates a work that is whole on one card."
UNREADABLE = "keikaku can't read the text file on this card."
NOT_FOUND = "There's no work at that address on Aozora Bunko."
UNREACHABLE = "Aozora Bunko didn't answer. Try again in a little while."
TOO_BIG = "That file is larger than any work keikaku translates."


class Refused(Exception):
    """A link that can't be added; the message is for the person who pasted it."""


def get(url: str) -> bytes:
    """One page or file from Aozora: https only, at most REDIRECTS redirects and each one still on
    Aozora, a timeout, and no more than MAX_BYTES."""
    for _ in range(REDIRECTS + 1):
        if not aozora_card.on_aozora(url):
            raise Refused(aozora_card.NOT_AOZORA)
        try:
            with httpx.stream("GET", url, timeout=TIMEOUT, follow_redirects=False,
                              headers={"User-Agent": "keikaku (Fortleben)"}) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code == 404:
                    raise Refused(NOT_FOUND)
                if r.status_code != 200:
                    raise Refused(UNREACHABLE)
                if int(r.headers.get("content-length") or 0) > MAX_BYTES:
                    raise Refused(TOO_BIG)
                data = bytearray()
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > MAX_BYTES:
                        raise Refused(TOO_BIG)
                return bytes(data)
        except httpx.HTTPError:
            raise Refused(UNREACHABLE) from None
    raise Refused(UNREACHABLE)


def unzip(data: bytes) -> str:
    """The .txt inside a ruby zip, decoded (Aozora's texts are Shift_JIS)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            txt = [i for i in z.infolist() if i.filename.lower().endswith(".txt")]
            if len(txt) != 1 or txt[0].file_size > MAX_TEXT:
                raise Refused(UNREADABLE)
            raw = z.read(txt[0])
    except (zipfile.BadZipFile, KeyError):
        raise Refused(UNREADABLE) from None
    for cs in ("cp932", "utf-8-sig"):
        try:
            return raw.decode(cs).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    raise Refused(UNREADABLE)


def rights(info: dict, read_on: str, person_page: bool = False) -> dict:
    """The rights record from the card, in works.json's shape; Refused unless works.eligible() passes.
    The death that counts is the latest of everyone credited (a translator's too). 初出 counts from the
    earliest year it names, but a note naming any year past 1930 (a serial that ran on, a later
    version) is refused: the text Aozora has may be the later one."""
    people = info["people"]
    if not people or any(p["died"] is None for p in people):
        raise Refused(UNKNOWN)
    last = max(people, key=lambda p: p["died"])
    if last["died"] > 1931:
        who = "" if last["role"] in ("著者", "") else " (the translator)" if last["role"] == "翻訳者" else f" ({last['role']})"
        raise Refused(f"{last['name']}{who} died in {last['died']}. keikaku only translates works by people "
                      f"who died in 1931 or earlier.")
    ys = aozora_card.years(info["first_published"] or "")
    if not ys:
        raise Refused(UNKNOWN)
    if ys[0] > 1930:
        raise Refused(f"This was first published in {ys[0]}. keikaku only translates works first published by 1930.")
    if ys[-1] > 1930:
        raise Refused(f"Aozora's card says this appeared in {ys[-1]} as well as {ys[0]}. keikaku only "
                      f"translates works that were wholly published by 1930.")
    died = ", ".join(f"{'author' if p['role'] == '著者' else 'translator' if p['role'] == '翻訳者' else p['role']} "
                     f"died {p['died']}" for p in people)
    record = {"author_died": last["died"], "first_published": info["first_published"], "first_published_year": ys[0],
              "people": [{"name": p["name"], "role": p["role"], "died": p["died"]} for p in people],
              "basis": f"Aozora card{' and author page' if person_page else ''}, read on {read_on}",
              "verdict": f"public domain ({died}, published {ys[0]})"}
    if not works.eligible(record):  # the rule itself, so this can never drift from it
        raise Refused(UNKNOWN)
    return record


def describe(conn, title: str, author: str, romaji: str | None, first_published: str, text: str) -> dict:
    """The English title, the romanised author and a blurb, from one small call; {} if it fails."""
    body = aozora.parse(text)
    opening = "".join(p.text for p in body.translatable())[:OPENING]
    inp = (f"Title: {title}\nAuthor: {author}" + (f" (Aozora's romanisation: {romaji})" if romaji else "")
           + f"\nFirst published: {first_published}\n\nThe opening:\n{opening}")
    try:
        res = make_client(conn).call(Call("work-card", SPARK, "low", inp, load_schema("work-card"),
                                          expected_output_tokens=300, max_output_tokens=4000, stage="add"))
        return res.data if isinstance(res.data, dict) else {}
    except Exception:  # noqa: BLE001 - the work is added without them; nothing here is worth failing the add for
        return {}


def find(conn, card_url: str) -> str | None:
    """A work keikaku already has for this card: one in fixtures/works.json, or one added before."""
    for wid, w in works.registry(conn).items():
        if w.get("card_url") == card_url and (works.source_path(wid).exists()):
            return wid
    return None


def add(conn, url: str, person_id: int | None = None, today: str | None = None,
        via: str | None = None) -> tuple[str, bool]:
    """Add the work this link points to. Returns (work id, whether it is new); Refused says why not.
    The same link twice finds the work it added the first time, with nothing fetched. `via` names where
    an anonymous add came from ("wishlist"), so that place's daily limit can count its own reads."""
    try:
        author_id, n, card_url = aozora_card.card(url)
    except NotAWork as e:
        raise Refused(str(e)) from None
    known = find(conn, card_url)
    if known:
        return known, False
    work_id = f"{works.ADDED}{author_id}-{n}"
    actor = "editor" if person_id else "house"
    try:
        info = aozora_card.parse_card(aozora_card.decode(get(card_url)), card_url)
        if not info["title"] or not info["author"]:
            raise Refused("keikaku couldn't read that card.")
        if aozora_card.is_split(info):
            raise Refused(SPLIT)
        person_page = False
        for p in info["people"]:  # the card normally carries each 没年; the person's own page if it doesn't
            if p["died"] is None and p["page"] and aozora_card.on_aozora(p["page"]) \
                    and aozora_card.PERSON.match(urlsplit(p["page"]).path):
                p["died"] = aozora_card.parse_person(aozora_card.decode(get(p["page"])))
                person_page = True
        record = rights(info, today or date.today().isoformat(), person_page)
        if not info["zip_url"]:
            raise Refused(NO_RUBY)
        text = unzip(get(info["zip_url"]))
        try:
            parsed = aozora.parse(text)
        except Exception:  # noqa: BLE001 - a text the parser can't take is refused, whatever the reason
            raise Refused(UNREADABLE) from None
        if not parsed.translatable():
            raise Refused(UNREADABLE)
    except Refused as e:
        events.emit(conn, None, actor, "work.refused", {"url": card_url, "why": str(e), "person": person_id,
                                                        **({"via": via} if via else {})})
        raise
    title = info["title"] + (f"　{info['subtitle']}" if info["subtitle"] else "")
    romaji = next((p["romaji"] for p in info["people"] if p["name"] == info["author"]), None)
    card_text = describe(conn, title, info["author"], romaji, info["first_published"], text)
    path = works.source_path(work_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".txt.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    conn.execute(
        """INSERT INTO work (id, aozora_id, language, title, title_en, author, author_en, author_id, source_url,
           card_url, colophon, rights, status, blurb, added_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'parsed',?,?)
           ON CONFLICT(id) DO UPDATE SET title=excluded.title, title_en=excluded.title_en, author=excluded.author,
           author_en=excluded.author_en, source_url=excluded.source_url, card_url=excluded.card_url,
           colophon=excluded.colophon, rights=excluded.rights, status='parsed', blurb=excluded.blurb""",
        (work_id, n.zfill(6), "ja", title, (card_text.get("title_en") or "").strip() or title, info["author"],
         (card_text.get("author_en") or "").strip() or info["author"], author_id, info["zip_url"], card_url,
         parsed.colophon, dumps(record), (card_text.get("blurb") or "").strip() or None, person_id))
    events.emit(conn, None, actor, "work.added", {"work": work_id, "url": card_url, "person": person_id,
                                                  "rights": record, **({"via": via} if via else {})}, commit=False)
    conn.commit()
    return work_id, True


def adds_today(conn, person_id: int) -> int:
    """Links this person has had read from Aozora in the last day, added or refused."""
    return conn.execute("SELECT COUNT(*) FROM event WHERE type IN ('work.added', 'work.refused') "
                        "AND json_extract(payload, '$.person') = ? AND created_at >= datetime('now', '-1 day')",
                        (person_id,)).fetchone()[0]

