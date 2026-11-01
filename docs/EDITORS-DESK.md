# keikaku — the editors' desk: how a run works for the person steering it

Written 1 Nov 2026, simplified the same day. The code isn't open source, so the way anyone other than us runs the house is on this site, signed in as an editor. That makes the run itself a product, and a product has to be exact about what happens to someone's text and their allowance. This is that spec. `STAGES.md` is the engine's view of the same run; this is the editor's.

**Two workflows, kept apart on purpose.** A *snippet* is the demo: a preset passage in the House, paid for by the house, not added to the library. A *run* is the real thing: a whole work, with the whole estimate reserved from the editor's allowance before it starts. There are no partial translations: nothing starts that can't finish, and nobody can spend the house's tokens without an allowance that covers them.

## Two ways to try it

| | No sign-in | Signed in as an editor |
|---|---|---|
| Where | `/house` | `/desk` by invite link |
| What runs | A **snippet**: a preset passage, pre-briefed (its reading and bible already built), through drafting and checking. Fixed presets only | A **run**: any work in the eligible index, whole, with the full estimate reserved first. The invite page suggests a short story that the allowance covers |
| Who pays | The house, inside the live-run cap; two runs per visitor a day | The editor's allowance, in drops |
| Where it goes | Watched live, then replayable; not added to the library | Published on the site under the editor's name when the run is released; the House shows it live while it runs |

Both exist because we don't know how much time anyone will give this. Someone with thirty seconds gets the House. Someone digging deeper gets an invite link with an allowance already on it, a suggested short story it covers, and can take that story the whole way, with their name on the edition if they want it there. If the desk's "start a text" isn't built by submission (`BUILD-PLAN.md` M7b is the stretch), the page says it's coming and the house editor starts runs by hand.

## Starting a run

1. **Pick a work** from the eligible index (rights already checked) or from the Catalogue. Requests from outside the index go through Acquisitions first and aren't startable until the rights verdict is *eligible*.
2. **See the estimate.** Length in sheets at 100 drops a sheet, which includes the brief. Also: how much allowance you have. If the allowance doesn't cover the whole estimate, the run can't start, and the page says what it would take.
3. **Agree to publication.** Everything that runs here is published here under the house's labels. There's no private run. The editor's name goes on the edition unless they choose to stay unnamed, in which case it says *an editor*.
4. **Start.** The whole estimate is reserved from the allowance before the first call. The run spends against the reservation; whatever it doesn't use is released at the end.

## What pauses, and what doesn't

- **The checkpoint**, once, after the brief: crux (and any disagreement between the two readers), the reading, the voice trial, the handful of bible decisions that touch everything, and open forks. About ten minutes to read. The editor approves, changes things (each change is a scoped rule, before a line of the full run is drafted) or sends it back for another first read. An editor can switch this pause off for a text; a text with no editor never pauses here.
- **Nothing else waits.** Forks, queries that went two rounds, sensitivity flags and the editor's letter all land on the desk as they arise, and the run carries on with the head's pick, labelled as such. The editor's rulings apply when they come: to lines not yet drafted directly, and to drafted lines as revisions through Source check. Locked lines are never touched by a rule; they raise a query to the editor instead.
- **The editor can pause or stop a run at any time.** Pausing finishes the call in flight, commits, and holds. Stopping does the same and releases what exists.

## What is committed when

Every stage writes its results to the record before the next stage starts (`STAGES.md`, "Stop and resume"), so a run that's paused or interrupted (a crash, the house closing, the daily cap) resumes from the last completed stage and page, and the response cache means nothing is paid for twice. While a run is in progress the House shows it live and the desk shows the record; the library shows it only once it's released. There are no partial editions in the library.

## Money

- **Reserved before it starts.** The full estimate comes off the allowance at start. No reservation, no run. This is the rule that stops anyone spending the house's tokens without cover.
- **The pool manages itself.** An estimate is an estimate, so within the run the house keeps to its pool the way `RUNNING-A-TEXT.md` §5 describes: it gives up interns, second drafts and some notes before it would run short, and Source check is the last thing to go. The result is a complete text, with *flagged, unresolved* spots where it economised, never a text cut off mid-page.
- **A small overrun is the house's.** If a run still exceeds its reservation (the estimate was wrong), the house covers up to a fixed margin (20%) so the text finishes; beyond that the hard caps stop it, it's committed where it stands, and the house editor decides whether to finish it on the house. That's an operational failure to fix in the estimate, not a state the product offers.
- **Unused reservation is released** at the end of the run.

## States of a run

`queued → brief → checkpoint (waiting for the editor) → drafting → revising → notes and checks → final read → released`, with two side states: *paused* (by the editor, or by the house closing or a cap) and *stopped* (by the editor). Every transition is an event, so the House shows it live and the record explains it afterwards.

## Allowances

Drops are granted by hand: by the house to an editor it has invited, or against a Catalogue funding target once it's met. No payments are taken by the site in this version. An allowance is per editor, visible on the desk, and spends only on runs that editor starts. Judges and reviewers get invite links with an allowance already on them and a suggested short story it covers.

## What we don't do

No private runs, no sample runs or partial editions (the snippet in the House is the demo), no runs on text that isn't in the public domain in Japan and the US, no pasted text, no deleting a published edition (a release can be superseded, never removed, except for a rights or safety takedown, which leaves a stub saying so).
