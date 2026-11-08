CREATE TABLE IF NOT EXISTS reader_registrations (
  id TEXT PRIMARY KEY,
  session_hash TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  organization TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('expert', 'vendor', 'other')),
  field TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  allow_contact INTEGER NOT NULL DEFAULT 0 CHECK (allow_contact IN (0, 1)),
  consent_version TEXT NOT NULL,
  consented_at TEXT NOT NULL,
  international_consent_at TEXT NOT NULL,
  entry_path TEXT NOT NULL,
  document_sha TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  read_confirmed_at TEXT,
  read_document_sha TEXT
);
CREATE INDEX IF NOT EXISTS reader_registrations_created ON reader_registrations(created_at DESC);
CREATE INDEX IF NOT EXISTS reader_registrations_expiry ON reader_registrations(expires_at);
