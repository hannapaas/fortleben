-- keikaku: the SQLite schema. Part of the contract between lanes (docs/CONVENTIONS.md).
-- Change it only with a note in the commit and the matching doc updated in the same commit.
-- JSON columns hold text; the shape of each is the schema in house/schemas/ named in the comment.

PRAGMA foreign_keys = ON;

-- One text. Aozora card, full colophon, rights record, status.
CREATE TABLE IF NOT EXISTS work (
  id            TEXT PRIMARY KEY,          -- slug, e.g. 'bansan'
  aozora_id     TEXT,                      -- '000223'
  language      TEXT NOT NULL DEFAULT 'ja',
  title         TEXT NOT NULL,             -- 晩餐
  title_en      TEXT,                      -- Supper
  author        TEXT NOT NULL,             -- 素木しづ
  author_en     TEXT,                      -- Shiraki Shizu
  author_id     TEXT,                      -- Aozora person id, '000012'
  source_url    TEXT,
  card_url      TEXT,
  colophon      TEXT,                      -- the 底本 block, verbatim
  rights        TEXT,                      -- JSON: death year, 初出, translation search + date
  status        TEXT NOT NULL DEFAULT 'parsed',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One pass of a work through the house.
CREATE TABLE IF NOT EXISTS run (
  id            INTEGER PRIMARY KEY,
  work_id       TEXT NOT NULL REFERENCES work(id),
  label         TEXT,                      -- 'dev-1', 'showcase'
  status        TEXT NOT NULL DEFAULT 'running',  -- running / paused / done / failed
  stage         TEXT,                      -- last stage completed
  cap_usd       REAL,                      -- the live-run cap for this run
  options       TEXT,                      -- JSON: the run's set-up (models, drafting prompt)
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Paragraphs of the source, in order. The paragraph is the unit of English (docs/STAGES.md).
CREATE TABLE IF NOT EXISTS segment (
  id            TEXT NOT NULL,             -- 'p12'
  work_id       TEXT NOT NULL REFERENCES work(id),
  seq           INTEGER NOT NULL,          -- order in the text, from 1
  kind          TEXT NOT NULL,             -- narration / dialogue / heading / break
  text          TEXT NOT NULL,             -- plain Japanese, ruby bases only
  source        TEXT NOT NULL,             -- the original Aozora line, verbatim
  tokens        TEXT NOT NULL,             -- JSON: [{t:'text'|'ruby'|'emph'|'gaiji', ...}]
  sentences     TEXT NOT NULL,             -- JSON: [{id:'p12-s1', text:'...'}]
  scene_break_before INTEGER NOT NULL DEFAULT 0,
  tier          TEXT,                      -- plain / tricky / hard, set by the Analyst
  tier_reason   TEXT,
  PRIMARY KEY (work_id, id)
);

-- The story bible and the house's reading, versioned (docs/STORY-STATE.md).
CREATE TABLE IF NOT EXISTS bible (
  work_id       TEXT NOT NULL REFERENCES work(id),
  version       INTEGER NOT NULL,
  kind          TEXT NOT NULL,             -- 'reading' / 'crux-check' / 'bible' / 'parts'
  body          TEXT NOT NULL,             -- JSON
  event_id      INTEGER,                   -- the event that made this version
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (work_id, kind, version)
);

-- What the house learned about an author across works, with provenance.
CREATE TABLE IF NOT EXISTS author_file (
  id            INTEGER PRIMARY KEY,
  author_id     TEXT NOT NULL,
  work_id       TEXT REFERENCES work(id),
  stage         TEXT,
  entry         TEXT NOT NULL,
  agreed        INTEGER,                   -- did the latest reading agree with it
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Base English per paragraph (or group), versioned.
CREATE TABLE IF NOT EXISTS revision (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER NOT NULL REFERENCES run(id),
  work_id       TEXT NOT NULL,
  segment_ids   TEXT NOT NULL,             -- JSON list: ['p12'] or ['p12','p13'] for a group
  version       INTEGER NOT NULL,
  english       TEXT NOT NULL,             -- plain English
  spans         TEXT,                      -- JSON: best-effort sentence spans
  notes         TEXT,                      -- JSON: translator notes
  alternatives  TEXT,                      -- JSON: marked alternatives
  flags         TEXT,                      -- JSON
  variant       TEXT NOT NULL DEFAULT 'lead',  -- 'lead'; other variants are for experiments
  event_id      INTEGER,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Retired with the ledger; kept only so runs recorded before it went can still be read (house/audit.py).
CREATE TABLE IF NOT EXISTS term (
  id            TEXT NOT NULL,
  work_id       TEXT NOT NULL REFERENCES work(id),
  source        TEXT NOT NULL,
  reading       TEXT,
  casual        TEXT,
  curious       TEXT,
  student       TEXT,
  rationale     TEXT,
  status        TEXT NOT NULL DEFAULT 'proposed',  -- proposed / approved / locked
  PRIMARY KEY (work_id, id)
);

CREATE TABLE IF NOT EXISTS note (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER NOT NULL REFERENCES run(id),
  work_id       TEXT NOT NULL,
  anchor        TEXT NOT NULL,             -- 'p12' or 'p12-s3'
  span          TEXT,                      -- the English the note hangs on
  editions      TEXT NOT NULL,             -- JSON list: casual / curious / student
  body          TEXT NOT NULL,
  sources       TEXT,                      -- JSON list
  status        TEXT NOT NULL DEFAULT 'unverified',  -- verified / unverified / killed
  author        TEXT NOT NULL,             -- department or person
  event_id      INTEGER
);

CREATE TABLE IF NOT EXISTS query (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER NOT NULL REFERENCES run(id),
  work_id       TEXT NOT NULL,
  segment_id    TEXT NOT NULL,
  span          TEXT,
  raised_by     TEXT NOT NULL,             -- department/role
  owner         TEXT NOT NULL,             -- desk / editor / desk-recheck / translation (code-raised)
  category      TEXT NOT NULL,
  reason        TEXT NOT NULL,
  evidence      TEXT,                      -- JSON list
  recommendation TEXT,
  confidence    TEXT,
  status        TEXT NOT NULL DEFAULT 'open',  -- open / taken / declined / forked / unaddressed / noted
  round         INTEGER NOT NULL DEFAULT 0,
  answer        TEXT,                      -- JSON: status, reason, revised text
  say           TEXT,
  resolver      TEXT,
  event_id      INTEGER
);

CREATE TABLE IF NOT EXISTS fork (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER NOT NULL REFERENCES run(id),
  work_id       TEXT NOT NULL,
  anchor        TEXT,                      -- paragraph id, or 'work' for a global fork
  question      TEXT NOT NULL,
  options       TEXT NOT NULL,             -- JSON: [{author, text, tradeoff, case}]
  head_pick     INTEGER,
  head_reason   TEXT,
  decision      TEXT,                      -- the editor's, when it comes
  rule_id       INTEGER,
  status        TEXT NOT NULL DEFAULT 'open',
  event_id      INTEGER
);

CREATE TABLE IF NOT EXISTS rule (
  id            INTEGER PRIMARY KEY,
  work_id       TEXT,
  text          TEXT NOT NULL,
  scope         TEXT NOT NULL,             -- line / character / term / work / author / house
  scope_ref     TEXT,
  origin        TEXT,
  touched       TEXT,                      -- JSON list of segment ids
  status        TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS lock (
  work_id       TEXT NOT NULL,
  segment_id    TEXT NOT NULL,
  person        TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (work_id, segment_id)
);

CREATE TABLE IF NOT EXISTS status (
  work_id       TEXT NOT NULL,
  segment_id    TEXT NOT NULL,
  label         TEXT NOT NULL,             -- draft / house-checked / editor-approved / human-reviewed
  who           TEXT,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (work_id, segment_id)
);

-- Append-only log. The single source for history, the House stream and replay (house/events.py).
CREATE TABLE IF NOT EXISTS event (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER REFERENCES run(id),
  seq           INTEGER NOT NULL,          -- per run, from 1
  actor         TEXT NOT NULL,             -- 'analyst', 'translation/drafter', 'desk', 'editor', 'house'
  type          TEXT NOT NULL,             -- see house/events.py
  payload       TEXT NOT NULL,             -- JSON
  cost_usd      REAL NOT NULL DEFAULT 0,
  call_id       INTEGER REFERENCES call(id),
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS event_run ON event(run_id, seq);

-- The spend ledger: one row per model call, live or from the response cache.
CREATE TABLE IF NOT EXISTS call (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER,
  stage         TEXT,
  prompt        TEXT NOT NULL,             -- prompt file name
  model         TEXT NOT NULL,
  effort        TEXT,
  input_tokens  INTEGER NOT NULL DEFAULT 0,
  cached_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  reasoning_tokens INTEGER NOT NULL DEFAULT 0,
  web_searches  INTEGER NOT NULL DEFAULT 0,
  cost_usd      REAL NOT NULL DEFAULT 0,   -- what this call cost; 0 when served from the cache
  list_cost_usd REAL NOT NULL DEFAULT 0,   -- what it cost when it was first made
  from_cache    INTEGER NOT NULL DEFAULT 0,
  prompt_hash   TEXT NOT NULL,
  input_hash    TEXT NOT NULL,
  cache_key     TEXT,                      -- prompt_cache_key sent to the API
  response_key  TEXT NOT NULL,             -- key into the response cache
  response_id   TEXT,
  latency_s     REAL,
  ok            INTEGER NOT NULL DEFAULT 1,
  error         TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS intern (
  id            INTEGER PRIMARY KEY,
  run_id        INTEGER NOT NULL REFERENCES run(id),
  department    TEXT NOT NULL,
  question      TEXT NOT NULL,
  reason        TEXT NOT NULL,
  budget_usd    REAL,
  spend_usd     REAL,
  report        TEXT,
  event_id      INTEGER
);

CREATE TABLE IF NOT EXISTS person (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  trust         TEXT NOT NULL DEFAULT 'reader',
  credit_as     TEXT
);

CREATE TABLE IF NOT EXISTS allowance (
  id            INTEGER PRIMARY KEY,
  person_id     INTEGER NOT NULL REFERENCES person(id),
  drops_granted INTEGER NOT NULL DEFAULT 0,
  drops_reserved INTEGER NOT NULL DEFAULT 0,
  drops_spent   INTEGER NOT NULL DEFAULT 0,
  reason        TEXT
);

CREATE TABLE IF NOT EXISTS reaction (
  id            INTEGER PRIMARY KEY,
  target        TEXT NOT NULL,             -- 'bansan/p12', a note id, an alternative
  axis          TEXT NOT NULL,
  value         INTEGER NOT NULL,
  voter         TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proposal (
  id            INTEGER PRIMARY KEY,
  work_id       TEXT NOT NULL,
  segment_id    TEXT NOT NULL,
  span          TEXT,
  body          TEXT NOT NULL,
  screen        TEXT,                      -- JSON: pass / fail + reason
  query_id      INTEGER,
  person_id     INTEGER,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS report (
  work_id       TEXT PRIMARY KEY,
  public        TEXT NOT NULL,             -- JSON
  internal      TEXT,                      -- JSON
  basis         TEXT,
  label         TEXT,
  translation_status TEXT,
  checked_at    TEXT
);

CREATE TABLE IF NOT EXISTS edition (
  id            INTEGER PRIMARY KEY,
  work_id       TEXT NOT NULL REFERENCES work(id),
  editor        TEXT NOT NULL DEFAULT 'the house',
  current_release INTEGER
);

CREATE TABLE IF NOT EXISTS release (
  id            INTEGER PRIMARY KEY,
  edition_id    INTEGER NOT NULL REFERENCES edition(id),
  run_id        INTEGER REFERENCES run(id),
  version       TEXT NOT NULL,             -- v1, v1.1
  changelog     TEXT,
  credits       TEXT,                      -- JSON
  body          TEXT,                      -- JSON: the released editions
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vote (
  work_id       TEXT NOT NULL,
  voter         TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (work_id, voter)
);

CREATE TABLE IF NOT EXISTS request (
  id            INTEGER PRIMARY KEY,
  aozora_id     TEXT,
  reference     TEXT,                      -- JSON: title, author, link
  reason        TEXT,
  verdict       TEXT,                      -- eligible / in copyright / can't tell
  evidence      TEXT,
  decision      TEXT,
  status        TEXT NOT NULL DEFAULT 'new',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
