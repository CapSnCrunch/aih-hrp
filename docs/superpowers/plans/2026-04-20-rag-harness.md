# RAG Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a RAG harness that retrieves semantically relevant note chunks per patient using pgvector + mxbai-embed-large, then answers EHRNoteQA questions from that context.

**Architecture:** An offline embedding pipeline (`src/process_data.py`) chunks and embeds discharge/radiology notes for the 962 EHRNoteQA patients into a `mimiciv_note.chunks` pgvector table. At benchmark time, `RAGHarness` embeds the question, retrieves the top-5 most similar chunks for that patient via cosine similarity, and answers using the same prompt/answer pattern as `NaiveHarness`.

**Tech Stack:** pgvector (Postgres extension), mxbai-embed-large (Ollama), psycopg2, Python 3.14, existing Docker container (mimiciv_db)

---

### Task 1: Install pgvector into the Docker container and add the chunks table

**Files:**
- Modify: `src/db/schema.sql`
- Modify: `docker-compose.yml` (swap base image for pgvector-enabled image)

- [ ] **Step 1: Update docker-compose.yml to use pgvector image**

In `docker-compose.yml`, change the postgres image from `postgres:16` to `pgvector/pgvector:pg16`:

```yaml
image: pgvector/pgvector:pg16
```

- [ ] **Step 2: Add chunks table and pgvector extension to schema.sql**

Add at the end of `src/db/schema.sql`:

```sql
-- pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Note chunks with embeddings for RAG
CREATE TABLE IF NOT EXISTS mimiciv_note.chunks (
    chunk_id    SERIAL PRIMARY KEY,
    subject_id  INTEGER NOT NULL,
    note_id     TEXT NOT NULL,
    source_table TEXT NOT NULL,  -- 'discharge' or 'radiology'
    section_name TEXT,
    chunk_text  TEXT NOT NULL,
    embedding   vector(1024)
);

CREATE INDEX IF NOT EXISTS chunks_subject_id_idx ON mimiciv_note.chunks (subject_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON mimiciv_note.chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

- [ ] **Step 3: Rebuild the container with the new image**

```bash
docker compose down
docker compose up -d
```

Wait ~10 seconds for Postgres to start, then verify:

```bash
docker exec mimiciv_db psql -U mimiciv -d mimiciv -c "\dx"
```

Expected output includes `vector` in the extensions list.

- [ ] **Step 4: Verify chunks table exists**

```bash
docker exec mimiciv_db psql -U mimiciv -d mimiciv -c "\d mimiciv_note.chunks"
```

Expected: table with columns chunk_id, subject_id, note_id, source_table, section_name, chunk_text, embedding.

- [ ] **Step 5: Commit**

```bash
git add src/db/schema.sql docker-compose.yml
git commit -m "feat: add pgvector extension and chunks table for RAG"
```

---

### Task 2: Write the embedding pipeline (src/process_data.py)

**Files:**
- Modify: `src/process_data.py`

- [ ] **Step 1: Write the chunking logic**

Replace the contents of `src/process_data.py` with:

```python
"""
Embedding pipeline: chunks and embeds discharge/radiology notes for the 962
EHRNoteQA patients into mimiciv_note.chunks using mxbai-embed-large via Ollama.

Usage:
    .venv/bin/python src/process_data.py
    .venv/bin/python src/process_data.py --ollama-url http://localhost:11434
"""

import argparse
import json
import re
import urllib.request
from typing import Generator

import psycopg2
import psycopg2.extras

EMBED_MODEL = "mxbai-embed-large"
MAX_TOKENS = 512       # max tokens per chunk (approximated as chars/4)
OVERLAP_TOKENS = 64    # overlap between chunks
MAX_CHARS = MAX_TOKENS * 4
OVERLAP_CHARS = OVERLAP_TOKENS * 4

SECTION_RE = re.compile(r'^([A-Z][A-Z &/()-]{2,}):[ \t]*$', re.MULTILINE)


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split a note into (section_name, section_text) pairs."""
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return [("FULL_NOTE", text.strip())]

    sections = []
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((name, body))
    return sections


def chunk_text(text: str, section_name: str) -> Generator[tuple[str, str], None, None]:
    """Yield (section_name, chunk_text) pairs, splitting long sections with overlap."""
    if len(text) <= MAX_CHARS:
        yield section_name, text
        return

    start = 0
    while start < len(text):
        end = start + MAX_CHARS
        chunk = text[start:end].strip()
        if chunk:
            yield section_name, chunk
        if end >= len(text):
            break
        start = end - OVERLAP_CHARS


def embed(text: str, ollama_url: str) -> list[float]:
    """Get embedding vector from Ollama."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["embedding"]


