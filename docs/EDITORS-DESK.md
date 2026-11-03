# keikaku — the editors' desk: how a run works for the person steering it

Written 1 Nov 2026, simplified the same day. The code is open source, but the way most people will run the house is on this site, signed in as an editor, not from a clone. That makes the run itself a product, and a product has to be exact about what happens to someone's text and their allowance. This is that spec. `STAGES.md` is the engine's view of the same run; this is the editor's.

**Only editors start runs.** The House is the demo for everyone else: a walkthrough of a finished run, where nothing runs (`SITE.md`, `/house`). A *run* is the real thing: a whole work, with the whole estimate reserved from the editor's allowance before it starts. There are no partial translations: nothing starts that can't finish, and nobody can spend the house's tokens without an allowance that covers them.

## Two ways to try it

| | No sign-in | Signed in as an editor |
|---|---|---|
| Where | `/house` | `/desk`, signed in with an email address and password, or by invite link |
| What runs | Nothing: a walkthrough of the showcase run, with picked moments and every stage's full output | A **run**: any work in the eligible index, whole, with the full estimate reserved first. The invite page suggests a short story that the allowance covers |
| Who pays | Nobody; it's read from the record | The editor's allowance, in drops |
| Where it goes | Nothing new is made | Published on the site under the editor's name when the run is released |

Both exist because we don't know how much time anyone will give this. Someone with thirty seconds gets the House. Someone digging deeper gets an invite link with an allowance already on it, a suggested short story it covers, and can take that story the whole way, with their name on the edition if they want it there.

## Starting a run

1. **Pick a work** from the eligible index (rights already checked) or from the Catalogue. Requests from outside the index go through Acquisitions first and aren't startable until the rights verdict is *eligible*.
2. **See the estimate.** Length in sheets at 100 drops a sheet, which includes the brief. Also: how much allowance you have. If the allowance doesn't cover the whole estimate, the run can't start, and the page says what it would take.
3. **Agree to publication.** Everything that runs here is published here under the house's labels. There's no private run. The editor's name goes on the edition unless they choose to stay unnamed, in which case it says *an editor*.
4. **Start.** The whole estimate is reserved from the allowance before the first call. The run spends against the reservation; whatever it doesn't use is released at the end.

## What pauses, and what doesn't

- **The checkpoint**, once, after the brief: crux (and any disagreement between the two readers), the reading and its voice takes, the handful of bible decisions that touch everything, and open forks. About ten minutes to read. The editor approves, changes things (each change is a scoped rule, before a line of the full run is drafted) or sends it back for another first read. An editor can switch this pause off for a text; a text with no editor never pauses here.
- **Nothing else waits.** Forks, the final read's notes for the editor, sensitivity flags and the editor's letter all land on the desk as they arise, and the run carries on with the house's pick, labelled as such. The editor's rulings apply when they come: to lines not yet drafted directly, and to drafted lines as revisions through the desk. Locked lines are never touched by a rule; they raise a query to the editor instead.
- **The editor can pause or stop a run at any time.** Pausing finishes the call in flight, commits, and holds. Stopping does the same and releases what exists.

## What is committed when

Every stage writes its results to the record before the next stage starts (`STAGES.md`, "Stop and resume"), so a run that's paused or interrupted (a crash, the house closing, the daily cap) resumes from the last completed stage and page, and the response cache means nothing is paid for twice. While a run is in progress the House shows it live and the desk shows the record; the library shows it only once it's released. There are no partial editions in the library.

## Money

