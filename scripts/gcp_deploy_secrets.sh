#!/bin/bash
# ────────────────────────────────────────────────────────────────────────────
# scripts/gcp_deploy_secrets.sh
# ────────────────────────────────────────────────────────────────────────────
# Script to bind required secrets from GCP Secret Manager and standard environment
# variables to the Cloud Run service, with automatic runtime SA permission grants.
# ────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Make service name and region overridable via env vars
SERVICE_NAME="${SERVICE_NAME:-em-copilot-react}"
REGION="${REGION:-europe-west1}"

# Resolve GCP Project details
echo "Resolving Google Cloud project configuration..."
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "$PROJECT_ID" ]; then
  echo "Error: Could not resolve GCP Project ID. Ensure you are authenticated with gcloud."
  exit 1
fi
echo "GCP Project ID: $PROJECT_ID"

# ── 1. Check if Cloud Run service exists ──────────────────────────────────────
echo "Checking if Cloud Run service '${SERVICE_NAME}' exists..."
if ! gcloud run services describe "$SERVICE_NAME" --region="$REGION" &>/dev/null; then
  echo "Error: Cloud Run service '${SERVICE_NAME}' not found in region '${REGION}'."
  echo "Please deploy the service at least once via Cloud Build or gcloud run deploy first."
  exit 1
fi

# ── 2. Resolve runtime Service Account of the Cloud Run service ──────────────
echo "Resolving runtime service account..."
RUN_SA=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --format="value(spec.template.spec.serviceAccountName)")

if [ -z "$RUN_SA" ] || [ "$RUN_SA" = "default" ]; then
  PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
  RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi
echo "Runtime Service Account is: $RUN_SA"

# ── 3. Grant Secret Manager Accessor permission to the runtime SA ─────────────
SECRETS=(
  "OPENAI_API_KEY"
  "PINECONE_API_KEY"
  "LANGCHAIN_API_KEY"
  "GOOGLE_OAUTH_CLIENT_SECRET"
  "GOOGLE_SA_B64"
  "JIRA_API_TOKEN"
  "ELEVENLABS_API_KEY"
  "ANTHROPIC_API_KEY"
  "SLACK_WEBHOOK_URL"
  "REDIS_URL"                  # Upstash Redis (us-east-2 / Ohio); enables L2 cache
  "TAVILY_API_KEY"
  "GITHUB_TOKEN"
)

echo "Verifying secrets and granting permissions..."
for SECRET in "${SECRETS[@]}"; do
  if gcloud secrets describe "$SECRET" &>/dev/null; then
    echo "  → Granting Secret Accessor on '${SECRET}' to ${RUN_SA}..."
    gcloud secrets add-iam-policy-binding "$SECRET" \
      --member="serviceAccount:${RUN_SA}" \
      --role="roles/secretmanager.secretAccessor" \
      --quiet >/dev/null
  else
    echo "  → Warning: Secret '${SECRET}' not found in Secret Manager. Skipping IAM grant."
  fi
done

# ── 4. Bind Secrets and standard Environment Variables in one update ─────────
echo "Updating Cloud Run service configuration..."

# Configure default values for environment variables if not already defined in the env
GOOGLE_SHEET_ID="${GOOGLE_SHEET_ID:-1iQ8r2Z0qmXIS5lQCzMIhj7ePmq5kYPBxRhA_ud4Xq0I}"
JIRA_BASE_URL="${JIRA_BASE_URL:-https://ganboteglobal.atlassian.net}"
JIRA_EMAIL="${JIRA_EMAIL:-rganbote@gmail.com}"
JIRA_PROJECT_KEY="${JIRA_PROJECT_KEY:-SCRUM}"
JIRA_ISSUE_TYPE="${JIRA_ISSUE_TYPE:-Task}"
ELEVENLABS_AGENT_ID="${ELEVENLABS_AGENT_ID:-agent_7001krh802v5fadsw06e8h0czdha}"
GOOGLE_OAUTH_CLIENT_ID="${GOOGLE_OAUTH_CLIENT_ID:-809545615573-pbj5sns33o31b8p0gqnbto02d20m76fe.apps.googleusercontent.com}"

