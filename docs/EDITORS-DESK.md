# keikaku — the editors' desk: how a run works for the person steering it

Written 1 Nov 2026. The code isn't open source, so the way anyone other than us runs the house is on this site, signed in as an editor. That makes the run itself a product, and a product has to be exact about what happens to someone's text and their allowance. This is that spec. `STAGES.md` is the engine's view of the same run; this is the editor's.

## Two ways to try it

| | No sign-in | Signed in as an editor |
|---|---|---|
| Where | `/house` | `/desk` by invite link |
| What runs | A preset passage, pre-briefed (its reading and bible already built), through drafting and checking; or a whole Aozora work under 2,000 characters with its brief built live | Any work in the eligible index, whole or as a sample |
| Who pays | The house, inside the live-run cap; two runs per visitor a day | The editor's allowance, in drops |
| Where it goes | Watched live, then replayable; not added to the library | Published on the site under the editor's name, as it progresses |

Both exist because we don't know how much time anyone will give this. Someone with thirty seconds gets the House. Someone digging deeper gets an invite link with a large allowance and can take a short story the whole way, with their name on the edition if they want it there.

## Starting a text

1. **Pick a work** from the eligible index (rights already checked) or from the Catalogue. Requests from outside the index go through Acquisitions first and aren't startable until the rights verdict is *eligible*.
2. **See the estimate.** Length in sheets; the brief at about 15 drops a sheet of the *whole* text; the full run at 100 drops a sheet. Also: how much allowance you have, and what's already been done on this work by anyone (an existing brief or sample can be continued rather than redone).
3. **Choose whole or sample.** A sample runs the brief on the whole text (the house always reads the whole book) and then drafts, checks and revises only the first *n* sheets. That's how publishers commission: a sample and an approach, before the manuscript. A sample can be continued later from exactly where it stopped, by the same editor or another, with the same bible.
4. **Agree to publication.** Everything that runs here is published here, as it progresses, under the house's labels. There's no private run. The editor's name goes on the edition unless they choose to stay unnamed, in which case it says *an editor*.
5. **Start.** The allowance is reserved for the estimate; the run spends against it.

## What pauses, and what doesn't

- **The checkpoint**, once, after the brief: crux (and any disagreement between the two readers), the reading, the voice trial, the handful of bible decisions that touch everything, and open forks. About ten minutes to read. The editor approves, changes things (each change is a scoped rule, before a line of the full run is drafted) or sends it back for another first read. An editor can switch this pause off for a text; a text with no editor never pauses here.
- **Nothing else waits.** Forks, queries that went two rounds, sensitivity flags and the editor's letter all land on the desk as they arise, and the run carries on with the head's pick, labelled as such. The editor's rulings apply when they come: to lines not yet drafted directly, and to drafted lines as revisions through Source check. Locked lines are never touched by a rule; they raise a query to the editor instead.
- **The editor can pause or stop a run at any time.** Pausing finishes the call in flight, commits, and holds. Stopping does the same and releases what exists.

## What is committed when

Every stage writes its results to the record before the next stage starts (`STAGES.md`, "Stop and resume"), and the site shows the record. So at any moment the page for a work shows exactly what exists:

| After… | What's on the site |
|---|---|
| the brief | The house's reading, the bible, the voice trial; the work labelled *in progress: brief done*, with the checkpoint open if an editor is assigned |
| each page drafted | That page, labelled *draft*, in all views; the effort strip filling in |
| Source check on a page | The page's label moves to *checked against the source*; queries visible in the margin |
| the English-only passes and notes | *house-checked* per paragraph as each clears |
| the final read and release | The release: a version number, changelog, credits, colophon. The work is *published* |

Partial work is never thrown away and never hidden. A sample is a published sample. A run that stopped at page 12 of 30 is published to page 12, with a line saying where and why it stopped and what it would take to continue.

## Running out

The allowance is checked before every call against the estimate for that call. When it can't cover the next call:

1. The call in flight finishes and is committed.
2. The run is marked *paused: out of allowance* at the exact stage and page.
3. Everything done so far stays published, labelled as far as it got.
4. Anyone with allowance can resume it: the editor tops up, or a funding target on the Catalogue reaches the amount, or the house decides to finish it. Resuming continues from the committed state with the same bible and rules; the response cache means nothing already done is paid for twice.

Within a run, the house also manages the pool itself (`RUNNING-A-TEXT.md` §5): before it runs dry it gives up interns, second drafts and some notes, and Source check is the last thing to go. So "out of allowance" usually means a text published complete but with *flagged, unresolved* spots, not a text cut off mid-page.

## States of a run

`queued → brief → checkpoint (waiting for the editor) → drafting → revising → notes and checks → final read → released`, with three side states any run can enter and leave: *paused by the editor*, *paused: out of allowance*, *stopped: house closed or cap hit*. Every transition is an event, so the House shows it live and the record explains it afterwards.

## Allowances

Drops are granted by hand: by the house to an editor it has invited, or against a Catalogue funding target once it's met. No payments are taken by the site in this version. An allowance is per editor, visible on the desk, and spends only on runs that editor starts or resumes. Judges and reviewers get invite links with enough to take a short story the whole way.

## What we don't do

No private runs, no runs on text that isn't in the public domain in Japan and the US, no pasted text, no deleting a published run (a release can be superseded, never removed, except for a rights or safety takedown, which leaves a stub saying so).
