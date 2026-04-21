-- MIMIC-IV 3.1 schema + MIMIC-IV-Note 2.2 + EHRNoteQA

CREATE SCHEMA IF NOT EXISTS mimiciv_hosp;
CREATE SCHEMA IF NOT EXISTS mimiciv_icu;
CREATE SCHEMA IF NOT EXISTS mimiciv_note;
CREATE SCHEMA IF NOT EXISTS ehrqa;

-- ============================================================
-- mimiciv_hosp
-- ============================================================

CREATE TABLE mimiciv_hosp.patients (
    subject_id      INTEGER NOT NULL PRIMARY KEY,
    gender          CHAR(1),
    anchor_age      SMALLINT,
    anchor_year     SMALLINT,
    anchor_year_group TEXT,
    dod             DATE
);

CREATE TABLE mimiciv_hosp.admissions (
    subject_id          INTEGER NOT NULL,
    hadm_id             INTEGER NOT NULL PRIMARY KEY,
    admittime           TIMESTAMP NOT NULL,
    dischtime           TIMESTAMP,
    deathtime           TIMESTAMP,
    admission_type      TEXT,
    admit_provider_id   TEXT,
    admission_location  TEXT,
    discharge_location  TEXT,
    insurance           TEXT,
    language            TEXT,
    marital_status      TEXT,
    race                TEXT,
    edregtime           TIMESTAMP,
    edouttime           TIMESTAMP,
    hospital_expire_flag SMALLINT
);

CREATE TABLE mimiciv_hosp.transfers (
    subject_id  INTEGER NOT NULL,
    hadm_id     INTEGER,
    transfer_id INTEGER NOT NULL PRIMARY KEY,
    eventtype   TEXT,
    careunit    TEXT,
    intime      TIMESTAMP,
    outtime     TIMESTAMP
);

CREATE TABLE mimiciv_hosp.diagnoses_icd (
    subject_id  INTEGER NOT NULL,
    hadm_id     INTEGER NOT NULL,
    seq_num     SMALLINT NOT NULL,
    icd_code    TEXT NOT NULL,
    icd_version SMALLINT NOT NULL
);

CREATE TABLE mimiciv_hosp.d_icd_diagnoses (
    icd_code    TEXT NOT NULL,
    icd_version SMALLINT NOT NULL,
    long_title  TEXT,
    PRIMARY KEY (icd_code, icd_version)
);

CREATE TABLE mimiciv_hosp.procedures_icd (
    subject_id  INTEGER NOT NULL,
    hadm_id     INTEGER NOT NULL,
    seq_num     SMALLINT NOT NULL,
    chartdate   DATE,
    icd_code    TEXT NOT NULL,
    icd_version SMALLINT NOT NULL
);

CREATE TABLE mimiciv_hosp.d_icd_procedures (
    icd_code    TEXT NOT NULL,
    icd_version SMALLINT NOT NULL,
    long_title  TEXT,
    PRIMARY KEY (icd_code, icd_version)
);

CREATE TABLE mimiciv_hosp.services (
    subject_id    INTEGER NOT NULL,
    hadm_id       INTEGER NOT NULL,
    transfertime  TIMESTAMP NOT NULL,
    prev_service  TEXT,
    curr_service  TEXT
);

CREATE TABLE mimiciv_hosp.labevents (
    labevent_id      BIGINT NOT NULL PRIMARY KEY,
    subject_id       INTEGER NOT NULL,
    hadm_id          INTEGER,
    specimen_id      INTEGER NOT NULL,
    itemid           INTEGER NOT NULL,
    order_provider_id TEXT,
    charttime        TIMESTAMP,
    storetime        TIMESTAMP,
    value            TEXT,
    valuenum         DOUBLE PRECISION,
    valueuom         TEXT,
    ref_range_lower  DOUBLE PRECISION,
    ref_range_upper  DOUBLE PRECISION,
    flag             TEXT,
    priority         TEXT,
    comments         TEXT
);

CREATE TABLE mimiciv_hosp.d_labitems (
    itemid   INTEGER NOT NULL PRIMARY KEY,
    label    TEXT,
    fluid    TEXT,
    category TEXT
);

