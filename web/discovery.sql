CREATE TABLE IF NOT EXISTS discovery_answers (
  submission_hash TEXT PRIMARY KEY NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('attribution','topic','contribution','none')),
  method TEXT CHECK(method IN ('spreadsheet','analytics','crm','manual','no_process')),
  role TEXT CHECK(role IN ('creator','marketing','agency','other')),
  received_day TEXT NOT NULL DEFAULT (date('now'))
);
