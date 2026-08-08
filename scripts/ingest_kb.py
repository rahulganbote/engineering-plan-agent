"""
scripts/ingest_kb.py
═════════════════════
One-time script to ingest all 6 knowledge base documents into Pinecone.

Run this ONCE before starting the pipeline. Safe to re-run - Pinecone
upsert is idempotent so existing vectors are overwritten, not duplicated.

Knowledge base documents (in knowledge_base/):
    brd_fintech_payment_portal.txt  - past BRD, fintech domain, medium complexity
    brd_platform_idp.txt            - past BRD, platform domain, complex
    arch_patterns.txt               - 6 architecture patterns with trade-offs
    plan_templates.txt              - phased delivery templates with milestones
    project_timelines.csv           - 15 historical projects with velocity data
    tech_decision_log.txt           - org technology decisions with rationale

Usage:
    # Full ingestion + retrieval test (recommended first time)
    python scripts/ingest_kb.py

    # Check Pinecone connectivity only
    python scripts/ingest_kb.py --check-only

    # Run retrieval tests only (after ingestion already done)
    python scripts/ingest_kb.py --test-only

Expected output:
    ✅ brd_fintech_payment_portal.txt - 12 chunks
    ✅ brd_platform_idp.txt           - 11 chunks
    ✅ arch_patterns.txt              - 7 chunks
    ✅ plan_templates.txt             - 8 chunks
    ✅ project_timelines.csv          - 15 chunks
    ✅ tech_decision_log.txt          - 14 chunks
    ─────────────────────────────────
    Total: 67 chunks ingested
    ✅ All retrieval tests passed
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add project root to Python path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.core.logger import get_logger
from src.core.rag import ingest_document, retrieve

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "secrets" / ".env")

log = get_logger(__name__)

# ── Knowledge base document registry ─────────────────────────────────────────
# Each entry defines the source_type, domain, and tags for a KB document.
# source_type controls which chunking strategy is used (see src/core/rag.py).
DOCUMENTS = [
    {
        "filename":    "brd_fintech_payment_portal.txt",
        "source_type": "brd",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["payment", "fintech", "pci-dss", "microservices", "api"],
    },
    {
        "filename":    "brd_platform_idp.txt",
        "source_type": "brd",
        "domain":      "platform",
        "complexity":  "complex",
        "tags":        ["platform", "kubernetes", "devops", "developer-experience"],
    },
    {
        "filename":    "arch_patterns.txt",
        "source_type": "arch_pattern",
        "domain":      "generic",
        "complexity":  "medium",
        "tags":        ["microservices", "event-driven", "cqrs", "saga", "serverless"],
    },
    {
        "filename":    "plan_templates.txt",
        "source_type": "plan_template",
        "domain":      "generic",
        "complexity":  "medium",
        "tags":        ["phases", "milestones", "risk", "planning", "delivery"],
    },
    {
        "filename":    "project_timelines.csv",
        "source_type": "timeline",
        "domain":      "generic",
        "complexity":  "medium",
        "tags":        ["velocity", "estimation", "schedule", "variance", "team-size"],
    },
    {
        "filename":    "tech_decision_log.txt",
        "source_type": "tech_log",
        "domain":      "generic",
        "complexity":  "medium",
        "tags":        ["tech-stack", "database", "framework", "decision", "rationale"],
    },
]

# expected_output_{simple,medium,complex}.json intentionally NOT ingested:
# these are the eval suite's answer keys (eval/run_eval.py compares agent
# output against them). Indexing them into the KB would let a live BRD run's
# RAG retrieval surface ground-truth eval answers as "context", leaking the
# answer key into production grounding. Keep them out of DOCUMENTS.

# ── NEW DOCUMENTS (added from Project 1 PFRA training data) ──────────────────
NEW_DOCUMENTS = [
    {
        "filename":    "BRD_Template.txt",
        "source_type": "brd",
        "domain":      "generic",
        "complexity":  "simple",
        "tags":        ["template", "brd", "structure", "requirements"],
    },
    {
        "filename":    "BRD_Example1_PFRA.txt",
        "source_type": "brd",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["example", "brd", "finance", "reporting", "ai-agent", "pfra"],
    },
    {
        "filename":    "Engineering_Plan_Template.txt",
        "source_type": "plan_template",
        "domain":      "generic",
        "complexity":  "simple",
        "tags":        ["template", "engineering-plan", "phases", "milestones"],
    },
    {
        "filename":    "Engineering_Plan_Example1_PFRA.txt",
        "source_type": "plan_template",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["example", "engineering-plan", "finance", "ai-agent", "pfra"],
    },
    {
        "filename":    "Project_Schedule_Example1_PFRA.txt",
        "source_type": "timeline",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["example", "schedule", "sprints", "effort", "pfra"],
    },
    {
        "filename":    "Solution_Architect_Template.txt",
        "source_type": "arch_pattern",
        "domain":      "generic",
        "complexity":  "simple",
        "tags":        ["template", "architecture", "components", "nfr", "mermaid"],
    },
    {
        "filename":    "Solution_Architect_Example1_PFRA.txt",
        "source_type": "arch_pattern",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["example", "architecture", "orchestrator-agent", "rag", "pfra"],
    },
    {
        "filename":    "PoC_Plan_Template.txt",
        "source_type": "plan_template",
        "domain":      "generic",
        "complexity":  "simple",
        "tags":        ["template", "poc", "hypothesis", "go-nogo"],
    },
    {
        "filename":    "PoC_Plan_Example1_PFRA.txt",
        "source_type": "plan_template",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["example", "poc", "cross-correlation", "finance", "pfra"],
    },
    {
        "filename":    "Tech_Stack_Options_Example1_PFRA.txt",
        "source_type": "tech_log",
        "domain":      "fintech",
        "complexity":  "medium",
        "tags":        ["example", "tech-stack", "options", "trade-offs", "cloud-native", "pfra"],
    },
]

# Merge new documents into main DOCUMENTS list
DOCUMENTS.extend(NEW_DOCUMENTS)

# ── Domain Specific Document - LegalTech SaaS documents (added from BRD Example 2) ─────────────────────
LEGALTECH_DOCUMENTS = [
    {
        "filename":    "BRD_Example2_LegalTech_SaaS.txt",
        "source_type": "brd",
        "domain":      "legaltech",
        "complexity":  "complex",
        "tags":        ["example", "brd", "legaltech", "saas", "microservices",
                        "multi-tenant", "compliance", "soc2", "byok", "ediscovery"],
    },
    {
        "filename":    "Engineering_Plan_Example2_LegalTech_SaaS.txt",
        "source_type": "plan_template",
        "domain":      "legaltech",
        "complexity":  "complex",
        "tags":        ["example", "engineering-plan", "legaltech", "microservices",
                        "phases", "milestones", "compliance", "pentest"],
    },
    {
        "filename":    "Project_Schedule_Example2_LegalTech_SaaS.txt",
        "source_type": "timeline",
        "domain":      "legaltech",
        "complexity":  "complex",
        "tags":        ["example", "schedule", "sprints", "effort", "legaltech",
                        "soc2", "compliance", "microservices"],
    },
    {
        "filename":    "Solution_Architect_Example2_LegalTech_SaaS.txt",
        "source_type": "arch_pattern",
        "domain":      "legaltech",
        "complexity":  "complex",
        "tags":        ["example", "architecture", "microservices", "multi-tenant",
                        "event-sourcing", "audit-ledger", "byok", "legaltech", "mermaid"],
    },
    {
        "filename":    "PoC_Plan_Example2_LegalTech_SaaS.txt",
        "source_type": "plan_template",
        "domain":      "legaltech",
        "complexity":  "complex",
        "tags":        ["example", "poc", "tenant-isolation", "pentest",
                        "byok", "legaltech", "adversarial-testing"],
    },
    {
        "filename":    "Tech_Stack_Options_Example2_LegalTech_SaaS.txt",
        "source_type": "tech_log",
        "domain":      "legaltech",
        "complexity":  "complex",
        "tags":        ["example", "tech-stack", "options", "trade-offs",
                        "aws-native", "compliance", "legaltech", "byok", "soc2"],
    },
]

DOCUMENTS.extend(LEGALTECH_DOCUMENTS)

# ── Org standards + expanded tech decision log ──────────────────────────────
STANDARDS_DOCUMENTS = [
    {
        "filename":    "org_engineering_standards.txt",
        "source_type": "standard",
        "domain":      "generic",
        "complexity":  "reference",
        "tags":        ["standards", "coding", "cicd", "security", "architecture-review",
                        "approved-stack", "compliance", "observability", "adr"],
    },
]

DOCUMENTS.extend(STANDARDS_DOCUMENTS)

# ── Additional Tech Stack Recommendation ──────────────────────────────
TECH_STACK_RECOMMENDATION_DOCUMENTS = [
    {
        "filename":    "Tech_Stack_Recommender_Microservices_WebApp.txt",
        "source_type": "standard",
        "domain":      "Microservices or WebApp",
        "complexity":  "complex",
        "tags":        ["example", "tech-stack", "options", "Microservices", "WebApp", "Frotend", "Backend",
                        "aws-native", "scalable", "generic", "byok", "security"],
    },
       {
        "filename":    "Tech_Stack_Recommender_AIML_DataScience.txt",
        "source_type": "standard",
        "domain":      "AIML and Data Science Engineering",
        "complexity":  "complex",
        "tags":        ["example", "tech-stack", "options", "AIML", "Data Science","MLOps",
                        "aws-native", "scalable", "generic", "security"],
    },
]

DOCUMENTS.extend(TECH_STACK_RECOMMENDATION_DOCUMENTS)


#KB_DIR = Path(__file__).parent.parent / "knowledge_base"
KB_DIR = PROJECT_ROOT / "knowledge_base"


def ingest_all() -> tuple[int, list[str]]:
    """Ingest all KB documents. Returns (total_chunks, failed_files)."""
    print("=" * 60)
    print("EM Copilot - Knowledge Base Ingestion")
    #print(f"Target: Pinecone index '{__import__(\"os\").getenv(\"PINECONE_INDEX\", \"brd-knowledge-base\")}'")
    print(f"Target: Pinecone index '{os.getenv('PINECONE_INDEX', 'brd-knowledge-base')}'")
                                        
    print("=" * 60)

    total_chunks = 0
    failed: list[str] = []

    for doc in DOCUMENTS:
        filepath = KB_DIR / doc["filename"]

        if not filepath.exists():
            print(f"  ⚠️  MISSING: {doc['filename']}")
            failed.append(doc["filename"])
            continue

        text = filepath.read_text(encoding="utf-8")
        print(f"  Ingesting: {doc['filename']} ...", end=" ", flush=True)

        try:
            result = ingest_document(
                text=text,
                doc_id=filepath.stem,           # filename without extension
                source_type=doc["source_type"],
                domain=doc["domain"],
                complexity=doc["complexity"],
                tags=doc["tags"],
            )
            chunk_count  = int(result.split(" ")[0])
            total_chunks += chunk_count
            print(f"✅ {result}")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            failed.append(doc["filename"])

    print("-" * 60)
    print(f"Total: {total_chunks} chunks ingested")
    if failed:
        print(f"⚠️  Failed: {', '.join(failed)}")
    return total_chunks, failed


def test_retrieval() -> bool:
    """Run retrieval tests to confirm KB is queryable."""
    print("\nRunning retrieval verification tests...")

    # Each test: (query, source_types_filter, expected_min_results)
    tests = [
        ("engineering plan phases milestones risks",   ["plan_template", "brd"],  1),
        ("microservices event-driven architecture NFR", ["arch_pattern"],          1),
        ("project timeline estimation team velocity",   ["timeline"],              1),
        ("technology stack decision database choice",   ["tech_log"],              1),
    ]

    all_passed = True
    for query, source_types, min_results in tests:
        chunks = retrieve(query, source_types=source_types, top_k=3)
        passed = len(chunks) >= min_results
        icon   = "✅" if passed else "⚠️ "
        print(f"  {icon} [{source_types[0]}] '{query[:45]}...' → {len(chunks)} chunks")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ All retrieval tests passed - KB is ready.")
    else:
        print("\n⚠️  Some tests returned no results. Check ingestion errors above.")
        print("   Pinecone may need 15-30 seconds after upsert to index new vectors.")

    return all_passed


def check_connectivity() -> bool:
    """Check Pinecone connectivity without ingesting anything."""
    try:
        import os

        from pinecone import Pinecone
        pc    = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        idx   = os.getenv("PINECONE_INDEX", "brd-knowledge-base")
        stats = pc.Index(idx).describe_index_stats()
        print(f"✅ Pinecone connected | index={idx} | vectors={stats.total_vector_count}")
        return True
    except Exception as e:
        print(f"❌ Pinecone connection failed: {e}")
        print("   Check PINECONE_API_KEY and PINECONE_INDEX in .env")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EM Copilot KB ingestion and verification")
    parser.add_argument("--check-only", action="store_true", help="Check connectivity only")
    parser.add_argument("--test-only",  action="store_true", help="Run retrieval tests only")
    args = parser.parse_args()

    if args.check_only:
        sys.exit(0 if check_connectivity() else 1)

    elif args.test_only:
        sys.exit(0 if test_retrieval() else 1)

    else:
        # Full ingestion + test
        total, failed = ingest_all()

        if total == 0:
            print("\n❌ No chunks ingested - check errors above.")
            sys.exit(1)

        print("\nWaiting 45 seconds for Pinecone to index vectors...")
        time.sleep(45)

        passed = test_retrieval()
        print("\nEnding the Ingestion Process...")
        sys.exit(0 if passed else 1)    # Exit with code 1 if retrieval tests failed, so CI can catch it

