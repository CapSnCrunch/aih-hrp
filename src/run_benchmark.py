"""
Run the EHRNoteQA benchmark against a local Ollama model.

Usage:
    python src/run_benchmark.py --harness naive --model llama3.2
    python src/run_benchmark.py --harness naive --model llama3.2 --category level1 --limit 10
"""

import argparse
import json

from harness.naive import NaiveHarness
from harness.rag import RAGHarness
from harness.sql import SQLHarness
from harness.code_agent import CodeAgentHarness

HARNESSES = {
    "naive": NaiveHarness,
    "rag": RAGHarness,
    "sql": SQLHarness,
    "code_agent": CodeAgentHarness,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", choices=HARNESSES.keys(), required=True)
    parser.add_argument("--model", required=True, help="Ollama model name (e.g. llama3.2)")
    parser.add_argument("--category", default=None, help="Filter by question category")
    parser.add_argument("--limit", type=int, default=None, help="Max questions to run")
    parser.add_argument("--output-dir", default="results", help="Directory for result files")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--verbose", action="store_true", help="Print SQL queries and observations inline")
    args = parser.parse_args()

    harness = HARNESSES[args.harness](model=args.model, ollama_url=args.ollama_url)

    print(f"Running {args.harness} harness with model '{args.model}'...")
    results = harness.run(category=args.category, limit=args.limit, verbose=args.verbose)

    summary = harness.score(results)
    print(json.dumps(summary, indent=2))

    path = harness.save_results(results, output_dir=args.output_dir)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    main()
