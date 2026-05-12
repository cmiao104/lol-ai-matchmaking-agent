#!/bin/bash
set -e

SERVICE="chat-agent-api"
REGION="us-central1"

echo "🚀 Deploying Cloud Run service..."

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 180 \
  --concurrency 10 \
  --update-env-vars "GOOGLE_GENAI_USE_VERTEXAI=True,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION=us-central1"

echo "✅ Deployment complete."
