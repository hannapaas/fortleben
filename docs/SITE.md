# Fortleben — the site, page by page

What a visitor finds at each address and what they can do there, as `house/web.py` serves it. Anything not in the tables below isn't served: it gets a short "There's no page at this address" page (or a JSON 404 for a script). How the text on the pages was made is `STAGES.md`; how a run works for the person steering it is `EDITORS-DESK.md`.

Two rules run through every page:
- **Say what was done, no more.** Every edition says at the top that the English is keikaku's (and who commissioned it), and in its colophon that keikaku drafted, read and revised it on Meta's models, in how many calls, with how many queries. A paragraph carries a mark only when a person did something to it: a seal for *editor-approved*, a second seal for an editor's own change. A paragraph that never got past the draft says *unchecked draft*, in words.
- **No dollars on the site.** An editor's allowance shows in drops of ink, and a run on someone's own key in tokens. Prices and the house's recipes keep changing, and a dollar figure on a page goes stale; the costs are in `docs/experiments/`.

## Pages

| Address | What's on it | What a visitor can do |
|---|---|---|
| `/` | **The library.** A headline, a line on what Fortleben is, the name's meaning (Benjamin's "living on"), and 転生 printed under it in the edition colour. Three short answers: who translates, how to read it, can I make my own edition. Then the shelf, grouped by source language: each work's Japanese and English title, author, year, its length in paragraphs as the reader shows them, a blurb (with more behind it where there is more), and every English edition by name: keikaku's and any an editor commissioned, linked, and other people's translations with their year. Each work wears its edition's colour. At the foot, how to suggest a book and become an editor. | Open a book; go to About, the wishlist or sign-up |
| `/about` | **About**: how keikaku translates, how to read an edition (the three presets), notes in the margin, becoming an editor, suggesting a book, where the texts come from. | Read |
| `/read/<work>` | **The reader.** Opens keikaku's own edition of the work (or, if keikaku has none, the first an editor commissioned). Under the title, three short boxes: the work; every English edition, with keikaku's linked and other people's named with their year (and linked where they're free to read); and the appendix, a link to the analysis. The page wears the edition's colour: the editor's pick (pink, lime, lavender or peach), or for keikaku's own the next in turn by when its work arrived. **Aa** opens the reading settings: three presets (Clean · Curious · Annotated) set the layout (English only · side by side · under each paragraph), which notes are marked, whether notes open under each paragraph, whether the 原 and * tools, the comments and paragraph numbers show. Each can be changed by hand under "More settings", along with furigana, OpenDyslexic, size and line spacing; changing anything keeps your place, and the choice is kept in the browser. At the end: the original's details with the Aozora attribution and its colophon (folded), what keikaku did (models, calls, queries raised and what came of them, and any paragraphs the editor changed by hand), the CC BY-SA 4.0 licence, and other English translations by name and year. | Tap 原 for the Japanese, or * for the paragraph's **margin**: the readers' queries (F read against the Japanese, R read as English) grouped by what was decided and why, the revision history where the text changed, the notes, and any hand edits with their date and a diff. Tap an underlined phrase for its note. **Comment** in the margin (below) |
| `/read/<work>?edition=<id>` | Another edition of the same work, one an editor commissioned from the desk, with their name under the title. | As above |
| `/read/<work>?edition=<id>&edit=1` | The edition's own editor, signed in, sees "This is your edition. Edit the English" on their edition; with `edit=1` a click on a paragraph opens its English for editing. Each saved change is published at once under the paragraph's *, with their name and the date; nothing else about the edition changes. 120 edits an hour per editor. | The editor changes a paragraph's English |
| `/read/<work>/analysis` | **How keikaku read the book**: the analysis written before drafting, on its own page (`?edition=<id>` for another edition's). What it's about (and a second reader's crux, labelled as such, where the two read it differently), the reading, the voice it was drafted in (and who rewrote it, if the editor did), who's who and what they're called by whom, the style sheet, who tells it, what comes back, and the hard spots, each linked to the paragraph that holds it. Paragraphs and people are named in words, never by the engine's ids. Where the editor changed these files by hand at the checkpoint, the changes are shown at the end, line by line. | Read; follow a hard spot to its paragraph; start your own edition (`/signup`) |
| `/wishlist` | **The wishlist.** Works on Aozora Bunko that people would like to read in English, most asked first: Japanese and English title (the Japanese alone if the English card is missing), author, year, length in sheets, a one-line summary, the Aozora card, and how many asked. Works that have an edition move to a Translated list at the foot, linked. | Paste an Aozora link, with no name or sign-in. A new link goes through the same checks as a work added on the desk (a real card, the rights rule by code, a ruby text file); a link already listed counts one more ask, once per address. Five links an hour per address, and ten new cards read from Aozora a day across the list. `keikaku wish <url>` adds or edits entries from the command line; `bin/seed-wishlist.sh` seeds a new database |
| `/signup` | **Translate one yourself**: name, email, password (at least 8 characters). The desk asks for the Meta key afterwards and says what happens to it. | Sign up, and land on your desk |
| `/login` | Sign in with email and password. A wrong pair says only that it doesn't match. Invited editors are told their link still works. | Sign in; go to reset |
| `POST /logout` | The "Sign out" button in the header. | Sign out |
| `/reset`, `/reset/<token>` | A forgotten password. Asking for a link says the same whether or not the address has an account; the link is good for an hour, once. From the link, a new password, which signs you in and signs you out everywhere else. Without reset mail on the server, the page says so and gives `KEIKAKU_CONTACT` to write to if it's set. | Ask for a link; set a new password |
| `/desk`, `/desk/<token>` | **The editors' desk**, signed in or by invite link (opening a valid link signs you in): who you are, how your runs are paid for (your own key, shown by its last four characters, or an allowance in drops), your translations, and the account form (add or change email and password). `EDITORS-DESK.md` covers it in full. | Manage the key and sign-in; open a translation |
| `/desk/new` | **A new translation**: the works a run can start on, each with its length in sheets and estimate in drops, a field to add a work from an Aozora link, the credit (or "an editor"), the edition's colour. Everything translated here is published. | Pick a work and start the run |
| `/desk/translations/<id>` | One translation: how far it has got, and while it waits at the checkpoint, the reading, the voices with page 1 in each, the files to edit by hand, notes to keikaku and approval. The page follows the run and reloads when it moves on. | Steer, approve, resume a stopped run |
| `/moderate/<action>/<id>?sig=…` | The editor's links from the daily comments email (`hide` or `restore`). The page shows the comment and asks; only its button acts, so a mail scanner that follows the link changes nothing. A link with a bad signature is refused. | Hide or publish one comment |

Behind the pages, for `reader.js` and `desk.js` only:
- `POST /read/<work>/comments` (post a comment), `GET /comments/<id>` (a comment's status, for its writer only), `POST /comments/<id>/report`, and `POST /read/<work>/edit` (the editor's paragraph edit).
- The desk's JSON routes, each at `/desk/…` and `/desk/<token>/…`: `POST runs`, `GET runs/<id>`, `POST runs/<id>/resume`, `runs/<id>/steer`, `runs/<id>/files/<name>`, `runs/<id>/approve`, and `POST works` (add a work from a link). Its HTML forms: `POST key`, `key/forget` and `account`.
- `/static/` for the CSS and scripts. There's no build step.

## Comments

Marginalia: per paragraph, in the right-hand margin beside it on wide screens and under it on phones, flat (no replies), with an optional name and no account. They're kept apart from the translation's own notes and never change the text. A margin with more than three shows two and folds the rest behind "+ N more".

**How a comment gets on the page.** No person has to be watching. Free checks in code come first (`house/comments.py`):
- at most 1,200 characters, a name of at most 40, one link at most and none in the name;
- per writer (the `fl_id` cookie the reader page sets): 3 an hour, 10 a day; per address: 6 an hour, 20 a day; 200 a day across the whole site. All of these are settings (`.env.example`).

A comment that passes is screened in the background by Spark with the `comment-screen` prompt, its name included, as quoted data. It fails spam, promotion, links that aren't about the book, hate, abuse of anyone, sexual content beyond what the book contains, threats, private details about a real person, anything unlawful to publish, and anything unrelated to the book; each fail is given a category for the editor. Criticism of the translation, tangents and talk about the book's dark content pass, and when in doubt it passes, except for links and promotion. Until it's screened only its writer sees it ("Only you can see this until it's checked"); if it fails, they see the reason and can reword. A comment whose screen didn't run (the house was closed, a cap was reached) is tried again every quarter of an hour; one the model answered badly three times waits in the daily email for the editor to publish it.

**Reports.** Every published comment has a *report* link. Reports have their own limit per address (6 an hour, 20 a day), one per address per comment, and reports from two different addresses hide the comment at once.

**Nothing is deleted.** A failed or hidden comment stays in the database with its reason and disappears from the page, for its writer too once hidden.

**The editor's email.** Once a day, after `DIGEST_HOUR` (UK time), the editor (`REPORT_EMAIL_TO`) gets one email through Resend: the day's comments, what the screen stopped, what readers hid, and what's still unscreened, each with a link signed with `KEIKAKU_SECRET` to hide or publish it. Without a Resend key the email goes to the server log. `keikaku comments` lists, hides and restores from the command line, and `--email` prints the day's email without sending it.

## Accounts and security, in brief

The code is public, so nothing here relies on the scheme being secret.
- **Passwords** are kept as scrypt hashes with a salt each. A sign-in that fails costs the same time whether or not the address has an account.
- **Sessions, reset links and invite tokens** are long random tokens; only their hashes are stored. A session lasts 90 days. A new password from the desk or a reset ends every other session; revoking an invite ends the person's sessions and removes their sign-in.
- **CSRF.** Every HTML form that changes something carries a token that must match the `fl_csrf` cookie. The desk's JSON requests and the paragraph edit need an `X-Requested-With: fetch` header, which a form on another site can't send. Cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` over https.
- **Rate limits** on sign-up (5 an hour per address), failed sign-ins (10 an hour per address and per email address), reset mails (5 an hour per address and per email address), wrong current passwords on the account form (10 an hour per person), as well as the comment and wishlist limits. A visitor's address is the connection's own, or behind a proxy that appends it to `X-Forwarded-For` (Railway does), the right-most value, read only with `KEIKAKU_TRUST_PROXY=true`.
- **Headers.** Every response, errors included, carries `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`. Desk, sign-in, sign-up and reset pages (and the reader for a signed-in person) are `Cache-Control: no-store`; desk and account pages are `noindex`. Request bodies over 256 KB are refused. There are no API docs pages.
- **Own keys.** A Meta key an editor adds is stored encrypted with a key derived from `KEIKAKU_SECRET`, used only for that editor's runs, never logged, and shown only by its last four characters. Forgetting it deletes it. Changing `KEIKAKU_SECRET` makes every stored key unreadable, so editors add theirs again.
- **Privacy.** Commenters' cookies and addresses are stored only as salted hashes. Names on comments are optional.
- **Spending** is capped in code: run, daily and total caps, an estimate before every run that refuses one that won't fit, one run at a time per person and three across the site, and `HOUSE_OPEN=false` as a kill switch. Visitors can't start runs.

## Replay and live

`keikaku serve` runs the site; `keikaku serve --replay` runs it from a clean clone with no key and no network.

| | `--replay` | Live |
|---|---|---|
| Database | A fresh one in a temp folder, loaded from the recorded runs in `fixtures/` | The live database (`KEIKAKU_DATA_DIR`); the recorded runs are loaded into it once, so a fresh server has a shelf, and live runs add to it |
| Banner | "Replay: you're looking at recorded runs from the repo. Nothing here calls a model." | None |
| Reading, analysis | Yes | Yes |
| Comments | Shown, closed to new ones | Open with a site key (`MODEL_API_KEY`), since each is screened |
| Wishlist | Shown, adding closed | Open with a site key |
| Sign-up, desk | Sign-up closed, no sign-in link in the header; the desk says runs can't start | Open. Without a site key, people can still sign up and run on their own key |
| Daily comment email | No | Yes |

With `HOUSE_OPEN=false` a live site serves reading and nothing that calls a model: comments, the wishlist form, sign-up and new runs close.
