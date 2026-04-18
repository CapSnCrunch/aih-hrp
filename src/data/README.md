# Local data layout

Downloaded datasets live under this directory. **Only** `README.md`, the two `.gitkeep` files, and empty directory structure are versioned; actual files in `ehr-note-qa/` and `mimic-iv/` stay on your machine (see root `.gitignore`).

```
src/data/
├── README.md          # this file
├── ehr-note-qa/       # EHRNoteQA benchmark files (PhysioNet)
└── mimic-iv/          # MIMIC-IV tables / notes (PhysioNet)
```

## Access

Both resources require a [PhysioNet](https://physionet.org/) account, training (e.g. CITI “Data or Specimens Only Research”), and signing the **project-specific** data use agreements before download.

## MIMIC-IV (`mimic-iv/`)

1. Open [MIMIC-IV on PhysioNet](https://physionet.org/content/mimiciv/) and complete credentialing for that project.
2. Download the version you need (e.g. v3.1) via the site’s files page, `wget`/`curl` with your PhysioNet credentials, or the [PhysioNet CLI](https://physionet.org/docs/pnw/), and extract into `src/data/mimic-iv/` so paths match what your code expects (you may use a flat layout or a mirror-style tree—keep it consistent with `src/process_data.py` or downstream scripts).

Official documentation: [MIMIC-IV documentation](https://mimic.mit.edu/docs/iv/).

## EHRNoteQA (`ehr-note-qa/`)

EHRNoteQA is a discharge-summary QA benchmark tied to MIMIC-IV notes.

1. Request access to [EHRNoteQA on PhysioNet](https://physionet.org/content/ehr-notes-qa-llms/).
2. Download the released files into `src/data/ehr-note-qa/`.
3. For preprocessing, environment hints, and how the benchmark joins to MIMIC discharge text, see the [official code repository](https://github.com/ji-youn-kim/EHRNoteQA) and the paper *EHRNoteQA: An LLM Benchmark for Real-World Clinical Practice Using Discharge Summaries* ([arXiv](https://arxiv.org/abs/2402.16040)).

## Check that Git is not tracking downloads

From the repo root:

```bash
git check-ignore -v src/data/mimic-iv/path/to/some_file.csv.gz
```

You should see a rule from `.gitignore`. `git status` should not list raw dataset files after they are ignored.
