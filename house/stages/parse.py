"""Stage 0: parse. Deterministic: the work and its paragraphs go into the database."""

from house.db import dumps


def run(ctx) -> dict:
    w, m = ctx.work, ctx.work.meta
    ctx.conn.execute(
        """INSERT INTO work (id, aozora_id, title, title_en, author, author_en, author_id, source_url,
           card_url, colophon, rights) VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET colophon=excluded.colophon, rights=excluded.rights""",
        (ctx.work_id, m["aozora_id"], w.title, m.get("title_en"), w.author, m.get("author_en"),
         m.get("author_id"), m.get("zip_url"), m.get("card_url"), w.colophon, dumps(m.get("rights", {}))),
    )
    for p in w.paragraphs:
        ctx.conn.execute(
            """INSERT INTO segment (id, work_id, seq, kind, text, source, tokens, sentences, scene_break_before)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(work_id, id) DO UPDATE SET text=excluded.text, source=excluded.source,
               tokens=excluded.tokens, sentences=excluded.sentences, kind=excluded.kind""",
            (p.id, ctx.work_id, p.seq, p.kind, p.text, p.source, dumps(p.tokens), dumps(p.sentences),
             int(p.scene_break_before)),
        )
    ctx.conn.commit()
    chars = sum(len(p.text) for p in w.translatable())
    return {"paragraphs": len(w.paragraphs), "translatable": len(w.translatable()), "chars": chars}
