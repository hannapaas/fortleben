# The editors' desk: steering a run

The desk is where a person starts a translation and steers it. It's a few pages on the site (`/desk`), backed by `house/desk.py`, `house/steer.py` and `house/accounts.py`; the same steering works from the terminal and through a coding assistant. `STAGES.md` is the engine's view of a run; this is the view of the person running it.

A run is always a whole work. Nothing starts that the allowance (or, on your own key, the run cap) can't cover, it stops once for the editor to review, and everything it makes is published on the site under the editor's credit. There are no private translations, and no pasted text: a work comes from the list or from an Aozora Bunko link that passes the rights check.

## Two ways in

**An invite link with an allowance.** `keikaku invite "Name" --drops 4000` makes a person, an allowance in drops and a link, `/desk/<token>`, printed once. Opening it signs the person in (a session cookie, as below), so `/desk` works for them afterwards, and from the desk they can add an email address and password to sign in without the link. Their runs spend the site's key, out of their allowance. An invite can name a work to suggest (`--work`); otherwise the desk suggests the shortest work the allowance covers.

**Sign up and bring your own Meta key.** `/signup` takes a name (it goes on the edition), an email address and a password of at least 8 characters, and signs the person straight in to `/desk`. The desk then asks for their Meta Model API key, with plain advice: make a key for this alone, put on it only what you're willing to spend, start small, turn off automatic top-up. Their runs spend that key and have no allowance.

**The key** is encrypted with `KEIKAKU_SECRET` (Fernet) and decrypted only to build the model client for that person's own runs and notes. It's never logged and never shown back except as its last four characters. *Forget this key* on the desk deletes it; *Add a key* takes a new one. A site without the secret can't hold keys and says so; changing the secret makes stored keys unreadable (the desk treats them as gone) and voids every invite link, whose tokens are stored only as a hash salted with the same secret. A site with no model key of its own still lets people start runs on theirs.

**Signing in.** `/login` takes the email and password; `/reset` mails a link good for an hour and once, and reads the same whether or not the address has an account. Passwords are salted scrypt hashes; a session is a random id in the `fl_session` cookie for 90 days, stored only as a hash. A new password ends the person's other sessions. Revoking an invite ends that person's sessions and clears any email and password they added. Sign-ups, wrong sign-ins and reset mails are each limited per hour.

## The pages

- **`/desk`**: your translations, each with where it has got to and what it has spent; *Start a new translation*; and your account (email and password, the key or the allowance).
- **`/desk/new`**: pick or add a work and start it.
- **`/desk/translations/<id>`**: one translation. Its steps run down the page (done, the current one with a moving ellipsis, the rest faded; the editor's review is drawn round where keikaku's steps are square). While the run waits for the editor, the review sits underneath.

Every desk route answers at `/desk/…` for a signed-in person and at `/desk/<token>/…` for an invite link. The pages ask the server how runs are getting on every five seconds, and a translation's page reloads when its run moves on a step.

## Starting a translation

1. **Pick a work.** The list is every work whose rights record passes and whose text is stored, with its length in sheets (400 characters of the Japanese) and, for an allowance, its estimate in drops and whether the allowance covers it. A work you can't afford is shown but can't be picked. A work already on the shelf can be translated again: yours is a separate edition under your credit.
2. **Or add one from Aozora Bunko.** Paste the link to a work's card (or a file on it). The house reads the card and applies the rights rule in code: everyone credited died in 1931 or earlier, and every year in 初出 is 1930 or earlier; a year it can't read is a refusal, never a guess. A work split across several cards, or a card with no ruby text, is refused. A work that passes is kept in the data folder's `sources/` and added to everyone's list, marked *Added from Aozora*, with an English title, romanised author and one-line blurb from one small model call (if it fails, the Japanese shows alone and the call is tried again, at most hourly, when the work is next listed). The same card twice is the same work. Each person can have ten cards read a day; a card refused on what it says is remembered for 30 days and refused again without being fetched or counted.
3. **The estimate.** Sheets times a rate: the average cost per sheet of the last five finished runs, with a tenth on top, never under 100 drops a sheet, and 175 until there are finished runs to go on (`DESK_DROPS_PER_SHEET`). A start never holds more than the page showed, and is refused with a request to reload if the page's figure is more than a quarter below the fresh one. On your own key there's no figure in drops; a work whose estimate is over the run cap is marked as longer than one run may spend.
4. **Credit.** How the edition names you, up to 60 characters, no links, and not one of the site's own names. Left empty, the edition says *an editor*. On the site the edition reads as *keikaku, commissioned by* that name. An editor's next run of the same work revises their own edition; nobody's run lands in someone else's.
5. **Colour.** The edition's own accent, for its title and marks: pink, lime, lavender or peach.
6. **Publication.** The page says it plainly: everything translated here is published on Fortleben with your credit on it. Starting is agreeing; the server refuses a start without that agreement.
7. **Start.** On an allowance, the whole estimate is reserved before the first call. The run's cap is the reservation plus 20%. Start goes straight to the translation's own page, and you can close it while the run goes.

