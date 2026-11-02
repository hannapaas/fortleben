"""The Aozora Bunko source adapter: fetch a work's ruby text and parse it.

Aozora's notation (https://www.aozora.gr.jp/annotation/): ruby as 漢字《かんじ》 or ｜base《reading》,
inputter's notes and layout in ［＃…］, gaiji as ※［＃description、第3水準1-85-25］ or U+XXXX,
／＼ and ／″＼ for the doubled repetition mark. Every token keeps its raw text, so joining the
raw text gives back the line exactly; that round trip is tested on the four demo texts.

The parser is deterministic and decides what a paragraph is: one line of the body is one
paragraph, a dialogue line is a paragraph, blank lines and ※ / ◇ markers are scene breaks.
"""

import io
import re
import zipfile

import httpx

from house.parser import Paragraph, ParsedWork

ODORIJI = {"／＼": "〳〵", "／″＼": "〴〵"}
DASHES = re.compile(r"^-{20,}$")
NOTE = re.compile(r"［＃(.*?)］")
JIS = re.compile(r"(?:第[34]水準)?([12])-(\d{1,2})-(\d{1,2})")
UNICODE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
EMPH = re.compile(r"^「(.+?)」に(傍点|白ゴマ傍点|丸傍点|白丸傍点|黒三角傍点|白三角傍点|二重丸傍点|蛇の目傍点|ばつ傍点|傍線|二重傍線|鎖線|破線|点線|波線)$")
LAYOUT = re.compile(r"(字下げ|字上げ|地付き|地から|改ページ|改丁|改段|改見開き|ここから|ここで|見出し|大見出し|中見出し|小見出し|ページの左右中央|左右中央|割り注|縦中横|横組み|罫囲み|行右小書き|行左小書き|上付き小文字|下付き小文字|太字|斜体|終わり)")
SCENE_MARKS = {"※", "◇", "◆", "＊", "*", "◇◇◇", "＊　＊　＊", "※　※　※"}
KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヶ〇\U00020000-\U0003ffff]")
SENT_END = "。！？!?"
CLOSERS = "』」）)】"


def gaiji_char(desc: str) -> str | None:
    """The real character for a gaiji note, where the note gives a JIS X 0213 or Unicode code."""
    m = UNICODE.search(desc)
    if m:
        return chr(int(m.group(1), 16))
    m = JIS.search(desc)
    if m:
        plane, row, cell = (int(g) for g in m.groups())
        raw = bytes([0xA0 + row, 0xA0 + cell])
        if plane == 2:
            raw = b"\x8f" + raw
        try:
            return raw.decode("euc_jis_2004")
        except UnicodeDecodeError:
            return None
    return None


def tokenize(line: str) -> list[dict]:
    """Split one line into tokens. Each token has 'raw'; ''.join(raw) == line."""
    tokens: list[dict] = []
    bar_at: int | None = None  # index in tokens where a ｜ base starts
    i = 0

    def add_text(s: str):
        if tokens and tokens[-1]["t"] == "text":
            tokens[-1]["s"] += s
            tokens[-1]["raw"] += s
        else:
            tokens.append({"t": "text", "s": s, "raw": s})

    while i < len(line):
        ch = line[i]
        if ch == "｜":
            tokens.append({"t": "bar", "raw": "｜"})
            bar_at = len(tokens)
            i += 1
        elif line.startswith("※［＃", i):
            j = line.index("］", i)
            desc = line[i + 3:j]
            tokens.append({"t": "gaiji", "s": gaiji_char(desc) or "〓", "desc": desc, "raw": line[i:j + 1]})
            i = j + 1
        elif line.startswith("［＃", i):
            j = line.index("］", i)
            body = line[i + 2:j]
            raw = line[i:j + 1]
            m = EMPH.match(body)
            if m:
                tokens.append({"t": "emph", "target": m.group(1), "style": m.group(2), "raw": raw})
            elif LAYOUT.search(body) and "底本では" not in body and "？" not in body:
                tokens.append({"t": "layout", "body": body, "raw": raw})
            else:
                tokens.append({"t": "note", "body": body, "raw": raw})
            i = j + 1
        elif ch == "《":
            j = line.index("》", i)
            reading = line[i + 1:j]
            if bar_at is not None:
                base = tokens[bar_at:]
                del tokens[bar_at:]
                bar = tokens.pop()  # the ｜ itself
                assert bar["t"] == "bar"
                ruby = {"t": "ruby", "bar": True, "base": base, "reading": reading}
                bar_at = None
            else:
                base = implicit_base(tokens)
                ruby = {"t": "ruby", "bar": False, "base": base, "reading": reading}
            ruby["raw"] = ("｜" if ruby["bar"] else "") + "".join(b["raw"] for b in base) + line[i:j + 1]
            tokens.append(ruby)
            i = j + 1
        else:
            for raw, mark in ODORIJI.items():
                if line.startswith(raw, i):
                    tokens.append({"t": "odoriji", "s": mark, "raw": raw})
                    i += len(raw)
                    break
            else:
                add_text(ch)
                i += 1
    return tokens


