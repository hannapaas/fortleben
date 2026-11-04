"""The house style in code, for the copy desk: the mechanical choices that need no judgement (one quote
style, one dash, British spelling, a silence printed one way), and the two lists the copy editor works
from: words the English spells more than one way, and the name readings the ruby gives."""

import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict

US_UK = {"color": "colour", "colors": "colours", "colored": "coloured", "favor": "favour", "favors": "favours",
         "favorite": "favourite", "honor": "honour", "honored": "honoured", "neighbor": "neighbour",
         "neighbors": "neighbours", "neighborhood": "neighbourhood", "behavior": "behaviour", "humor": "humour",
         "labor": "labour", "odor": "odour", "parlor": "parlour", "harbor": "harbour", "rumor": "rumour",
         "rumors": "rumours", "vapor": "vapour", "armor": "armour", "savor": "savour", "splendor": "splendour",
         "traveling": "travelling", "traveled": "travelled", "traveler": "traveller", "travelers": "travellers",
         "marveling": "marvelling", "marveled": "marvelled", "quarreling": "quarrelling", "quarreled": "quarrelled",
         "canceled": "cancelled", "jewelry": "jewellery", "gray": "grey", "center": "centre", "theater": "theatre",
         "meter": "metre", "meters": "metres", "pajamas": "pyjamas", "mustache": "moustache", "plow": "plough",
         "paralyzed": "paralysed", "analyze": "analyse", "catalog": "catalogue", "dialog": "dialogue"}
US_WORD = re.compile(r"\b(" + "|".join(US_UK) + r")\b", re.IGNORECASE)
SILENCE = re.compile(r"^[「『]?[…‥・]+[」』]?$")


def _uk(m: re.Match) -> str:
    w = m.group(0)
    uk = US_UK[w.lower()]
    return uk.capitalize() if w[0].isupper() else uk


def house_style(en: str, ja: str) -> str:
    """The English with the house's mechanical choices made: straight quotes, one dash, British
    spelling, and a silence (「……」) printed as a quoted ellipsis on its own."""
    out = en.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    out = re.sub(r"\s--\s", " — ", out).replace("——", "—").replace("--", "—")
    out = US_WORD.sub(_uk, out)
    if SILENCE.match(ja.strip("　 ")):
        out = '"…"'
    elif re.match(r"^[「『][…‥]+[」』]", ja.strip("　 ")):  # a silence, then narration: the silence stays speech
        out = re.sub(r'^\s*"?(?:\.{3,}|…+)"?\s*', '"…" ', out, count=1)
    return out


def _key(word: str) -> str:
    plain = unicodedata.normalize("NFKD", word.strip("*")).encode("ascii", "ignore").decode()
    return re.sub(r"[-\s']", "", plain).lower()


WORD = re.compile(r"\*[^*\n]{1,40}\*|[A-Za-zĀāĒēĪīŌōŪū][A-Za-zĀāĒēĪīŌōŪū'’-]*")


def variants(units: dict[tuple, str], label) -> list[str]:
    """Words the English spells more than one way: macrons, hyphens, italics, not just capitals.
    One line per word: each form, how often, and where it first appears."""
    forms, where = defaultdict(Counter), defaultdict(list)
    for unit, en in units.items():
        for m in WORD.finditer(en):
            w = m.group(0)
            forms[_key(w)][w] += 1
            if len(where[w]) < 3:
                where[w].append(label(unit))
    out = []
    for key, c in forms.items():
        if len({f.strip("*").lower() for f in c} | {f for f in c if f.startswith("*")}) < 2 or len(key) < 3:
            continue  # spelled one way, or only capitalised differently
        out.append("; ".join(f"{f} ×{n} ({', '.join(where[f])})" for f, n in c.most_common()))
    return out


# Hepburn, with macrons for long o and u, for the readings the ruby gives
KANA = dict(zip(
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょゎゐゑ",
    "a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa o n ga gi gu ge go za ji zu ze zo da ji zu de do ba bi bu be bo pa pi pu pe po a i u e o ya yu yo wa i e".split()))


def romaji(kana: str) -> str:
    """A reading in Hepburn: いきなわ → ikinawa, おおすぎ → ōsugi."""
    s = "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in kana)  # katakana to hiragana
    out, i = "", 0
    while i < len(s):
        ch, nxt = s[i], s[i + 1] if i + 1 < len(s) else ""
        if ch == "っ" and nxt in KANA:
            out += KANA[nxt][0]
        elif ch == "ー" and out:
            out += out[-1]
        elif nxt in "ゃゅょ" and nxt and ch in KANA and KANA[ch].endswith("i"):
            base = KANA[ch][:-1]
            out += (base if base in ("sh", "ch", "j") else base + "y") + KANA[nxt][-1]
            i += 1
        else:
            out += KANA.get(ch, ch)
        i += 1
    out = re.sub(r"o[ou]", "ō", out)
    out = re.sub(r"uu", "ū", out)
    return out


