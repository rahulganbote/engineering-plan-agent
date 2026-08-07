"""
scripts/purge_stale_kb_vectors.py
══════════════════════════════════
One-time cleanup companion to the ingest_kb.py registry fix.

Two issues this fixes in the live Pinecone index:

1. expected_output_{simple,medium,complex}.json were removed from
   ingest_kb.py's DOCUMENTS list (they're the eval suite's answer keys -
   indexing them let live BRD runs retrieve ground-truth eval answers as
   RAG "context", leaking the answer key into production grounding).
   Removing them from the registry only stops FUTURE ingestion runs from
   re-upserting them - it does NOT remove the vectors already sitting in
   Pinecone from prior runs. This script deletes those.

2. Tech_Stack_Recommender_{Microservices_WebApp,AIML_DataScience}.txt were
   re-tagged from source_type "tech_log" -> "standard" (see ingest_kb.py),
   which changes their chunking strategy from _row_split (one chunk per
   line) to _section_split (one chunk per ## header). Chunk IDs are
   deterministic - "{doc_id}_chunk_{i}" (src/core/rag.py) - not content-
   hashed, and Pinecone upsert only overwrites IDs that still exist after
   re-ingestion. Since the new chunking produces FEWER chunks than the old
   line-by-line split, the higher-numbered chunk IDs from the old ingestion
   become permanent orphans unless explicitly deleted first.

This script deletes a generous ID range per affected doc_id (safe: deleting
a nonexistent ID is a no-op in Pinecone, not an error), then re-runs
ingestion for just those 5 documents so the index picks up the clean data.

Usage:
    python scripts/purge_stale_kb_vectors.py            # delete + re-ingest
    python scripts/purge_stale_kb_vectors.py --dry-run   # print IDs only
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "secrets" / ".env")

from src.core.config import settings  # noqa: E402
from src.core.rag import ingest_document  # noqa: E402

KB_DIR = PROJECT_ROOT / "knowledge_base"

# Generous upper bound on chunk index per doc_id. Deleting IDs that were
# never created is harmless, so these are intentionally over-sized rather
# than exact.
STALE_DOC_IDS: dict[str, int] = {
    "expected_output_complex":  30,
    "expected_output_medium":   30,
    "expected_output_simple":   30,
    "Tech_Stack_Recommender_Microservices_WebApp": 60,
    "Tech_Stack_Recommender_AIML_DataScience":      60,
}

# Re-ingest these two under their corrected source_type after purging.
# (expected_output_* docs are deleted only - they no longer belong in the KB.)
REINGEST = [
    {
        "filename":    "Tech_Stack_Recommender_Microservices_WebApp.txt",
        "source_type": "standard",
        "domain":      "Microservices or WebApp",
        "complexity":  "complex",
        "tags":        ["example", "tech-stack", "options", "Microservices", "WebApp",
                        "aws-native", "scalable", "generic", "byok", "security"],
    },
    {
        "filename":    "Tech_Stack_Recommender_AIML_DataScience.txt",
        "source_type": "standard",
        "domain":      "AIML and Data Science Engineering",
        "complexity":  "complex",
        "tags":        ["example", "tech-stack", "options", "AIML", "Data Science", "MLOps",
                        "aws-native", "scalable", "generic", "security"],
    },
]


def build_delete_ids() -> list[str]:
    ids = []
    for doc_id, max_chunks in STALE_DOC_IDS.items():
        ids.extend(f"{doc_id}_chunk_{i}" for i in range(max_chunks))
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge stale/leaked KB vectors and re-ingest corrected docs")
    parser.add_argument("--dry-run", action="store_true", help="Print the IDs that would be deleted, without connecting to Pinecone")
    args = parser.parse_args()

    delete_ids = build_delete_ids()

    if args.dry_run:
        print(f"Would delete {len(delete_ids)} candidate vector IDs across {len(STALE_DOC_IDS)} doc_ids:")
        for doc_id in STALE_DOC_IDS:
            print(f"  {doc_id}_chunk_0 .. {doc_id}_chunk_{STALE_DOC_IDS[doc_id] - 1}")
        print("\n(Deleting a nonexistent ID is a no-op in Pinecone - these ranges are intentionally over-sized.)")
        return 0

    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index)

    print(f"Deleting {len(delete_ids)} candidate vector IDs from '{settings.pinecone_index}'...")
    # Pinecone delete-by-ids has a per-call limit; batch to be safe.
    BATCH = 100
    for i in range(0, len(delete_ids), BATCH):
        index.delete(ids=delete_ids[i:i + BATCH])
    print("✅ Delete complete.")

    print("\nRe-ingesting corrected Tech_Stack_Recommender docs...")
    for doc in REINGEST:
        filepath = KB_DIR / doc["filename"]
        if not filepath.exists():
            print(f"  ⚠️  MISSING: {doc['filename']}")
            continue
        text = filepath.read_text(encoding="utf-8")
        result = ingest_document(
            text=text,
            doc_id=filepath.stem,
            source_type=doc["source_type"],
            domain=doc["domain"],
            complexity=doc["complexity"],
            tags=doc["tags"],
        )
        print(f"  ✅ {doc['filename']}: {result}")

    print("\nDone. expected_output_* vectors are purged and NOT re-ingested (they're eval-only, excluded from ingest_kb.py's DOCUMENTS).")
    print("Tech_Stack_Recommender_* vectors are purged and re-ingested under source_type='standard'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