# Derive the redirect URI from the actual service URL — prevents stale-fallback bugs
# during region migrations. Override via env var only if pointing at a custom domain.
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format='value(status.url)')
GOOGLE_OAUTH_REDIRECT_URI="${GOOGLE_OAUTH_REDIRECT_URI:-${SERVICE_URL}/auth/callback}"

gcloud run services update "$SERVICE_NAME" \
  --region="$REGION" \
  --platform="managed" \
  --update-secrets=\
OPENAI_API_KEY=OPENAI_API_KEY:latest,\
PINECONE_API_KEY=PINECONE_API_KEY:latest,\
LANGCHAIN_API_KEY=LANGCHAIN_API_KEY:latest,\
GOOGLE_OAUTH_CLIENT_SECRET=GOOGLE_OAUTH_CLIENT_SECRET:latest,\
GOOGLE_SA_B64=GOOGLE_SA_B64:latest,\
JIRA_API_TOKEN=JIRA_API_TOKEN:latest,\
ELEVENLABS_API_KEY=ELEVENLABS_API_KEY:latest,\
ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,\
SLACK_WEBHOOK_URL=SLACK_WEBHOOK_URL:latest,\
REDIS_URL=REDIS_URL:latest,\
TAVILY_API_KEY=TAVILY_API_KEY:latest,\
GITHUB_TOKEN=GITHUB_TOKEN:latest \
  --update-env-vars=\
ANTHROPIC_DEFAULT_MODEL="${ANTHROPIC_DEFAULT_MODEL:-claude-sonnet-4-5}",\
ANTHROPIC_MINI_MODEL="${ANTHROPIC_MINI_MODEL:-claude-haiku-4-5}",\
LANGCHAIN_TRACING_V2="${LANGCHAIN_TRACING_V2:-true}",\
LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT:-em-copilot-brd-agent}",\
GOOGLE_SHEET_ID="${GOOGLE_SHEET_ID}",\
JIRA_BASE_URL="${JIRA_BASE_URL}",\
JIRA_EMAIL="${JIRA_EMAIL}",\
JIRA_PROJECT_KEY="${JIRA_PROJECT_KEY}",\
JIRA_ISSUE_TYPE="${JIRA_ISSUE_TYPE}",\
ELEVENLABS_AGENT_ID="${ELEVENLABS_AGENT_ID}",\
AGENT_TIMEOUT_SEC="${AGENT_TIMEOUT_SEC:-100}",\
SEMANTIC_CACHE_THRESHOLD="${SEMANTIC_CACHE_THRESHOLD:-0.95}",\
GOOGLE_OAUTH_CLIENT_ID="${GOOGLE_OAUTH_CLIENT_ID}",\
GOOGLE_OAUTH_REDIRECT_URI="${GOOGLE_OAUTH_REDIRECT_URI}",\
OPENAI_DEFAULT_MODEL="${OPENAI_DEFAULT_MODEL:-gpt-4o}",\
OPENAI_MINI_MODEL="${OPENAI_MINI_MODEL:-gpt-4o-mini}"

echo "✓ Configuration successfully applied to Cloud Run service '${SERVICE_NAME}'."

# ── 5. Verification step (Smoke Test) ─────────────────────────────────────────
echo "Verifying service health..."
URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format='value(status.url)')
echo "Service URL: $URL"

echo "Checking health endpoint..."
for i in {1..6}; do
  if curl -sf "$URL/health" >/dev/null; then
    echo "✓ Smoke check passed! Service is healthy."
    exit 0
  fi
  echo "Attempt $i/6: waiting for health endpoint to respond..."
  sleep 5
done

echo "✗ Smoke check failed: Service did not respond to /health."
exit 1