CREATE TABLE mimiciv_hosp.microbiologyevents (
    microevent_id        BIGINT NOT NULL PRIMARY KEY,
    subject_id           INTEGER NOT NULL,
    hadm_id              INTEGER,
    micro_specimen_id    INTEGER NOT NULL,
    order_provider_id    TEXT,
    chartdate            DATE,
    charttime            TIMESTAMP,
    spec_itemid          INTEGER,
    spec_type_desc       TEXT,
    test_seq             SMALLINT,
    storedate            DATE,
    storetime            TIMESTAMP,
    test_itemid          INTEGER,
    test_name            TEXT,
    org_itemid           INTEGER,
    org_name             TEXT,
    isolate_num          SMALLINT,
    quantity             TEXT,
    ab_itemid            INTEGER,
    ab_name              TEXT,
    dilution_text        TEXT,
    dilution_comparison  TEXT,
    dilution_value       DOUBLE PRECISION,
    interpretation       TEXT,
    comments             TEXT
);

CREATE TABLE mimiciv_hosp.pharmacy (
    subject_id          INTEGER NOT NULL,
    hadm_id             INTEGER NOT NULL,
    pharmacy_id         INTEGER NOT NULL PRIMARY KEY,
    poe_id              TEXT,
    starttime           TIMESTAMP,
    stoptime            TIMESTAMP,
    medication          TEXT,
    proc_type           TEXT,
    status              TEXT,
    entertime           TIMESTAMP,
    verifiedtime        TIMESTAMP,
    route               TEXT,
    frequency           TEXT,
    disp_sched          TEXT,
    infusion_type       TEXT,
    sliding_scale       TEXT,
    lockout_interval    TEXT,
    basal_rate          DOUBLE PRECISION,
    one_hr_max          TEXT,
    doses_per_24_hrs    DOUBLE PRECISION,
    duration            DOUBLE PRECISION,
    duration_interval   TEXT,
    expiration_value    DOUBLE PRECISION,
    expiration_unit     TEXT,
    expirationdate      TIMESTAMP,
    dispensation        TEXT,
    fill_quantity       TEXT
);

CREATE TABLE mimiciv_hosp.prescriptions (
    subject_id          INTEGER NOT NULL,
    hadm_id             INTEGER NOT NULL,
    pharmacy_id         INTEGER,
    poe_id              TEXT,
    poe_seq             INTEGER,
    order_provider_id   TEXT,
    starttime           TIMESTAMP,
    stoptime            TIMESTAMP,
    drug_type           TEXT,
    drug                TEXT,
    formulary_drug_cd   TEXT,
    gsn                 TEXT,
    ndc                 TEXT,
    prod_strength       TEXT,
    form_rx             TEXT,
    dose_val_rx         TEXT,
    dose_unit_rx        TEXT,
    form_val_disp       TEXT,
    form_unit_disp      TEXT,
    doses_per_24_hrs    DOUBLE PRECISION,
    route               TEXT
);

CREATE TABLE mimiciv_hosp.emar (
    subject_id          INTEGER NOT NULL,
    hadm_id             INTEGER,
    emar_id             TEXT NOT NULL PRIMARY KEY,
    emar_seq            INTEGER NOT NULL,
    poe_id              TEXT,
    pharmacy_id         INTEGER,
    enter_provider_id   TEXT,
    charttime           TIMESTAMP,
    medication          TEXT,
    event_txt           TEXT,
    scheduletime        TIMESTAMP,
    storetime           TIMESTAMP
);

CREATE TABLE mimiciv_hosp.emar_detail (
    subject_id                          INTEGER NOT NULL,
    emar_id                             TEXT NOT NULL,
    emar_seq                            INTEGER NOT NULL,
    parent_field_ordinal                TEXT,
    administration_type                 TEXT,
    pharmacy_id                         INTEGER,
    barcode_type                        TEXT,
    reason_for_no_barcode               TEXT,
    complete_dose_not_given             TEXT,
    dose_due                            TEXT,
    dose_due_unit                       TEXT,
    dose_given                          TEXT,
    dose_given_unit                     TEXT,
    will_remainder_of_dose_be_given     TEXT,
    product_amount_given                TEXT,
    product_unit                        TEXT,
    product_code                        TEXT,
    product_description                 TEXT,
    product_description_other           TEXT,
    prior_infusion_rate                 TEXT,
    infusion_rate                       TEXT,
    infusion_rate_adjustment            TEXT,
    infusion_rate_adjustment_amount     TEXT,
    infusion_rate_unit                  TEXT,
    route                               TEXT,
    infusion_complete                   TEXT,
    completion_interval                 TEXT,
    new_iv_bag_hung                     TEXT,
    continued_infusion_in_other_location TEXT,
    restart_interval                    TEXT,
    side                                TEXT,
    site                                TEXT,
    non_formulary_visual_verification   TEXT
);

