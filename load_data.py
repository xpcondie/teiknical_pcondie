import sqlite3
import pandas as pd
from config import CSV_PATH, DB_PATH

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  TEXT    NOT NULL UNIQUE,
    project_id  TEXT    NOT NULL,
    condition   TEXT,
    age         INTEGER,
    sex         TEXT,
    treatment   TEXT,
    response    INTEGER CHECK (response IN (0, 1, NULL))
);

CREATE TABLE IF NOT EXISTS samples (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id                 TEXT    NOT NULL UNIQUE,
    subject_fk                TEXT    NOT NULL REFERENCES subjects(id),
    sample_type               TEXT,
    time_from_treatment_start INTEGER
);

CREATE TABLE IF NOT EXISTS cell_counts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_fk   INTEGER NOT NULL REFERENCES samples(id),
    cell_type   TEXT,
    cell_count  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_subjects_condition ON subjects(condition);
CREATE INDEX IF NOT EXISTS idx_subjects_treatment ON subjects(treatment);
CREATE INDEX IF NOT EXISTS idx_samples_time_from_treatment_start ON samples(time_from_treatment_start);
CREATE INDEX IF NOT EXISTS idx_cell_counts_cell_type ON cell_counts(cell_type);
"""

SUBJECT_COLS = ["subject_id", "project_id", "condition", "age", "sex", "treatment", "response"]
SAMPLE_COLS =  ["sample_id", "subject_id", "sample_type", "time_from_treatment_start"]
CELL_COLS   =  ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# create the .db
def load(csv_path, db_path) -> None:
    print(f"Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    # this rename is mostly for clarity to maintain the natural keys for future reference
    df.rename(columns={"project": "project_id", "subject": "subject_id", "sample": "sample_id"}, inplace=True)

    # validate expected columns are present
    expected = set(SUBJECT_COLS + SAMPLE_COLS + CELL_COLS)
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing expected columns: {missing}")

    # change response cl to boolean, preserve nulls
    def parse_response(v):
        if pd.isna(v):
            return None
        return 1 if str(v).strip().lower() in ("1", "true", "yes") else 0
 
    df["response"] = df["response"].map(parse_response)

    print(f"Rows: {len(df)}  |  Subjects: {df['subject_id'].nunique()}  |  Samples: {df['sample_id'].nunique()}")

    # --- connect and create schema ---
    print(f"\nCreating database: {db_path}")
    con = sqlite3.connect(db_path)
    con.executescript(DDL)
    con.commit()

    # --- subjects table ---
    subjects_df = df[SUBJECT_COLS].drop_duplicates(subset=["subject_id"])
    subjects_df.to_sql("subjects", con, if_exists="append", index=False)
    print(f"Inserted {len(subjects_df)} subjects.")

    # --- samples table ---
    subject_id_to_fk = pd.read_sql("SELECT id AS subject_fk, subject_id FROM subjects", con)
    samples_df = (
        df[SAMPLE_COLS]
        .drop_duplicates(subset=["sample_id"])
        .merge(subject_id_to_fk, on="subject_id")
        .drop(columns=["subject_id"])
    )
    samples_df.to_sql("samples", con, if_exists="append", index=False)
    print(f"Inserted {len(samples_df)} samples.")

    # --- cell_counts table, long format ---
    sample_id_to_fk = pd.read_sql("SELECT id AS sample_fk, sample_id FROM samples", con)
    counts_df = (
        df[["sample_id"] + CELL_COLS]
        .drop_duplicates(subset=["sample_id"])
        .merge(sample_id_to_fk, on="sample_id")
        .drop(columns=["sample_id"])
        .melt(id_vars=["sample_fk"], var_name="cell_type", value_name="cell_count")
    )
    counts_df.to_sql("cell_counts", con, if_exists="append", index=False)
    print(f"Inserted {len(counts_df)} cell_count rows.")

    con.commit()
    con.close()
    print("\nDone. Database ready.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load(CSV_PATH, DB_PATH)