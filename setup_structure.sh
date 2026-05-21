#!/bin/bash
# ══════════════════════════════════════════════════════════════
# EM Copilot — Project Setup Script
# Run this ONCE in your project root to create all folders
#
# Usage:
#   cd /Users/rahul/OneDrive/Rahul/InterviewKickstart/AgenticAI/Capstone_Project/BRD_to_Engineering_Agent/engineering-plan-agent
#   bash setup_structure.sh
# ══════════════════════════════════════════════════════════════

echo "Creating EM Copilot project structure..."

# Source directories
mkdir -p src/core
mkdir -p src/agents
mkdir -p src/api
mkdir -p src/security
mkdir -p src/integrations

# Data directories
mkdir -p knowledge_base
mkdir -p eval
mkdir -p scripts
mkdir -p docs
mkdir -p logs
mkdir -p secrets          # for google_service_account.json (gitignored)

# Test directories
mkdir -p tests/unit
mkdir -p tests/integration

# Config directories
mkdir -p .streamlit

echo "✅ All directories created"
echo ""
echo "Next steps:"
echo "  1. Copy all downloaded files into the matching directories"
echo "  2. cp .env.example .env  then fill in your API keys"
echo "  3. pip install -r requirements.txt"
echo "  4. python scripts/ingest_kb.py"
echo "  5. Open in VS Code: code ."
