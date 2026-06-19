#!/bin/bash
# ────────────────────────────────────────────────────────────────────────────
# scripts/gcp_deploy_secrets.sh
# ────────────────────────────────────────────────────────────────────────────
# Script to bind required secrets from GCP Secret Manager to the Cloud Run service.
# Run this ONCE to configure the service's secret references.
# ────────────────────────────────────────────────────────────────────────────

SERVICE_NAME="em-copilot-react"
REGION="europe-west1"

echo "Binding Secret Manager secrets to Cloud Run service '${SERVICE_NAME}' in region '${REGION}'..."

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
SLACK_WEBHOOK_URL=SLACK_WEBHOOK_URL:latest,\
ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest

if [ $? -eq 0 ]; then
  echo "✓ Secrets successfully bound to ${SERVICE_NAME}."
else
  echo "✗ Failed to bind secrets. Ensure the Cloud Build/Deploy service account has 'Secret Manager Secret Accessor' permissions."
  exit 1
fi
