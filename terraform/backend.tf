# Remote state in GCS — create the bucket manually before first run:
#   gsutil mb -p $PROJECT_ID -l $REGION gs://${PROJECT_ID}-terraform-state
#   gsutil versioning set on gs://${PROJECT_ID}-terraform-state

terraform {
  backend "gcs" {
    bucket = "" # Set via -backend-config="bucket=<project>-terraform-state"
    prefix = "stratum/state"
  }
}