CREATE TABLE mimiciv_hosp.poe (
    poe_id                  TEXT NOT NULL PRIMARY KEY,
    poe_seq                 INTEGER NOT NULL,
    subject_id              INTEGER NOT NULL,
    hadm_id                 INTEGER,
    ordertime               TIMESTAMP NOT NULL,
    order_type              TEXT,
    order_subtype           TEXT,
    transaction_type        TEXT,
    discontinue_of_poe_id   TEXT,
    discontinued_by_poe_id  TEXT,
    order_provider_id       TEXT,
    order_status            TEXT
);

CREATE TABLE mimiciv_hosp.poe_detail (
    poe_id      TEXT NOT NULL,
    poe_seq     INTEGER NOT NULL,
    subject_id  INTEGER NOT NULL,
    field_name  TEXT NOT NULL,
    field_value TEXT
);

CREATE TABLE mimiciv_hosp.drgcodes (
    subject_id   INTEGER NOT NULL,
    hadm_id      INTEGER NOT NULL,
    drg_type     TEXT,
    drg_code     TEXT,
    description  TEXT,
    drg_severity SMALLINT,
    drg_mortality SMALLINT
);

CREATE TABLE mimiciv_hosp.hcpcsevents (
    subject_id        INTEGER NOT NULL,
    hadm_id           INTEGER NOT NULL,
    chartdate         DATE,
    hcpcs_cd          TEXT,
    seq_num           SMALLINT,
    short_description TEXT
);

CREATE TABLE mimiciv_hosp.d_hcpcs (
    code              TEXT NOT NULL PRIMARY KEY,
    category          TEXT,
    long_description  TEXT,
    short_description TEXT
);

CREATE TABLE mimiciv_hosp.omr (
    subject_id   INTEGER NOT NULL,
    chartdate    DATE NOT NULL,
    seq_num      INTEGER NOT NULL,
    result_name  TEXT NOT NULL,
    result_value TEXT
);

CREATE TABLE mimiciv_hosp.provider (
    provider_id TEXT NOT NULL PRIMARY KEY
);

-- ============================================================
-- mimiciv_icu
-- ============================================================

CREATE TABLE mimiciv_icu.icustays (
    subject_id      INTEGER NOT NULL,
    hadm_id         INTEGER NOT NULL,
    stay_id         INTEGER NOT NULL PRIMARY KEY,
    first_careunit  TEXT,
    last_careunit   TEXT,
    intime          TIMESTAMP NOT NULL,
    outtime         TIMESTAMP,
    los             DOUBLE PRECISION
);

