#!/usr/bin/env bash
# Loads MIMIC-IV CSVs, MIMIC-IV-Note, and EHRNoteQA into the mimiciv Postgres container.
# Run from the repo root after `docker compose up -d`.
#
# Usage:
#   ./src/db/load_data.sh [--slim] [MIMIC_DIR] [EHRQA_FILE] [NOTE_DIR]
#
# --slim  Skips large event tables not needed for EHRNoteQA benchmarking:
#         chartevents, labevents, emar, emar_detail, poe, poe_detail, pharmacy
#         Reduces load time from ~2 hours to ~20 minutes and disk from ~80GB to ~12GB.
#
# Defaults:
#   MIMIC_DIR  = ~/Projects/ai-in-healthcare/mimiciv/3.1
#   EHRQA_FILE = ~/Projects/ai-in-healthcare/EHRNoteQA.jsonl
#   NOTE_DIR   = ~/Projects/ai-in-healthcare/mimiciv/physionet.org/files/mimic-iv-note/2.2/note

set -euo pipefail

SLIM=false
POSITIONAL=()
for arg in "$@"; do
  if [[ "$arg" == "--slim" ]]; then
    SLIM=true
  else
    POSITIONAL+=("$arg")
  fi
done

MIMIC_DIR="${POSITIONAL[0]:-$HOME/Projects/ai-in-healthcare/mimiciv/3.1}"
EHRQA_FILE="${POSITIONAL[1]:-$HOME/Projects/ai-in-healthcare/EHRNoteQA.jsonl}"
NOTE_DIR="${POSITIONAL[2]:-$HOME/Projects/ai-in-healthcare/mimiciv/physionet.org/files/mimic-iv-note/2.2/note}"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-mimiciv}"
PGPASSWORD="${PGPASSWORD:-mimiciv}"
PGDATABASE="${PGDATABASE:-mimiciv}"
export PGPASSWORD

PSQL="psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE"

echo "Waiting for Postgres..."
until $PSQL -c '\q' 2>/dev/null; do
  sleep 2
done
echo "Postgres is ready."
$SLIM && echo "Mode: slim (skipping chartevents, labevents, emar, emar_detail, poe, poe_detail, pharmacy)" || echo "Mode: full"

copy_gz() {
  local file="$1"
  local table="$2"
  echo "  Loading $(basename "$file") -> $table"
  gzip -dc "$file" | $PSQL -c "\COPY $table FROM STDIN CSV HEADER"
}

echo ""
echo "=== mimiciv_hosp ==="

copy_gz "$MIMIC_DIR/hosp/patients.csv.gz"           mimiciv_hosp.patients
copy_gz "$MIMIC_DIR/hosp/admissions.csv.gz"         mimiciv_hosp.admissions
copy_gz "$MIMIC_DIR/hosp/transfers.csv.gz"          mimiciv_hosp.transfers
copy_gz "$MIMIC_DIR/hosp/provider.csv.gz"           mimiciv_hosp.provider
copy_gz "$MIMIC_DIR/hosp/d_icd_diagnoses.csv.gz"    mimiciv_hosp.d_icd_diagnoses
copy_gz "$MIMIC_DIR/hosp/d_icd_procedures.csv.gz"   mimiciv_hosp.d_icd_procedures
copy_gz "$MIMIC_DIR/hosp/d_hcpcs.csv.gz"            mimiciv_hosp.d_hcpcs
copy_gz "$MIMIC_DIR/hosp/d_labitems.csv.gz"         mimiciv_hosp.d_labitems
copy_gz "$MIMIC_DIR/hosp/diagnoses_icd.csv.gz"      mimiciv_hosp.diagnoses_icd
copy_gz "$MIMIC_DIR/hosp/procedures_icd.csv.gz"     mimiciv_hosp.procedures_icd
copy_gz "$MIMIC_DIR/hosp/services.csv.gz"           mimiciv_hosp.services
copy_gz "$MIMIC_DIR/hosp/drgcodes.csv.gz"           mimiciv_hosp.drgcodes
copy_gz "$MIMIC_DIR/hosp/hcpcsevents.csv.gz"        mimiciv_hosp.hcpcsevents
copy_gz "$MIMIC_DIR/hosp/omr.csv.gz"                mimiciv_hosp.omr
copy_gz "$MIMIC_DIR/hosp/microbiologyevents.csv.gz" mimiciv_hosp.microbiologyevents
copy_gz "$MIMIC_DIR/hosp/prescriptions.csv.gz"      mimiciv_hosp.prescriptions