PLACE = tuple("村町川山寺宮島橋坂屋国郡下原沢野田谷浦崎津")
SUFFIXES = ("mura", "son", "machi", "cho", "kawa", "gawa", "yama", "san", "ji", "dera", "tera", "gun", "kori", "gori",
            "shita", "shima", "jima", "hashi", "bashi", "zaka", "saka", "ya", "kuni")  # the place-word a translation may put in English


def named(bible: dict) -> dict[str, set[str]]:
    """The English words the bible gives for Japanese ones: each cast entry's romanised name, and every
    "梅屋 (Umeya)" in its text. Keyed like _key, to the Japanese they stand for."""
    out = {}

    def add(ja, en):
        for w in re.findall(r"[A-ZĀĒĪŌŪ][\wāēīōū']+", en or ""):
            out.setdefault(_key(w), set()).add(ja)

    for c in bible.get("cast") or []:
        if c.get("name_ja"):
            add(c["name_ja"], c.get("romanised"))
    for ja, en in re.findall(r"([぀-ヿ一-鿿々〆]+)\s*[(（]([^()（）]{1,60})[)）]", json.dumps(bible, ensure_ascii=False)):
        add(ja, en)
    return out


def readings(paragraphs, bible: dict, units: dict) -> list[str]:
    """Names the English may have misread: where the ruby gives a reading for a name or a place (the
    cast's names, anything ending like a place) and the English never spells it that way, the reading
    and the English forms closest to it, among those that stand in a paragraph whose Japanese has the
    name. A near form only elsewhere is some other word's (石原 is Ishihara, near 蘆原 Ashihara), and so is
    one the bible gives for another Japanese word: 東屋《あずまや》 (an arbour) is near Umeya, which the
    bible gives for 梅屋. And any cast entry whose romanised form doesn't match its own reading, since
    every page follows the cast. `units` is the English by unit, as latest_units gives it."""
    names = {c.get("name_ja") or "" for c in bible.get("cast") or []} - {""}
    others = named(bible)
    japanese = {p.id: p.text for p in paragraphs}
    english = "\n".join(units.values())

    def beside(base: str) -> set[str]:
        """The keys of the capitalised words in the English of every unit whose Japanese has `base`."""
        return {_key(w) for unit, en in units.items() if base in "".join(japanese.get(pid, "") for pid in unit)
                for w in re.findall(r"[A-ZĀĒĪŌŪ][\wāēīōū]+", en) if len(w) > 2}

    words = Counter(re.findall(r"[A-ZĀĒĪŌŪ][\wāēīōū]+", english))
    plain = {_key(w): w for w in words}
    seq = re.findall(r"[A-Za-zĀāĒēĪīŌōŪū']+", english)
    runs = {_key("".join(seq[i:i + n])) for i in range(len(seq)) for n in (1, 2, 3, 4)}
    seen, out = set(), []
    for p in paragraphs:
        toks = p.tokens
        for i, t in enumerate(toks):
            if t.get("t") != "ruby":
                continue
            base = "".join(b.get("s", b.get("raw", "")) for b in t.get("base", []))
            after = (toks[i + 1].get("s") or "")[:1] if i + 1 < len(toks) else ""
            in_cast = base in names or (len(base) > 1 and any(base in n for n in names))  # not 長 for 局長
            if not base or base in seen or not (in_cast or base.endswith(PLACE) or after in PLACE):
                continue
            seen.add(base)
            rom = romaji(t["reading"])
            k = _key(rom)
            if len(k) < 4 or any(r.startswith(k) for r in runs) or any(k == r + suffix for r in runs for suffix in SUFFIXES if k.endswith(suffix)):
                continue  # too short to judge, or the English has it (with a space, with the okurigana after it, or 村 as "village")
            # among the words where the name stands, so a looser match (あんば written "Awa" is 0.57), and not
            # a short word that only begins it (Edo, the city, in Edozaki; Ikina for Ikinawa is a misreading)
            near = [m for m in difflib.get_close_matches(k, sorted(beside(base) & plain.keys()), n=2, cutoff=0.55)
                    if not (k.startswith(m) and 2 * len(m) <= len(k))
                    and (m not in others or any(base in ja or ja in base for ja in others[m]))]
            if near:
                out.append(f"{base}《{t['reading']}》 reads {rom.capitalize()}; the English has "
                           + " and ".join(f"{plain[k]} ×{words[plain[k]]}" for k in near) + f" (first at {p.id})")
    for c in bible.get("cast") or []:
        reading, rom = c.get("reading") or "", c.get("romanised") or ""
        a, b = _key(romaji(reading)), _key(rom)
        if reading and rom and a not in b and b not in a and difflib.SequenceMatcher(None, a, b).ratio() >= 0.7:
            out.append(f"The cast gives {c.get('name_ja')} as {rom}, but its reading {reading} is {romaji(reading)}")
    return out
