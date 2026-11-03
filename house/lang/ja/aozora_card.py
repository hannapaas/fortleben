"""Reading an Aozora Bunko card page: which link is a work, and what its card says about it.

A card (/cards/<author id>/card<n>.html) is one work. It has a title table (作品名, 副題, 著者名),
a 作品データ table whose 初出 row says where and when the work first appeared, one 作家データ table
per person credited (著者, 翻訳者, ...) with their 没年, and the download table, where the ruby
text is the `<n>_ruby_<m>.zip` file. A person's page (/index_pages/person<id>.html) has the same
作家データ rows; it is read only when the card leaves out a 没年. A work Aozora splits across
cards (分冊) carries a numbered or 上/下 副題: 「源氏物語」 with 副題 "01 桐壺".
Cards are UTF-8 today; older pages declare Shift_JIS, so pages are decoded by what they declare.
"""

import html
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

HOSTS = ("www.aozora.gr.jp", "aozora.gr.jp")
CARD = re.compile(r"^/cards/(\d{6})/card(\d+)\.html$")
FILE = re.compile(r"^/cards/(\d{6})/files/(\d+)[_.][^/]*$")
RUBY_ZIP = re.compile(r"^/cards/\d{6}/files/\d+_ruby_\d+\.zip$")
PERSON = re.compile(r"^/index_pages/person(\d+)\.html$")


class NotAWork(ValueError):
    """The link isn't a work on Aozora Bunko; the message says so plainly."""


NOT_AOZORA = "That isn't an Aozora Bunko link. Paste the address of a work's page on https://www.aozora.gr.jp."
PLAIN_HTTP = "That link starts with http://. Paste the https:// address of the page."
NOT_A_CARD = ("That link isn't a work on Aozora Bunko. Paste the address of the work's card, "
              "like https://www.aozora.gr.jp/cards/000879/card92.html.")


def on_aozora(url: str) -> bool:
    """https on www.aozora.gr.jp or aozora.gr.jp, with no port, user or password."""
    try:
        p = urlsplit(url.strip())
        return (p.scheme == "https" and (p.hostname or "") in HOSTS and p.port in (None, 443)
                and p.username is None and p.password is None)
    except ValueError:
        return False


def card(url: str) -> tuple[str, str, str]:
    """(author id, card number, card URL) for a card or a file under a card; NotAWork otherwise.
    Query strings and fragments are dropped."""
    if not isinstance(url, str) or not on_aozora(url):
        if isinstance(url, str) and on_aozora("https" + url.strip()[4:]) and url.strip().lower().startswith("http:"):
            raise NotAWork(PLAIN_HTTP)
        raise NotAWork(NOT_AOZORA)
    path = urlsplit(url.strip()).path
    m = CARD.match(path) or FILE.match(path)
    if not m:
        raise NotAWork(NOT_A_CARD)
    author_id, n = m.group(1), str(int(m.group(2)))
    return author_id, n, f"https://www.aozora.gr.jp/cards/{author_id}/card{n}.html"


def decode(data: bytes) -> str:
    """A page's text, by the charset it declares, then UTF-8, then Shift_JIS."""
    m = re.search(rb"""charset\s*=\s*["']?([A-Za-z0-9_-]+)""", data[:4096])
    tried = []
    if m:
        cs = m.group(1).decode("ascii").lower()
        tried.append("cp932" if cs.replace("-", "_") in ("shift_jis", "sjis", "x_sjis", "windows_31j") else cs)
    for cs in [*tried, "utf-8", "cp932"]:
        try:
            return data.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def _rows(table: str) -> list[tuple[str, str]]:
    """(label, raw value) for each `<td class="header">label：</td><td>value</td>` row."""
    return [(_text(k).rstrip("：:"), v) for k, v in
            re.findall(r'<td class="header">(.*?)</td>\s*<td>(.*?)</td>\s*</tr>', table, re.S)]


def _tables(page: str, summary: str) -> list[str]:
    return re.findall(rf'<table summary="{summary}"[^>]*>(.*?)</table>', page, re.S)


def _first(rows, label):
    return next((v for k, v in rows if k == label), None)


def _person_href(value: str | None) -> str | None:
    m = re.search(r'href="([^"]*person\d+\.html)"', value or "")
    return m.group(1) if m else None


def join_name(name: str) -> str:
    """'素木 しづ' → '素木しづ', as the texts and this site write Japanese names; other names keep their space."""
    return re.sub(r"(?<=[぀-ゟ㐀-鿿々])[ 　](?=[぀-ゟ㐀-鿿々])", "", name).strip()


