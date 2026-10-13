-- Nova Bank practice database. ALL DATA IS FAKE.
-- Running this file deletes and recreates every table.

CREATE EXTENSION IF NOT EXISTS vector;   -- used later for the knowledge base

DROP TABLE IF EXISTS call_log, disputes, tickets, transfers, loans,
                     transactions, cards, accounts, customers CASCADE;

CREATE TABLE customers (
  customer_id       TEXT PRIMARY KEY,          -- 5 digits, easy to say on a call
  full_name         TEXT NOT NULL,
  date_of_birth     DATE NOT NULL,
  phone             TEXT NOT NULL,
  email             TEXT NOT NULL,
  address           TEXT NOT NULL,
  city              TEXT NOT NULL,
  state             TEXT NOT NULL,
  security_question TEXT NOT NULL,
  security_answer   TEXT NOT NULL,             -- single lowercase word
  kyc_status        TEXT NOT NULL,             -- verified | pending | expired
  customer_since    DATE NOT NULL
);

CREATE TABLE accounts (
  account_id      TEXT PRIMARY KEY,
  customer_id     TEXT NOT NULL REFERENCES customers,
  account_type    TEXT NOT NULL,               -- checking | savings
  last4           TEXT NOT NULL,               -- only last 4 digits are ever stored
  balance         NUMERIC(12,2) NOT NULL,
  currency        TEXT NOT NULL DEFAULT 'USD',
  status          TEXT NOT NULL,               -- active | frozen | dormant
  status_reason   TEXT,
  overdraft_limit NUMERIC(12,2) NOT NULL DEFAULT 0,
  interest_rate   NUMERIC(5,2) NOT NULL DEFAULT 0,
  opened_on       DATE NOT NULL
);
CREATE INDEX ON accounts (customer_id);

CREATE TABLE cards (
  card_id         TEXT PRIMARY KEY,
  customer_id     TEXT NOT NULL REFERENCES customers,
  account_id      TEXT REFERENCES accounts,    -- NULL for credit cards
  card_type       TEXT NOT NULL,               -- debit | credit
  last4           TEXT NOT NULL,
  status          TEXT NOT NULL,               -- active | blocked | lost | expired
  expiry          DATE NOT NULL,
  daily_limit     NUMERIC(12,2),
  credit_limit    NUMERIC(12,2),
  outstanding     NUMERIC(12,2),
  minimum_payment NUMERIC(12,2),
  payment_due     DATE
);
CREATE INDEX ON cards (customer_id);

CREATE TABLE transactions (
  txn_id      TEXT PRIMARY KEY,
  account_id  TEXT NOT NULL REFERENCES accounts,
  txn_time    TIMESTAMP NOT NULL,
  description TEXT NOT NULL,
  category    TEXT NOT NULL,
  amount      NUMERIC(12,2) NOT NULL,          -- negative = money out
  channel     TEXT NOT NULL,                   -- card | atm | direct_deposit | direct_debit | transfer | interest | fee
  status      TEXT NOT NULL                    -- posted | pending | disputed
);
CREATE INDEX ON transactions (account_id, txn_time DESC);

CREATE TABLE loans (
  loan_id           TEXT PRIMARY KEY,
  customer_id       TEXT NOT NULL REFERENCES customers,
  loan_type         TEXT NOT NULL,             -- personal | auto | home
  principal         NUMERIC(12,2) NOT NULL,
  interest_rate     NUMERIC(5,2) NOT NULL,     -- yearly %
  term_months       INT NOT NULL,
  monthly_payment   NUMERIC(12,2) NOT NULL,
  remaining_balance NUMERIC(12,2) NOT NULL,
  start_date        DATE NOT NULL,
  next_due_date     DATE,
  status            TEXT NOT NULL,             -- current | late | paid_off
  days_past_due     INT NOT NULL DEFAULT 0
);
CREATE INDEX ON loans (customer_id);

CREATE TABLE transfers (
  transfer_id         TEXT PRIMARY KEY,
  from_account_id     TEXT NOT NULL REFERENCES accounts,
  transfer_type       TEXT NOT NULL,           -- domestic | international
  beneficiary_name    TEXT NOT NULL,
  beneficiary_bank    TEXT NOT NULL,
  amount              NUMERIC(12,2) NOT NULL,
  fee                 NUMERIC(12,2) NOT NULL DEFAULT 0,
  initiated_at        TIMESTAMP NOT NULL,
  expected_completion DATE NOT NULL,
  status              TEXT NOT NULL,           -- processing | completed | failed | returned | compliance_hold
  failure_reason      TEXT
);
CREATE INDEX ON transfers (from_account_id);

CREATE TABLE tickets (
  ticket_id   SERIAL PRIMARY KEY,
  customer_id TEXT REFERENCES customers,       -- NULL if caller was not verified
  category    TEXT NOT NULL,
  priority    TEXT NOT NULL DEFAULT 'normal',  -- low | normal | high | urgent
  description TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'open',    -- open | in_progress | resolved
  created_at  TIMESTAMP NOT NULL DEFAULT now(),
  resolution  TEXT
);

CREATE TABLE disputes (
  dispute_id  SERIAL PRIMARY KEY,
  txn_id      TEXT NOT NULL REFERENCES transactions,
  customer_id TEXT NOT NULL REFERENCES customers,
  reason      TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'submitted',
  created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE call_log (
  id           SERIAL PRIMARY KEY,
  caller       TEXT,
  customer_id  TEXT,
  summary      TEXT,
  ended_reason TEXT,
  duration_sec INT,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);