if ! $SLIM; then
  copy_gz "$MIMIC_DIR/hosp/poe.csv.gz"              mimiciv_hosp.poe
  copy_gz "$MIMIC_DIR/hosp/poe_detail.csv.gz"       mimiciv_hosp.poe_detail
  copy_gz "$MIMIC_DIR/hosp/pharmacy.csv.gz"         mimiciv_hosp.pharmacy
  copy_gz "$MIMIC_DIR/hosp/emar.csv.gz"             mimiciv_hosp.emar
  copy_gz "$MIMIC_DIR/hosp/emar_detail.csv.gz"      mimiciv_hosp.emar_detail
  copy_gz "$MIMIC_DIR/hosp/labevents.csv.gz"        mimiciv_hosp.labevents
fi

echo ""
echo "=== mimiciv_icu ==="

copy_gz "$MIMIC_DIR/icu/caregiver.csv.gz"           mimiciv_icu.caregiver
copy_gz "$MIMIC_DIR/icu/d_items.csv.gz"             mimiciv_icu.d_items
copy_gz "$MIMIC_DIR/icu/icustays.csv.gz"            mimiciv_icu.icustays
copy_gz "$MIMIC_DIR/icu/datetimeevents.csv.gz"      mimiciv_icu.datetimeevents
copy_gz "$MIMIC_DIR/icu/outputevents.csv.gz"        mimiciv_icu.outputevents
copy_gz "$MIMIC_DIR/icu/procedureevents.csv.gz"     mimiciv_icu.procedureevents
copy_gz "$MIMIC_DIR/icu/ingredientevents.csv.gz"    mimiciv_icu.ingredientevents
copy_gz "$MIMIC_DIR/icu/inputevents.csv.gz"         mimiciv_icu.inputevents

if ! $SLIM; then
  copy_gz "$MIMIC_DIR/icu/chartevents.csv.gz"       mimiciv_icu.chartevents
fi

echo ""
echo "=== mimiciv_note ==="

copy_gz "$NOTE_DIR/discharge.csv.gz"         mimiciv_note.discharge
copy_gz "$NOTE_DIR/discharge_detail.csv.gz"  mimiciv_note.discharge_detail
copy_gz "$NOTE_DIR/radiology.csv.gz"         mimiciv_note.radiology
copy_gz "$NOTE_DIR/radiology_detail.csv.gz"  mimiciv_note.radiology_detail

echo ""
echo "=== ehrqa ==="

echo "  Loading EHRNoteQA.jsonl -> ehrqa.questions"
python3 - "$EHRQA_FILE" <<'PYEOF'
import sys, json, csv, io, subprocess, os

ehrqa_file = sys.argv[1]

rows = []
with open(ehrqa_file) as f:
    for line in f:
        r = json.loads(line)
        rows.append([
            r.get("patient_id"),
            r.get("category"),
            r.get("num_notes"),
            r.get("clinician"),
            r.get("question"),
            r.get("choice_A"),
            r.get("choice_B"),
            r.get("choice_C"),
            r.get("choice_D"),
            r.get("choice_E"),
            r.get("answer"),
        ])

buf = io.StringIO()
writer = csv.writer(buf)
writer.writerows(rows)
csv_data = buf.getvalue().encode()

cols = "patient_id,category,num_notes,clinician,question,choice_a,choice_b,choice_c,choice_d,choice_e,answer"
cmd = [
    "psql",
    "-h", os.environ.get("PGHOST", "localhost"),
    "-p", os.environ.get("PGPORT", "5432"),
    "-U", os.environ.get("PGUSER", "mimiciv"),
    "-d", os.environ.get("PGDATABASE", "mimiciv"),
    "-c", f"\\COPY ehrqa.questions ({cols}) FROM STDIN CSV",
]
result = subprocess.run(cmd, input=csv_data, env={**os.environ})
sys.exit(result.returncode)
PYEOF

echo ""
echo "All done. Row counts:"
$PSQL -c "
SELECT schemaname, tablename,
       (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM '||schemaname||'.'||tablename, false, true, '')))[1]::text::int AS rows
FROM pg_tables
WHERE schemaname IN ('mimiciv_hosp','mimiciv_icu','mimiciv_note','ehrqa')
ORDER BY schemaname, tablename;
"
