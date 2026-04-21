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
MAX_TOKENS = 384       # conservative limit for mxbai-embed-large (512 token max)
OVERLAP_TOKENS = 48    # overlap between chunks
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


def embed(text: str, ollama_url: str) -> list[float] | None:
    """Get embedding vector from Ollama. Returns None if the chunk cannot be embedded."""
    for attempt, t in enumerate([text, text[:len(text)//2]]):
        payload = json.dumps({"model": EMBED_MODEL, "prompt": t}).encode()
        req = urllib.request.Request(
            f"{ollama_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())["embedding"]
        except urllib.error.HTTPError as e:
            if e.code == 500 and attempt == 0:
                continue  # retry with half-length text
            print(f"      [SKIP] embed failed (HTTP {e.code}), chunk len={len(t)}")
            return None


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
                    if vector is None:
                        continue
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