CREATE TABLE mimiciv_icu.caregiver (
    caregiver_id INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE mimiciv_icu.d_items (
    itemid          INTEGER NOT NULL PRIMARY KEY,
    label           TEXT,
    abbreviation    TEXT,
    linksto         TEXT,
    category        TEXT,
    unitname        TEXT,
    param_type      TEXT,
    lownormalvalue  DOUBLE PRECISION,
    highnormalvalue DOUBLE PRECISION
);

CREATE TABLE mimiciv_icu.chartevents (
    subject_id   INTEGER NOT NULL,
    hadm_id      INTEGER NOT NULL,
    stay_id      INTEGER NOT NULL,
    caregiver_id INTEGER,
    charttime    TIMESTAMP NOT NULL,
    storetime    TIMESTAMP,
    itemid       INTEGER NOT NULL,
    value        TEXT,
    valuenum     DOUBLE PRECISION,
    valueuom     TEXT,
    warning      SMALLINT
);

CREATE TABLE mimiciv_icu.datetimeevents (
    subject_id   INTEGER NOT NULL,
    hadm_id      INTEGER NOT NULL,
    stay_id      INTEGER NOT NULL,
    caregiver_id INTEGER,
    charttime    TIMESTAMP NOT NULL,
    storetime    TIMESTAMP,
    itemid       INTEGER NOT NULL,
    value        TIMESTAMP,
    valueuom     TEXT,
    warning      SMALLINT
);

CREATE TABLE mimiciv_icu.inputevents (
    subject_id                      INTEGER NOT NULL,
    hadm_id                         INTEGER NOT NULL,
    stay_id                         INTEGER NOT NULL,
    caregiver_id                    INTEGER,
    starttime                       TIMESTAMP NOT NULL,
    endtime                         TIMESTAMP,
    storetime                       TIMESTAMP,
    itemid                          INTEGER NOT NULL,
    amount                          DOUBLE PRECISION,
    amountuom                       TEXT,
    rate                            DOUBLE PRECISION,
    rateuom                         TEXT,
    orderid                         BIGINT,
    linkorderid                     BIGINT,
    ordercategoryname               TEXT,
    secondaryordercategoryname      TEXT,
    ordercomponenttypedescription   TEXT,
    ordercategorydescription        TEXT,
    patientweight                   DOUBLE PRECISION,
    totalamount                     DOUBLE PRECISION,
    totalamountuom                  TEXT,
    isopenbag                       SMALLINT,
    continueinnextdept              SMALLINT,
    statusdescription               TEXT,
    originalamount                  DOUBLE PRECISION,
    originalrate                    DOUBLE PRECISION
);

CREATE TABLE mimiciv_icu.outputevents (
    subject_id   INTEGER NOT NULL,
    hadm_id      INTEGER NOT NULL,
    stay_id      INTEGER NOT NULL,
    caregiver_id INTEGER,
    charttime    TIMESTAMP NOT NULL,
    storetime    TIMESTAMP,
    itemid       INTEGER NOT NULL,
    value        DOUBLE PRECISION,
    valueuom     TEXT
);

CREATE TABLE mimiciv_icu.procedureevents (
    subject_id                  INTEGER NOT NULL,
    hadm_id                     INTEGER NOT NULL,
    stay_id                     INTEGER NOT NULL,
    caregiver_id                INTEGER,
    starttime                   TIMESTAMP NOT NULL,
    endtime                     TIMESTAMP,
    storetime                   TIMESTAMP,
    itemid                      INTEGER NOT NULL,
    value                       DOUBLE PRECISION,
    valueuom                    TEXT,
    location                    TEXT,
    locationcategory            TEXT,
    orderid                     BIGINT,
    linkorderid                 BIGINT,
    ordercategoryname           TEXT,
    ordercategorydescription    TEXT,
    patientweight               DOUBLE PRECISION,
    isopenbag                   SMALLINT,
    continueinnextdept          SMALLINT,
    statusdescription           TEXT,
    originalamount              DOUBLE PRECISION,
    originalrate                DOUBLE PRECISION
);

CREATE TABLE mimiciv_icu.ingredientevents (
    subject_id      INTEGER NOT NULL,
    hadm_id         INTEGER NOT NULL,
    stay_id         INTEGER NOT NULL,
    caregiver_id    INTEGER,
    starttime       TIMESTAMP NOT NULL,
    endtime         TIMESTAMP,
    storetime       TIMESTAMP,
    itemid          INTEGER NOT NULL,
    amount          DOUBLE PRECISION,
    amountuom       TEXT,
    rate            DOUBLE PRECISION,
    rateuom         TEXT,
    orderid         BIGINT,
    linkorderid     BIGINT,
    statusdescription TEXT,
    originalamount  DOUBLE PRECISION,
    originalrate    DOUBLE PRECISION
);

-- ============================================================
-- mimiciv_note
-- ============================================================

CREATE TABLE mimiciv_note.discharge (
    note_id     TEXT NOT NULL PRIMARY KEY,
    subject_id  INTEGER NOT NULL,
    hadm_id     INTEGER,
    note_type   TEXT,
    note_seq    INTEGER,
    charttime   TIMESTAMP,
    storetime   TIMESTAMP,
    text        TEXT
);

CREATE TABLE mimiciv_note.discharge_detail (
    note_id         TEXT NOT NULL,
    subject_id      INTEGER NOT NULL,
    field_name      TEXT,
    field_value     TEXT,
    field_ordinal   DOUBLE PRECISION
);

CREATE TABLE mimiciv_note.radiology (
    note_id     TEXT NOT NULL PRIMARY KEY,
    subject_id  INTEGER NOT NULL,
    hadm_id     INTEGER,
    note_type   TEXT,
    note_seq    INTEGER,
    charttime   TIMESTAMP,
    storetime   TIMESTAMP,
    text        TEXT
);

CREATE TABLE mimiciv_note.radiology_detail (
    note_id         TEXT NOT NULL,
    subject_id      INTEGER NOT NULL,
    field_name      TEXT,
    field_value     TEXT,
    field_ordinal   DOUBLE PRECISION
);

-- ============================================================
-- ehrqa
-- ============================================================

CREATE TABLE ehrqa.questions (
    id          SERIAL PRIMARY KEY,
    patient_id  INTEGER NOT NULL,
    category    TEXT,
    num_notes   INTEGER,
    clinician   TEXT,
    question    TEXT,
    choice_a    TEXT,
    choice_b    TEXT,
    choice_c    TEXT,
    choice_d    TEXT,
    choice_e    TEXT,
    answer      CHAR(1)
);

-- ============================================================
-- Indexes (added after load for performance)
-- ============================================================

-- Core FK-path indexes
CREATE INDEX ON mimiciv_hosp.admissions (subject_id);
CREATE INDEX ON mimiciv_hosp.transfers (subject_id);
CREATE INDEX ON mimiciv_hosp.diagnoses_icd (subject_id, hadm_id);
CREATE INDEX ON mimiciv_hosp.procedures_icd (subject_id, hadm_id);
CREATE INDEX ON mimiciv_hosp.labevents (subject_id);
CREATE INDEX ON mimiciv_hosp.labevents (hadm_id);
CREATE INDEX ON mimiciv_hosp.labevents (itemid);
CREATE INDEX ON mimiciv_hosp.microbiologyevents (subject_id);
CREATE INDEX ON mimiciv_hosp.pharmacy (subject_id, hadm_id);
CREATE INDEX ON mimiciv_hosp.prescriptions (subject_id, hadm_id);
CREATE INDEX ON mimiciv_hosp.emar (subject_id);
CREATE INDEX ON mimiciv_hosp.emar_detail (emar_id);
CREATE INDEX ON mimiciv_hosp.poe (subject_id, hadm_id);
CREATE INDEX ON mimiciv_hosp.poe_detail (poe_id);
CREATE INDEX ON mimiciv_hosp.drgcodes (subject_id, hadm_id);
CREATE INDEX ON mimiciv_hosp.omr (subject_id);
CREATE INDEX ON mimiciv_icu.icustays (subject_id, hadm_id);
CREATE INDEX ON mimiciv_icu.chartevents (subject_id, stay_id);
CREATE INDEX ON mimiciv_icu.chartevents (itemid);
CREATE INDEX ON mimiciv_icu.inputevents (subject_id, stay_id);
CREATE INDEX ON mimiciv_icu.outputevents (subject_id, stay_id);
CREATE INDEX ON mimiciv_icu.procedureevents (subject_id, stay_id);
CREATE INDEX ON mimiciv_icu.ingredientevents (subject_id, stay_id);
CREATE INDEX ON ehrqa.questions (patient_id);
CREATE INDEX ON mimiciv_note.discharge (subject_id);
CREATE INDEX ON mimiciv_note.discharge (hadm_id);
CREATE INDEX ON mimiciv_note.discharge_detail (note_id);
CREATE INDEX ON mimiciv_note.radiology (subject_id);
CREATE INDEX ON mimiciv_note.radiology_detail (note_id);

-- ============================================================
-- pgvector + RAG chunks
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS mimiciv_note.chunks (
    chunk_id     SERIAL PRIMARY KEY,
    subject_id   INTEGER NOT NULL,
    note_id      TEXT NOT NULL,
    source_table TEXT NOT NULL,
    section_name TEXT,
    chunk_text   TEXT NOT NULL,
    embedding    vector(1024)
);

CREATE INDEX IF NOT EXISTS chunks_subject_id_idx ON mimiciv_note.chunks (subject_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON mimiciv_note.chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
