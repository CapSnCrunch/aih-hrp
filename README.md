# aih-hrp
AI in Healthcare course High-Risk Project

## Project plan

This repository supports a benchmarking study on **how patient data architecture affects LLM clinical reasoning**. The work compares ways of organizing healthcare information—from raw notes to relational and graph representations—and measures their impact on question answering. The evaluation contrasts **retrieval-augmented generation (RAG)** with **tool-use** setups (e.g., SQL access) to see which designs are most reliable for personalized-medicine-style queries.

### Motivation

Electronic health records (EHRs) are heterogeneous and high-stakes. The project goes beyond one-off demos by building a **repeatable benchmarking harness** so we can compare approaches under controlled conditions, focusing on demographics, surgical history, and prescription-related reasoning across different schemas.

### Methodology (three phases)

1. **Data synthesis and organization**  
   Synthetic patient records span labs, chart events, and clinical notes, stored in three parallel forms: unstructured notes, structured SQL tables, and graph-based representations.

2. **Benchmark Q/A**  
   Gold-standard questions probe distinct reasoning skills, for example:
   - **Temporal:** how long since the patient’s last surgery  
   - **Descriptive:** age and primary diagnosis  
   - **Predictive:** likely prescriptions given current vitals  

3. **Experimental harnesses**  
   Three evaluation modes:
   - **Naive context:** load data directly into the model context  
   - **RAG:** embedding-based retrieval of relevant segments  
   - **Agentic SQL:** the model queries structured data via SQL tools  

### Early results and next steps

Early runs suggest **RAG is strong on descriptive questions**, while **agentic SQL does better on temporal and quantitative reasoning**. Planned extensions include richer retrieval (e.g., NER) to improve RAG. Related literature spans temporal knowledge-graph modeling (e.g., RE-Net) and specialized medical reasoning frameworks; this work emphasizes **comparing full harnesses** rather than a single pipeline.

## Database setup

The `src/db/` directory contains everything needed to spin up a local Postgres instance loaded with MIMIC-IV 3.1 and EHRNoteQA.

### Prerequisites

```bash
brew install --cask docker   # Docker Desktop (runs the Postgres container)
brew install postgresql      # psql client tools (used by the load script)
```

Make sure Docker Desktop is open and running before proceeding. The compressed source data is **~10 GB**; once loaded, the Postgres data directory will expand to roughly **50–80 GB** on disk, so make sure you have the space.

### Start the container

```bash
docker compose up -d
```

The schema is applied automatically on first boot.

### Load the data

**Recommended — slim load (~20 min, ~12 GB on disk):**

Skips `chartevents`, `labevents`, `emar`, `emar_detail`, `poe`, `poe_detail`, and `pharmacy` — tables not needed for EHRNoteQA benchmarking.

```bash
caffeinate -i ./src/db/load_data.sh --slim
```

**Full load (~2 hours, ~50–80 GB on disk):**

```bash
caffeinate -i ./src/db/load_data.sh
```

On Linux or if you prefer not to use `caffeinate`, drop the `caffeinate -i` prefix. Both commands accept optional path overrides:

```bash
./src/db/load_data.sh --slim /path/to/mimiciv/3.1 /path/to/EHRNoteQA.jsonl
```

### Connect

```bash
psql -h localhost -U mimiciv -d mimiciv
```

Credentials: user `mimiciv`, password `mimiciv`, database `mimiciv`.

---

## Course assignment (AI in Healthcare — high-risk project)

This repo is the course **high-risk project**: something you have wanted to try but might not succeed at. **Grading emphasizes effort and rigor, not how impressive the final results are.** Ambitious or exploratory work is encouraged; weak or empty outcomes can still earn a strong grade if the attempt was serious. The instructors explicitly discourage choosing a project that would be easy for you.

### Learning outcomes

- Design a project related to AI in healthcare.
- Combine technologies and methods to address a healthcare question.
- Write an **ACM-style research report**.
- Present findings in a **recorded presentation**.

### Teams

You may work **solo** or in a group of **up to three** students. The course suggests using **Ed Discussion** to find collaborators. **Teams must be finalized at least two weeks before the due date**, and the expected depth and quality of the work should match team size.

### Choosing a topic

Topic choice drives the shape of the project. Consider your interests, what is feasible in one semester, and (for groups) the combined skills of teammates. The course stresses **stepping outside your comfort zone** and treating failure as part of learning.

Example directions mentioned in the assignment include: AI for health risk prediction; **LLMs for health problems**; explainable AI in healthcare (e.g., research from Su-In Lee’s group); tools to analyze clinical notes; and reports on social aspects of AI in health (ethics, law, fairness). For LLM-oriented ideas, the course materials also reference a NeurIPS 2023–inspired summary shared by the instructor.