- **Reserved before it starts.** The full estimate comes off the allowance at start. No reservation, no run. This is the rule that stops anyone spending the house's tokens without cover.
- **The estimate is high on purpose.** The engine prices the whole run before it starts (every stage live with no cache, the lever's pass back, then ×1.5) and refuses to start one that won't fit (`RUNNING-A-TEXT.md` §5). Nothing is given up part-way.
- **If it still runs out**, the hard caps stop it: it's committed where it stands, nothing is released, and the house editor decides whether to raise the cap and resume it on the house. That's an operational failure to fix in the estimate, not a state the product offers. (Planned for the site: the house covering a small overrun, up to 20%, so the text finishes.)
- **Unused reservation is released** at the end of the run.

## States of a run

`queued → brief → checkpoint (waiting for the editor) → drafting → revising → notes and checks → final read → released`, with two side states: *paused* (by the editor, or by the house closing or a cap) and *stopped* (by the editor). Every transition is an event, so the House shows it live and the record explains it afterwards.

## As built (2 Nov 2026, checkpoint 3 Nov)

Where the code (`house/desk.py`, `house/accounts.py`, the `/desk` routes in `house/web.py`) differs from the above, or settles what it left open:

- **Signing in.** People sign up at `/signup` with a name, an email address, a password (at least 8 characters) and their own Meta key, and are signed in to `/desk` straight away; no link is shown. `/login` takes the email and password (a wrong pair says only "That email and password don't match."; ten tries an hour per address and per email address); `POST /logout` signs out. The password is an scrypt hash with its own salt. A session is a random id in the `fl_session` cookie (httponly, SameSite=Lax, secure over https, 90 days); only its hash is stored, in `session`. One email address, one account. *Forgotten your password?* mails a link through Resend (the same path as the comments email), good for an hour and once; the page says the same whether or not the address has an account, and without `RESEND_API_KEY` it says reset mail isn't set up and the link goes to the server log. Setting a new password signs the person in and ends their other sessions.
- **One desk, two ways in.** Invite links still exist for editors we invite. Opening `/desk/<token>` signs the editor in with the same session, so `/desk` works for them afterwards, and from the desk they can add an email address and password to sign in without the link. Every desk route answers at `/desk/…` for a signed-in person and at `/desk/<token>/…` for a link; the web layer turns either into the person and the desk's functions (`desk.state`, `start`, `steer`, `approve`, …) take their id. Revoking an invite ends that person's sessions and clears any password they added.
- **Forms and requests that change things.** The desk's JSON requests carry `X-Requested-With: fetch` and are refused without it; the HTML forms (sign-up, sign-in, sign-out, reset, forget or add a key, add an email) carry a token that must match the `fl_csrf` cookie. Desk, sign-in and reset pages send `X-Robots-Tag: noindex`.

- **Invites.** `keikaku invite "Name" [--drops 4000] [--work sumiyaki] [--base-url …]` makes a person, an allowance and a link, and prints the link once. Only a hash of the token is stored (salted with `KEIKAKU_SECRET`, so changing that secret voids every link). `keikaku invite --list` shows who has what left; `keikaku invite --revoke <token or id>` closes a link.
- **The checkpoint.** Desk runs start with `checkpoint: true` (a start request can send `"checkpoint": false`). After the bible the run stops with status `waiting` and is settled, so nothing is held while it waits. The desk shows, under the form: the reading (crux, the reading itself, open questions), the voice takes side by side with page 1 drafted in each, the bible for a person (style sheet open; cast, narration, motifs and hard spots folded), the notes so far with the house's reply, what it changed, any question, and page 1 drafted again, which also replaces page 1 under the voice it was drafted in. *Send note* posts to `/desk/runs/<id>/steer` and the house reads it in the background (`house.steer.steer`); the page says "Reading your note" and reloads when the round is in. A round's calls are charged like the rest of the run. *Approve and draft* posts the voice to `/approve` (`house.steer.approve`), holds what's left of the reservation again and carries the run on from the draft. Notes and approval are refused unless the run is waiting. Pause and stop aren't built.
- **One run at a time per person; three across the site.** A run is going while its status is `queued` or `running`; a run waiting at the checkpoint doesn't count. A person with a run going can't start or approve another. Beyond three going runs on the site (from the desk or the command line) a start, resume or approval is refused with "The house is full at the moment", and the desk says so before anyone tries.
- **Money.** The estimate is `ceil(sheets × DROPS_PER_SHEET)`, reserved at start. The run's cap is the reservation plus 20%. At the end the editor is charged what the ledger says it spent, rounded up to whole drops and never more than the reservation; the rest is released. A failed or interrupted run is settled the same way, and resuming it reserves what's left of its estimate again.
- **States** on the desk are `queued`, `running`, `waiting`, `done`, `failed` and `interrupted`. A run left going when the site restarts is marked `interrupted` and can be resumed from the stage after the last one it finished; one approved at the checkpoint resumes from the draft. A waiting run carries on only through approval. A failed run (a stage error, the cap, or a key that ran out or was turned down) can be resumed too, and the desk says what stopped it in plain words: "It stopped when its budget ran out. Everything it finished is kept; resume it and it carries on from there."
- **Credit.** The edition carries the editor's name, or *an editor*. Each credit gets its own edition of the work beside the house's.
- **Any work on Aozora Bunko.** Above the list, an editor can paste the link of a work's card (or a file on it). `POST /desk/works` reads the card, applies the rights rule by code (everyone credited died by 1931; every year in 初出 is 1930 or earlier; anything unreadable is refused), keeps the ruby text in the data folder's `sources/`, and adds the work to everyone's list, marked "Added from Aozora", with an English title, romanised author and blurb from one Spark call (prompts/work-card.md). The same card twice is the same work, `aozora-<author id>-<card>`, and isn't fetched again. A work split across cards, or a card with no ruby text, is refused. Ten links a day per person. `keikaku add <url>` does the same from the command line, and `keikaku run <id>` runs it.
- **Where it's off.** The desk can't start runs under `--replay`, without `MODEL_API_KEY`, or with `HOUSE_OPEN=false`, and says so. Desk pages send `X-Robots-Tag: noindex`.

## Allowances

Drops are granted by hand: by the house to an editor it has invited, or against a Catalogue funding target once it's met. No payments are taken by the site in this version. An allowance is per editor, visible on the desk, and spends only on runs that editor starts. Judges and reviewers get invite links with an allowance already on them and a suggested short story it covers.

**Bring your own key.** Anyone can sign up at `/signup` with a name, an email address, a password and their own Meta Model API key, and gets a desk they sign in to, with no allowance: their runs spend their key, capped by the run cap (`KEIKAKU_CAP_RUN`) only, and the desk shows what a run spent in tokens, never money. The key is stored encrypted with `KEIKAKU_SECRET`, used only by the client of that person's runs, shown back only as its last four characters, and forgotten when they press *Forget this key*; *Add a key* on the desk takes a new one. A site with no key of its own still lets them start runs. Sign-ups are limited to five an hour from one address.

## What we don't do

No private runs, no sample runs or partial editions (the House walkthrough is the demo), no runs on text that isn't in the public domain in Japan and the US, no pasted text, no deleting a published edition (a release can be superseded, never removed, except for a rights or safety takedown, which leaves a stub saying so).
