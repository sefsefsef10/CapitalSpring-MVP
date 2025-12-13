#!/bin/bash
# CapitalSpring MVP - Initial Production Deployment Script
# Run this in Google Cloud Shell after cloning the repository
#
# Prerequisites completed:
# - Artifact Registry created
# - Terraform state bucket created
# - VPC Connector created
# - Anthropic API key secret created

set -e

PROJECT_ID="capitalspring-mvp"
REGION="us-central1"
DB_INSTANCE="capitalspring-dev"
DB_NAME="capitalspring"
DB_USER="app"

echo "============================================"
echo "CapitalSpring MVP - Initial Deployment"
echo "============================================"

# Step 1: Set project
echo ""
echo "Step 1: Setting GCP project..."
gcloud config set project $PROJECT_ID

# Step 2: Enable required APIs
echo ""
echo "Step 2: Enabling required APIs..."
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com

# Step 3: Create service account for Cloud Run API
echo ""
echo "Step 3: Creating service account for API..."
gcloud iam service-accounts create capitalspring-api-sa \
  --display-name="CapitalSpring API Service Account" \
  --description="Service account for CapitalSpring API on Cloud Run" \
  2>/dev/null || echo "Service account already exists"

# Grant roles to service account
echo "Granting roles to service account..."
for ROLE in \
  "roles/cloudsql.client" \
  "roles/storage.objectAdmin" \
  "roles/pubsub.publisher" \
  "roles/secretmanager.secretAccessor" \
  "roles/documentai.apiUser" \
  "roles/logging.logWriter" \
  "roles/cloudtrace.agent"
do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:capitalspring-api-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE" \
    --condition=None \
    --quiet
done

# Step 4: Create Cloud SQL instance
echo ""
echo "Step 4: Creating Cloud SQL instance..."
gcloud sql instances describe $DB_INSTANCE --quiet 2>/dev/null || \
gcloud sql instances create $DB_INSTANCE \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-size=10GB \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=04

# Generate and store database password
echo "Generating database password..."
DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)

# Create database user
echo "Creating database user..."
gcloud sql users create $DB_USER \
  --instance=$DB_INSTANCE \
  --password=$DB_PASSWORD \
  2>/dev/null || echo "User already exists, updating password..."
gcloud sql users set-password $DB_USER \
  --instance=$DB_INSTANCE \
  --password=$DB_PASSWORD

# Create database
echo "Creating database..."
gcloud sql databases create $DB_NAME \
  --instance=$DB_INSTANCE \
  2>/dev/null || echo "Database already exists"

# Step 5: Create DATABASE_URL secret
echo ""
echo "Step 5: Creating database URL secret..."
INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${INSTANCE_CONNECTION_NAME}"

# Create secret
gcloud secrets create capitalspring-db-url \
  --replication-policy=automatic \
  2>/dev/null || echo "Secret already exists"

# Add secret version
echo -n "$DATABASE_URL" | gcloud secrets versions add capitalspring-db-url --data-file=-

echo "Database URL secret created successfully!"

# Step 6: Grant Cloud Build permissions
echo ""
echo "Step 6: Granting Cloud Build permissions..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Cloud Build service account needs these roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin" \
  --condition=None \
  --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser" \
  --condition=None \
  --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None \
  --quiet

# Step 7: Create GCS bucket for documents
echo ""
echo "Step 7: Creating GCS bucket..."
gsutil mb -l US gs://${PROJECT_ID}-data 2>/dev/null || echo "Bucket already exists"

# Create folder structure
echo "Creating bucket folder structure..."
echo "" | gsutil cp - gs://${PROJECT_ID}-data/inbox/.keep
echo "" | gsutil cp - gs://${PROJECT_ID}-data/processing/.keep
echo "" | gsutil cp - gs://${PROJECT_ID}-data/complete/.keep
echo "" | gsutil cp - gs://${PROJECT_ID}-data/failed/.keep
echo "" | gsutil cp - gs://${PROJECT_ID}-data/archive/.keep

# Step 8: Run database migrations
echo ""
echo "Step 8: Running database migrations..."
echo "Connecting to Cloud SQL via proxy..."

# Start Cloud SQL proxy in background
cloud_sql_proxy --instances=${INSTANCE_CONNECTION_NAME}=tcp:5432 &
PROXY_PID=$!
sleep 5

# Run migrations (need to be in api directory with dependencies)
export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"
cd api
pip install -r requirements.txt -q
alembic upgrade head
cd ..

# Stop proxy
kill $PROXY_PID 2>/dev/null || true

# Step 9: Deploy via Cloud Build
echo ""
echo "Step 9: Deploying via Cloud Build..."
gcloud builds submit --config cloudbuild-initial.yaml \
  --substitutions=_REGION=$REGION

echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""
echo "Getting service URLs..."
API_URL=$(gcloud run services describe capitalspring-api --region=$REGION --format='value(status.url)')
FRONTEND_URL=$(gcloud run services describe capitalspring-frontend --region=$REGION --format='value(status.url)')
echo ""
echo "API URL: $API_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""
echo "Next steps:"
echo "1. Add your Anthropic API key to the secret:"
echo "   echo -n 'sk-ant-...' | gcloud secrets versions add anthropic-api-key --data-file=-"
echo ""
echo "2. Configure Firebase Authentication in the Firebase Console"
echo ""
echo "3. Update frontend env vars if needed and redeploy"
echo ""
echo "4. Test the application at: $FRONTEND_URL"
