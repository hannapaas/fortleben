# keikaku — the site, page by page

Written 1 Nov 2026. What a visitor finds at each address, what they can do there, and what's live at submission versus later. This is the contract for the site lane; `CONCEPT.md` says why, `STAGES.md` says how the text got there.

Two rules run through every page:
- **Nothing hinges on a human.** Every text is useful as machine work, and every paragraph says in words how far it got: *draft* · *house-checked* · *editor-approved* · *human-reviewed*. At submission almost everything will be *house-checked* and only the showcase *editor-approved*. The site says so plainly rather than implying more.
- **No dollars on the site.** Effort shows in drops of ink (`RUNNING-A-TEXT.md` §1). API prices and the house's recipes will keep changing, and a dollar figure on a page goes stale; the dollar figures live in the README and the evals, for developers and judges.

## Pages

| Address | What's on it | What a visitor can do | At submission |
|---|---|---|---|
| `/` | Three lines on what this is. The showcase. The shelf (every edition, with its label, language and length). The House, live or replaying. Links to the Catalogue and Evals. | Start reading | Live |
| `/library` | Every edition: title, author, language, length in sheets, how far it got, when it was last revised. No ranking; newest first. | Filter by label or language | Live |
| `/read/<work>` | **The reader.** One base text in three editions (Casual · Curious · Student) and three layouts (English · parallel · interleaved), chosen in the settings panel, which never loses your place. Ruby and furigana options for Japanese. Per-paragraph status in words; a thin margin strip showing where the house spent its effort; *flagged, unresolved* marks. The house's reading, the bible view and the author file, linked from the top. Colophon and credits at the end, with the Aozora attribution. | Tap a paragraph for the **margin**: the debate behind it (queries, dissent, forks, alternatives, the editor's rulings), notes with their sources, revision history. React on two axes (*how it reads* / *is it right*). **Comment** (below). **Propose a fix** to a span with a reason. | Live. Student edition if it holds; parallel layout is independent of it |
| `/read/<work>/reading` | The house's reading of this text, labelled as the house's, with what changed between versions. | Read; comment | Live |
| `/read/<work>/bible` | The story bible, human-readable: cast, ledger with the rendering per edition, motifs, style sheet, hard spots. Every version kept. | Read; propose a ledger change (becomes a query) | Live |
| `/author/<id>` | The author: dates, rights, works here and in the Catalogue. **The author file:** what the house learned about this writer across her works, each entry with where it came from (which work, which stage, or which editor ruling) and whether the latest reading agreed with it. | Read | Live for Shiraki; the file is empty until a second work by an author has run, and says so |
| `/catalogue` | Reader's reports on untranslated works: what it's about, why read it, how hard, how long, the evidence for "untranslated" and when it was checked. Default order isn't a leaderboard; a visitor can sort by most wanted. | **"I'd read this"**, one vote per reader. **Request** a text: search the Aozora index, or give title, author and link for anything else. The wanted list, including in-copyright books we won't translate. | Live with the 15 launch reports; more if time allows |
| `/house` | The floor plan with rooms lit by department, the message stream (every agent's `say`), the budget meter in drops, interns as dotted squares, forks as they open. One live run at a time; everyone watches the same one. When closed or capped, a replay and a line saying why. | Start a run on a preset passage (2 per visitor a day). Watch. Scrub the replay. | Live, presets only. Presets are pre-briefed: their reading and bible are built in advance so the live run is drafting and checking with the real state, not a cold passage |
| `/evals` | The headline side-by-side exhibit (one-shot vs keikaku, annotated in plain words); the audit counts beside it, including where we're worse; the long-context and planted-continuity results; judge calibration; method and raw verdicts. | Read; download the raw verdicts | Live |
| `/how-it-grows` | How a text gets translated here and how that could widen (below). | Vote, request | Live |
| `/about` | Where this comes from (publishing, fan translation, Wikipedia, web fiction), who built it, the licence (CC BY-SA 4.0 for our English), Aozora's terms, the honest-labels policy, contact and takedown. | | Live |
| `/editor/<token>` | The editor's desk, by invite link: the checkpoint screen, open forks, rules and their scope, locks, the moderation queue for comments and proposals, promote a reader. | Rule, lock, approve, moderate | Live, one editor |
| `/review/<token>` | A bilingual reviewer's desk, by invite link: read a paragraph against the source and mark it *human-reviewed*, or raise a query. | Mark, query | Live, probably unused by 4 Nov; that's fine and the labels will show it |

## Comments, reactions, proposals

Three different things, kept apart because they measure different things:

- **Reactions** are quick and anonymous: *beautiful · confusing · sounds off · made me stop* for how it reads, and *I think this is wrong* (which asks for a reason) for whether it's right. Shown as small chips a reader can hide. Never as rankings. The editor sees a heatmap.
- **Comments** are per paragraph, flat (no replies), pre-moderated, with an optional name. **Each thread opens with the record**: the agents' debate about that paragraph, the queries and how they were answered, so people argue with what was actually decided rather than from scratch. Until the editor has looked, a new comment shows to its author as *awaiting moderation* and to everyone else only as a count. Rate-limited by cookie and IP. Comments don't change the text.
- **Proposals** do, eventually: select a span, suggest a replacement, pick a reason (accuracy, flow, note). Pre-moderated like comments; once through, it becomes a query to the owning department and gets *accepted / stet / revised* with a reason, visible in the margin with the proposer's name if they gave one.

Moderation is one person with an invite link. The site doesn't depend on it being quick: everything is visible as counts and labels, nothing is lost, and nothing unmoderated is shown to others.

## How it grows

Written for the page, so it has to be honest:

- **Requests and votes decide what's next; an editor decides what runs.** No self-serve translation for now: the rights check, the cost and the moderation all need a person in the loop, and there's one. A text with no editor still runs, and its edition says the reading and voice weren't reviewed.
- **The wanted list is a public signal.** Which untranslated books readers want, including in-copyright ones we'll never touch, is useful to translators and presses. We'd rather a person translated them.
- **Funding a book.** The plan, not yet built: a book on the wanted list can carry a target; once readers have contributed that much, it's run through the house and published for everyone, free, as every edition here is. Nobody buys a translation; they fund one for everyone.
- **Supporting the house.** Also a plan: EPUB editions sold at a modest price on the usual stores, as a way to give something back. Everything in them is free here and anyone can generate their own, which the listing will say.
- **Other languages.** Japanese is first because it's the editor's own reading. The house is built per source language: a text comes in through a source adapter (Aozora is one), the story bible and the departments are the same, and what's specific to a language (furigana and ruby for Japanese, say) is added as that language arrives.
- **What stays the same as it grows:** every line labelled, nothing ranked by popularity, no human-sounding personas, public-domain sources only, never "human-quality".

## Later

Open accounts and a trust ladder with a calibration set; any Aozora text on request; longer works; EPUB and print; funding targets; other languages; a version of the working copy with the agents switched off, for human translators.