A desk run stops at the checkpoint unless the start request sends `"checkpoint": false`, which the desk page never does.

## The review (the checkpoint)

After the story bible, the run drafts page 1 once in each voice the reading offers (two or three), saves those drafts, and stops with status `waiting`. A waiting run is settled first, so nothing is held from the allowance while it waits, and it doesn't count as a run going.

The translation's page then shows:

- **The reading**: what the house thinks the story turns on, and how the English should carry it.
- **The analysis**: the story bible (who everyone is, the style sheet, the motifs, the hard spots).
- **The voice**: page 1 drafted in each voice, side by side, each with its name and description. Pick one.
- **Your notes so far**, each with keikaku's reply, what it changed, any question it asked, and page 1 as it came back.

These are the three files every later stage reads, word for word: the reading, the bible and the voice's name and line go into every call from the draft to the notes.

**Notes in plain words.** Write anything from "the daughter is older than this reads" to "less formal" and press *Send note*. One call goes to the model that wrote the reading, with the reading, the bible, page 1 in the picked voice, the earlier notes and your note. It returns a short reply, a line for each thing it changed, a question only if two quite different changes would both fit, and the reading and bible amended where the note reaches; these are saved as new versions only where they differ. Then page 1 is drafted again in the picked voice, under the amended bible, so you see the effect as English. The page says "Reading your note" and reloads when the round is in. Send as many as you like; nothing else is drafted until you approve. A round's calls are charged like the rest of the run, against its cap.

A note goes in as what the text does, never as what someone asked for: "I want the mother colder" becomes something like "her lines are short and she adds nothing to soften them". Every later stage carries the bible, and would otherwise repeat the request into the reader's margin.

**Editing the files by hand.** Each file is a box you can type in, as tall as its text. A change is saved with *Save* or Ctrl/Cmd-S, before a note or the approval goes, and when the page is left. Every later stage reads your version. The voice's name and description are fields on the picked voice and together make up the voices file (one `## Voice N: name` heading per voice, then its line). A file can grow to three times what keikaku wrote (at least 6,000 characters) and can't be emptied. A note sent after an edit is read against your version; if it amends that file, its version replaces yours, and the record says so.

**Rewriting page 1.** Page 1 in a voice can be rewritten paragraph by paragraph, keeping the same number of paragraphs. Approve in that voice and the draft takes your page as its first page instead of drafting it, and every later page is written to match it. A note that redrafts that page replaces your edit, and the record says so.

Every hand edit is kept as a new version with a `document.edited` event holding before, after and who. The edition's analysis page (`/read/<work>/analysis`) publishes the reading and the bible, and every edit as a line-by-line diff under the editor's credit and the date.

**Approving.** The note box has one button: *Send note* while something is written in it, *Approve and translate* while it's empty, so a note is never lost by approving. Approval records the picked voice, reserves what's left of the run's reservation again, and carries the run on from the draft. Notes, edits and approval are refused unless the run is waiting, and while a note is still being read. Approval is also refused if you have another run going or the site is full; notes aren't.

## After approval

The run drafts every page in the chosen voice, checks and revises it against the Japanese, gives it a final read and a copy-edit, writes the notes and releases the edition (`STAGES.md` has each stage). Nothing waits for the editor again.

When it's done, the desk links the edition (*Read it*) and the page for editing it (*Edit it*). At the end of the run you are charged what the ledger says it spent, rounded up to whole drops and never more than the reservation; the rest comes back to the allowance.

## Editing the published English

The edition's own editor, signed in, can change any paragraph from the reading page (`/read/<work>?edition=<id>&edit=1`, which *Edit it* opens), at any time. Each change is a new revision of the run's English with a `revision.created` event, cause `editor`, keeping before, after and who. The page shows the latest version. An edited paragraph carries a round mark; under its `*`, each change is listed as *Edited by* the editor, with the date and what was struck out and put in. The edition's closing line says how many paragraphs the editor changed by hand.

Section headings can't be edited, nor can a paragraph be emptied. One editor can save 120 changes an hour. Nobody else can edit an edition, and the house's own editions can't be edited from the site.

