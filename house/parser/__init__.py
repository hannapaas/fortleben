"""The source adapter interface. Each language adds house/lang/<code>/ with an adapter.

A source adapter fetches a work and turns it into an ordered list of paragraphs with IDs,
deterministically, before any model sees the text (docs/STAGES.md, "Units").
"""

from dataclasses import asdict, dataclass, field


@dataclass
class Paragraph:
    id: str  # 'p12', in source order, never changes
    seq: int
    kind: str  # narration / dialogue / heading / imprint
    text: str  # plain text, ruby bases only
    source: str  # the original line, verbatim
    tokens: list  # structured: text, ruby, emph, gaiji, odoriji, note, layout
    sentences: list  # [{'id': 'p12-s1', 'text': ...}]
    scene_break_before: bool = False
    model_text: str = ""  # what models read: ruby kept as base《reading》, editorial notes dropped

    @property
    def translatable(self) -> bool:
        return self.kind in ("narration", "dialogue", "heading")


@dataclass
class ParsedWork:
    title: str
    author: str
    head: str  # everything before the body, verbatim (title, author, the notation legend)
    paragraphs: list[Paragraph]
    lines: list  # the body, line by line: a paragraph id, or the verbatim text of a non-paragraph line
    colophon: str  # the 底本 block, verbatim
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def translatable(self) -> list[Paragraph]:
        return [p for p in self.paragraphs if p.translatable]

    def para(self, pid: str) -> Paragraph:
        return next(p for p in self.paragraphs if p.id == pid)
