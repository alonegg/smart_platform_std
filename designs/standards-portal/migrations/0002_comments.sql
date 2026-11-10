CREATE TABLE IF NOT EXISTS review_comments (
  id TEXT PRIMARY KEY,
  ref TEXT NOT NULL UNIQUE,
  round INTEGER NOT NULL,
  clause TEXT NOT NULL,
  section_key TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('vendor', 'expert', 'school', 'other')),
  profile TEXT NOT NULL DEFAULT '',
  problem TEXT NOT NULL,
  proposal TEXT NOT NULL DEFAULT '',
  rationale TEXT NOT NULL DEFAULT '',
  submitter TEXT NOT NULL DEFAULT '',
  organization TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  allow_public INTEGER NOT NULL DEFAULT 0 CHECK (allow_public IN (0, 1)),
  document_sha TEXT NOT NULL,
  session_hash TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  disposition TEXT NOT NULL DEFAULT 'pending'
    CHECK (disposition IN ('pending', 'accepted', 'partial', 'rejected', 'deferred')),
  response TEXT NOT NULL DEFAULT '',
  public_summary TEXT NOT NULL DEFAULT '',
  responded_at TEXT
);
CREATE INDEX IF NOT EXISTS review_comments_created ON review_comments(created_at DESC);
CREATE INDEX IF NOT EXISTS review_comments_session ON review_comments(session_hash);