def implicit_base(tokens: list[dict]) -> list[dict]:
    """Without ｜, the ruby base is the run of kanji (and gaiji) just before 《."""
    base: list[dict] = []
    while tokens:
        last = tokens[-1]
        if last["t"] == "gaiji":
            base.insert(0, tokens.pop())
            continue
        if last["t"] == "text":
            s = last["s"]
            k = len(s)
            while k > 0 and KANJI.match(s[k - 1]):
                k -= 1
            if k == len(s):
                if not base:  # no kanji: take the run of the same script, as Aozora does
                    k = len(s)
                    cls = script(s[-1])
                    while k > 0 and script(s[k - 1]) == cls:
                        k -= 1
                else:
                    break
            run = s[k:]
            if k == 0:
                tokens.pop()
            else:
                last["s"] = last["raw"] = s[:k]
            base.insert(0, {"t": "text", "s": run, "raw": run})
            if k > 0:
                break
            continue
        break
    return base


def script(ch: str) -> str:
    o = ord(ch)
    if 0x3040 <= o <= 0x309F:
        return "hiragana"
    if 0x30A0 <= o <= 0x30FF:
        return "katakana"
    if ch.isascii() and ch.isalnum() or 0xFF10 <= o <= 0xFF5A:
        return "latin"
    return "other"


def plain(tokens: list[dict], ruby: bool = False) -> str:
    """Text with bases only, or with readings kept as base《reading》 when ruby=True."""
    out = []
    for t in tokens:
        if t["t"] in ("text", "gaiji", "odoriji"):
            out.append(t["s"])
        elif t["t"] == "ruby":
            base = plain(t["base"])
            out.append(f"{base}《{reading_plain(t['reading'])}》" if ruby else base)
    return "".join(out)


def reading_plain(reading: str) -> str:
    for raw, mark in ODORIJI.items():
        reading = reading.replace(raw, mark)
    return reading


def split_sentences(text: str) -> list[str]:
    """Sentence anchors. A sentence ends at 。！？ (with any closing quotes after it), except
    when a quotation is followed by と or って, which continue the same sentence."""
    out, cur, i = [], "", 0
    while i < len(text):
        cur += text[i]
        if text[i] in SENT_END:
            while i + 1 < len(text) and text[i + 1] in CLOSERS:
                i += 1
                cur += text[i]
            nxt = text[i + 1:i + 3]
            if not (cur[-1] in CLOSERS and (nxt.startswith("と") or nxt.startswith("って"))):
                out.append(cur)
                cur = ""
        i += 1
    if cur.strip():
        out.append(cur)
    return out