def get_patient_ids(conn) -> list[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT patient_id FROM ehrqa.questions ORDER BY patient_id")
        return [row[0] for row in cur.fetchall()]


def get_already_embedded(conn) -> set[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT subject_id FROM mimiciv_note.chunks")
        return {row[0] for row in cur.fetchall()}


def get_notes(conn, subject_id: int, table: str) -> list[tuple[str, str]]:
    """Return list of (note_id, text) for a patient from the given table."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT note_id, text FROM mimiciv_note.{table} WHERE subject_id = %s",
            (subject_id,),
        )
        return [(row[0], row[1]) for row in cur.fetchall() if row[1]]


def insert_chunk(conn, subject_id: int, note_id: str, source_table: str,
                 section_name: str, chunk_text: str, embedding: list[float]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mimiciv_note.chunks
                (subject_id, note_id, source_table, section_name, chunk_text, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (subject_id, note_id, source_table, section_name, chunk_text, embedding),
        )
    conn.commit()


def process_patient(conn, subject_id: int, ollama_url: str) -> int:
    """Chunk, embed, and store all notes for a patient. Returns chunk count."""
    count = 0
    for source_table in ("discharge", "radiology"):
        for note_id, text in get_notes(conn, subject_id, source_table):
            for section_name, body in split_into_sections(text):
                for sec, chunk in chunk_text(body, section_name):
                    vector = embed(chunk, ollama_url)
                    insert_chunk(conn, subject_id, note_id, source_table, sec, chunk, vector)
                    count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host="localhost", port=5432, user="mimiciv", password="mimiciv", dbname="mimiciv"
    )

    patient_ids = get_patient_ids(conn)
    already_done = get_already_embedded(conn)
    remaining = [p for p in patient_ids if p not in already_done]

    print(f"Patients total: {len(patient_ids)} | already embedded: {len(already_done)} | remaining: {len(remaining)}")

    for i, patient_id in enumerate(remaining, 1):
        chunks = process_patient(conn, patient_id, args.ollama_url)
        print(f"[{i}/{len(remaining)}] patient={patient_id} chunks={chunks}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script imports cleanly**

```bash
.venv/bin/python -c "import src.process_data" 2>&1 || .venv/bin/python src/process_data.py --help
```

Expected: prints usage/help with no import errors.

- [ ] **Step 3: Run a smoke test on 1 patient**

```bash
.venv/bin/python -c "
import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, user='mimiciv', password='mimiciv', dbname='mimiciv')

# import helpers
import sys; sys.path.insert(0, 'src')
from process_data import get_patient_ids, split_into_sections, chunk_text

pids = get_patient_ids(conn)
print('First patient:', pids[0])

# Test chunker on a short string
sections = split_into_sections('HISTORY OF PRESENT ILLNESS:\nPatient is a 45yo male.\n\nMEDICATIONS:\nAspirin 81mg.')
print('Sections:', [s[0] for s in sections])

chunks = list(chunk_text('A' * 3000, 'TEST'))
print('Chunk count for 3000-char text:', len(chunks))
conn.close()
"
```

Expected: prints a patient id, section names `['HISTORY OF PRESENT ILLNESS', 'MEDICATIONS']`, and chunk count > 1.

- [ ] **Step 4: Commit**

```bash
git add src/process_data.py
git commit -m "feat: add note chunking and embedding pipeline"
```

---

### Task 3: Run the embedding pipeline

**Files:** None (data pipeline run)

- [ ] **Step 1: Pull the embedding model**

```bash
ollama pull mxbai-embed-large
```

Wait for download to complete.

- [ ] **Step 2: Run the pipeline with caffeinate**

```bash
caffeinate -i .venv/bin/python src/process_data.py
```

This will take a while. Progress is printed per patient. It is safe to interrupt and restart — already-embedded patients are skipped.

- [ ] **Step 3: Verify chunks were created**

```bash
docker exec mimiciv_db psql -U mimiciv -d mimiciv -c "
SELECT COUNT(*) AS total_chunks,
       COUNT(DISTINCT subject_id) AS patients_embedded
FROM mimiciv_note.chunks;"
```

Expected: `patients_embedded` = 962, `total_chunks` > 0.

- [ ] **Step 4: Build the IVFFlat index (if not auto-created)**

The index requires at least `lists * 39` rows to build. If the pipeline has finished:

```bash
docker exec mimiciv_db psql -U mimiciv -d mimiciv -c "
REINDEX INDEX mimiciv_note.chunks_embedding_idx;"
```

---

### Task 4: Implement RAGHarness (src/harness/rag.py)

**Files:**
- Modify: `src/harness/rag.py`

- [ ] **Step 1: Implement the harness**

Replace `src/harness/rag.py` with:

```python
import json
import urllib.request
from datetime import datetime

from .base import BaseHarness, BenchmarkQuestion, QuestionResult

EMBED_MODEL = "mxbai-embed-large"
TOP_K = 5


class RAGHarness(BaseHarness):
    """
    Retrieves the top-k most semantically similar note chunks for the patient
    using pgvector cosine similarity, then answers using the same prompt
    pattern as NaiveHarness.
    """

    def answer_question(self, question: BenchmarkQuestion, verbose: bool = False) -> QuestionResult:
        started_at = datetime.now()

        query_vector = self._embed(question.question)
        context = self._retrieve(question.patient_id, query_vector, verbose=verbose)
        prompt = self._format_prompt(question, context)
        raw, usage = self._ask_ollama(prompt)

        finished_at = datetime.now()
        predicted = self._extract_answer(raw)

        return QuestionResult(
            question_id=question.id,
            patient_id=question.patient_id,
            category=question.category,
            predicted=predicted,
            correct=question.answer,
            is_correct=predicted == question.answer,
            raw_response=raw,
            full_prompt=prompt,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            wall_time_s=round((finished_at - started_at).total_seconds(), 2),
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            tokens_per_sec=usage["tokens_per_sec"],
            llm_duration_s=usage["duration_s"],
        )

    def _embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{self.ollama_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["embedding"]

    def _retrieve(self, patient_id: int, query_vector: list[float], verbose: bool = False) -> str:
        sql = """
            SELECT section_name, chunk_text
            FROM mimiciv_note.chunks
            WHERE subject_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        rows = self._query(sql, (patient_id, query_vector, TOP_K))

        if not rows:
            return "No relevant notes found for this patient."

        chunks = []
        for row in rows:
            header = f"[{row['section_name']}]" if row['section_name'] else "[NOTE]"
            chunks.append(f"{header}\n{row['chunk_text']}")
            if verbose:
                print(f"      Retrieved: {header} ({len(row['chunk_text'])} chars)")

        return "\n\n".join(chunks)
```

- [ ] **Step 2: Verify import**

```bash
.venv/bin/python -c "from src.harness.rag import RAGHarness; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run a smoke test (5 questions)**

```bash
.venv/bin/python src/run_benchmark.py --harness rag --model llama3.2 --limit 5 --verbose
```

Expected: runs 5 questions, each showing retrieved chunk headers, no errors.

- [ ] **Step 4: Commit**

```bash
git add src/harness/rag.py
git commit -m "feat: implement RAGHarness with pgvector cosine similarity retrieval"
```

---

### Task 5: Verify and compare results

**Files:** None

- [ ] **Step 1: Run 20 questions with llama3.2 on RAG harness**

```bash
caffeinate -i .venv/bin/python src/run_benchmark.py --harness rag --model llama3.2 --limit 20 --verbose
```

- [ ] **Step 2: Compare to naive baseline**

Check the latest NaiveHarness result file and compare accuracy:

```bash
.venv/bin/python -c "
import json, glob
files = sorted(glob.glob('results/NaiveHarness_llama3.2_*.json'))
with open(files[-1]) as f:
    d = json.load(f)
print('Naive accuracy:', d['summary']['accuracy'])
files = sorted(glob.glob('results/RAGHarness_llama3.2_*.json'))
with open(files[-1]) as f:
    d = json.load(f)
print('RAG accuracy:', d['summary']['accuracy'])
"
```

- [ ] **Step 3: Run 20 questions with qwen2.5:32b on RAG harness**

```bash
caffeinate -i .venv/bin/python src/run_benchmark.py --harness rag --model qwen2.5:32b --limit 20 --verbose
```