def parse_card(page: str, card_url: str) -> dict:
    """What the card says. Values are None where the card doesn't say."""
    title_rows = _rows(_tables(page, "タイトルデータ")[0]) if _tables(page, "タイトルデータ") else []
    work_rows = _rows(_tables(page, "作品データ")[0]) if _tables(page, "作品データ") else []
    title = _text(_first(title_rows, "作品名") or "") or None
    subtitle = _text(_first(title_rows, "副題") or "") or None
    author = _first(title_rows, "著者名")
    a = re.search(r"<a [^>]*>(.*?)</a>", author or "", re.S)
    people = []
    for t in _tables(page, "作家データ"):
        rows = _rows(t)
        href = _person_href(_first(rows, "作家名"))
        people.append({"name": join_name(_text(_first(rows, "作家名") or "")), "role": _text(_first(rows, "分類") or ""),
                       "romaji": _text(_first(rows, "ローマ字表記") or "").strip(" ,") or None,
                       "died": death_year(_text(_first(rows, "没年") or "")),
                       "page": urljoin(card_url, href) if href else None})
    zips = [urljoin(card_url, h) for h in re.findall(r'href="([^"]+_ruby_\d+\.zip)"', page)]
    zips = [z for z in zips if on_aozora(z) and RUBY_ZIP.match(urlsplit(z).path)]
    first = _first(work_rows, "初出")
    return {"title": title, "subtitle": subtitle,
            "author": join_name(_text(a.group(1) if a else author or "")) or None,
            "people": people, "first_published": _text(first) if first is not None else None,
            "zip_url": zips[0] if zips else None}


def parse_person(page: str) -> int | None:
    """The 没年 on a person's page, as a year."""
    rows = [r for t in _tables(page, "作家データ") for r in _rows(t)]
    return death_year(_text(_first(rows, "没年") or ""))


# --- years ---------------------------------------------------------------------------------------

# The year before each era's first (元年): 大正6年 is 1911 + 6 = 1917.
ERAS = {"令和": 2018, "平成": 1988, "昭和": 1925, "大正": 1911, "明治": 1867, "慶応": 1864, "慶應": 1864,
        "元治": 1863, "文久": 1860, "万延": 1859, "安政": 1853, "嘉永": 1847, "弘化": 1843, "天保": 1829}
KANJI_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
ERA_YEAR = re.compile(rf"({'|'.join(ERAS)})\s*(元|\d+|[〇零一二三四五六七八九十]+)")
WESTERN = re.compile(r"(?<!\d)(\d{4})\s*(?:\([^)]{0,12}\))?\s*年")


def kanji_number(s: str) -> int | None:
    if s == "元":
        return 1
    if s.isdigit():
        return int(s)
    if "十" in s:
        tens, _, ones = s.partition("十")
        return (KANJI_DIGITS.get(tens, 0) if tens else 1) * 10 + (KANJI_DIGITS.get(ones, 0) if ones else 0)
    if all(c in KANJI_DIGITS for c in s):
        return int("".join(str(KANJI_DIGITS[c]) for c in s))
    return None


def years(text: str) -> list[int]:
    """Every year a note mentions: 西暦 followed by 年 (1917年, 1917（大正6）年), and era years (大正6, 大正六年)."""
    t = unicodedata.normalize("NFKC", text or "")
    out = [int(y) for y in WESTERN.findall(t)]
    for era, n in ERA_YEAR.findall(t):
        k = kanji_number(n)
        if k:
            out.append(ERAS[era] + k)
    return sorted(y for y in out if 600 <= y <= 2100)


def death_year(text: str) -> int | None:
    """'1918-01-29' → 1918; also '1918年' or an era date. None for 不詳, blank, or anything else."""
    t = unicodedata.normalize("NFKC", text or "")
    m = re.match(r"\s*(\d{4})(?:-\d{1,2}-\d{1,2})?\s*$", t)
    if m:
        return int(m.group(1))
    ys = years(t)
    return ys[0] if len(set(ys)) == 1 else None


SPLIT = re.compile(r"^(?:\d+|[上中下]|[上中下]巻|[前中後]編|[前中後]篇|第[\d〇一二三四五六七八九十百]+[巻部編篇回分冊])(?:\s|$|[(（])")


def is_split(info: dict) -> bool:
    """A work Aozora splits across cards: a numbered or 上/中/下 副題, or a title ending in (上) and the like."""
    sub = unicodedata.normalize("NFKC", info.get("subtitle") or "")
    title = unicodedata.normalize("NFKC", info.get("title") or "")
    return bool(SPLIT.match(sub) or re.search(r"\((?:上|中|下|前編|後編|その\d+)\)$|分冊", title + sub))