def kind_of(tokens: list[dict], text: str, is_last_lines: bool) -> str:
    stripped = text.strip("　 ")
    if stripped.startswith(("『", "「")):
        return "dialogue"
    layouts = [t for t in tokens if t["t"] == "layout"]
    # A closing bracketed line with a date or a magazine title is the imprint, not the story.
    if (is_last_lines and layouts and re.fullmatch(r"[（(].*[）)]", stripped)
            and re.search(r"[『「]|明治|大正|昭和|年|大[０-９\d]", stripped)):
        return "imprint"
    if any("見出し" in t["body"] for t in layouts):
        return "heading"
    return "narration"


def parse(raw: str, meta: dict | None = None) -> ParsedWork:
    text = raw.replace("\r\n", "\n")
    lines = text.split("\n")
    dash = [i for i, ln in enumerate(lines) if DASHES.match(ln)]
    body_start = dash[1] + 1 if len(dash) >= 2 else next(i for i, ln in enumerate(lines) if not ln.strip()) + 1
    colophon_at = next(i for i, ln in enumerate(lines) if ln.startswith("底本："))
    head = "\n".join(lines[:body_start])
    body = lines[body_start:colophon_at]
    colophon = "\n".join(lines[colophon_at:])

    last_content = max(i for i, ln in enumerate(body) if ln.strip())
    paragraphs, out_lines, pending_break, seen_text = [], [], False, False
    for i, ln in enumerate(body):
        bare = NOTE.sub("", ln).strip("　 ")
        if not ln.strip() or bare in SCENE_MARKS or (not bare and "改ページ" in ln):
            out_lines.append(ln)
            if seen_text:
                pending_break = True
            continue
        if not bare:  # a line holding only layout notes (ここから２字下げ and the like)
            out_lines.append(ln)
            continue
        tokens = tokenize(ln)
        assert "".join(t["raw"] for t in tokens) == ln, f"round trip failed on line {i}"
        ptext = plain(tokens)
        pid = f"p{len(paragraphs) + 1}"
        kind = kind_of(tokens, ptext, i >= last_content - 2)
        sents = [{"id": f"{pid}-s{k + 1}", "text": s} for k, s in enumerate(split_sentences(ptext.strip("　 ")))]
        paragraphs.append(Paragraph(
            id=pid, seq=len(paragraphs) + 1, kind=kind, text=ptext, source=ln, tokens=tokens,
            sentences=sents, scene_break_before=pending_break, model_text=plain(tokens, ruby=True),
        ))
        out_lines.append({"p": pid})
        pending_break, seen_text = False, True

    title, author = lines[0].strip(), lines[1].strip()
    return ParsedWork(title=title, author=author, head=head, paragraphs=paragraphs,
                      lines=out_lines, colophon=colophon, meta=meta or {})


def render(work: ParsedWork) -> str:
    """The source text back from the parse; equal to the original, line for line."""
    by_id = {p.id: p for p in work.paragraphs}
    body = [by_id[ln["p"]].source if isinstance(ln, dict) else ln for ln in work.lines]
    return "\n".join([work.head, *body, work.colophon])


def chapter(text: str, heading: str) -> str:
    """One chapter of an Aozora file: the head and notation legend, the chapter from its 中見出し heading
    to the next, and the colophon, so the excerpt still parses and still carries its credits."""
    lines = text.split("\n")
    heads = [i for i, ln in enumerate(lines) if "中見出し" in ln]
    start = next(i for i in heads if NOTE.sub("", lines[i]).strip("　 ") == heading)
    end = next((i for i in heads if i > start), next(i for i, ln in enumerate(lines) if ln.startswith("底本：")))
    colophon = next(i for i, ln in enumerate(lines) if ln.startswith("底本："))
    return "\n".join(lines[:heads[0]] + lines[start:end] + ["", ""] + lines[colophon:])


def fetch(zip_url: str) -> str:
    """Download an Aozora ruby zip and return its text, decoded from Shift_JIS."""
    r = httpx.get(zip_url, follow_redirects=True, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next(n for n in z.namelist() if n.endswith(".txt"))
        return z.read(name).decode("cp932")