## States, resume and failure

A run on the desk is `queued`, `running`, `waiting`, `done`, `failed` or `interrupted`. Every stage commits its results before the next starts, so a run that stops can carry on from the stage after the last one it finished, and the response cache means nothing is paid for twice.

- **Interrupted.** A desk run left going when the site restarts is marked `interrupted` and settled, so its hold is released. *Resume* carries it on; one approved at the checkpoint carries on from the draft.
- **Failed.** A stage error, the run's cap, the site's daily or total cap, a key that ran out of credit or was turned down, or the site switched off. The desk says what stopped it in plain words, for example: "It stopped when its budget ran out. Everything it finished is kept; resume it and it carries on from there." A run that stopped at its cap after using its whole reservation holds a quarter more on resume, and its cap rises to match. A run on your own key that the key turned down can't be resumed (a translation can't change keys part-way): start it afresh with a key that works. A run on a key you've since forgotten can't be resumed until you add one.
- **Waiting.** Goes on only through approval.

Resuming reserves what's left of the estimate again. A failed or interrupted run is settled like a finished one: charged what it spent, the rest released.

## Allowances and caps

- **Drops.** An allowance is counted in drops of ink. One drop is `KEIKAKU_DROP_USD` of model spend ($0.0006 by default); the site shows drops only. Allowances are granted by hand, with `keikaku invite`; the site takes no payments. An allowance is per person, visible on the desk, and spends only on that person's runs.
- **Run cap.** An allowance run is capped at its reservation plus 20%; an overrun past the reservation is never charged to the editor. A run on your own key is capped by the run cap alone (`KEIKAKU_CAP_RUN`, $30 by default), and a work whose estimate is over it can't start. The desk shows what an own-key run spent in tokens and calls, never money.
- **The house's caps.** `KEIKAKU_CAP_DAILY` and `KEIKAKU_CAP_TOTAL` limit what the site's own key spends. Runs on someone's own key don't count against them and aren't stopped by them.
- **Room.** One run going at a time per person, and three across the site, from the desk or the command line. A run waiting at the checkpoint doesn't count as going. Past three, a start, resume or approval is refused with "Fortleben is full at the moment", and the desk says so before anyone tries.
- **Where it's off.** The desk can't start runs under `--replay`, with `HOUSE_OPEN=false`, or without `MODEL_API_KEY` (except for people with their own key), and says why.

Desk JSON requests must carry `X-Requested-With: fetch`, and the HTML forms a token matching the `fl_csrf` cookie. Desk and account pages are `noindex` and `no-store`.

## From the terminal

The same checkpoint, as Markdown files in the data folder (`KEIKAKU_DATA_DIR`, else `var/`). Runs from the terminal spend the site's key under its caps, and are priced before they start: a run whose estimate is over what it may spend isn't started, and the message says which cap to raise.

```
keikaku run <work> --checkpoint          # stops at the checkpoint, page 1 drafted in each voice
keikaku checkpoint <work>                # writes reading.md, bible.md, voices.md to checkpoints/<work>/
keikaku steer <work> "your note"         # one round: prints the reply, what changed, any question; rewrites the files
keikaku approve <work> --voice N         # approves in voice N (from 0, as voices.md numbers them)
keikaku run <work> --from draft          # carries on
```

Each acts on the latest run of the work; `--run N` picks another. `reading.md` and `bible.md` are, under their titles, exactly what every later stage reads; `voices.md` gives each voice's name in its heading and its line in italics, then page 1 in it, the rounds so far and page 1 in Japanese. Edit `reading.md`, `bible.md`, or a voice's heading and line, and the next `checkpoint`, `steer` or `approve` takes your version for that run. An edit it can't take (the files were written for another run, or the run was approved) is said so and kept aside as `<name>.unused.md`, never written over. Page 1 itself can be rewritten only on the desk. `keikaku run --from draft` refuses a run that's still waiting.

Invites:

```
keikaku invite "Name" [--drops 4000] [--work <id>] [--base-url https://…]   # prints the link once
keikaku invite --list                                                     # who has what left
keikaku invite --revoke <token or id>                                     # closes a link
```

`keikaku add <aozora link>` adds a work from Aozora with the same rights check as the desk, and `keikaku run <id>` runs it.

## Through a coding assistant

`AGENTS.md` at the repo root tells a coding assistant how to drive a run for someone who isn't technical: start it with a checkpoint, read the files, show the person the voices as the actual English of page 1, pass their notes on word for word, edit the files only when they ask for exact words changed, and approve in the voice they choose. The commands are the ones above.
