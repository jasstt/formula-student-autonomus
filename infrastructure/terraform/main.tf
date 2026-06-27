terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.80.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "YOUR_PROJECT_ID"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west3" # Frankfurt (Düşük latency için)
}

# --- PUB/SUB TOPICS ---

resource "google_pubsub_topic" "sensor_data" {
  name = "sensor-data-topic"
}

resource "google_pubsub_topic" "agent_results" {
  name = "agent-results-topic"
}

resource "google_pubsub_topic" "deployment" {
  name = "deployment-topic"
}

# --- FIRESTORE ---
# Note: Requires App Engine application in project to enable Firestore in Native Mode
# via Terraform in some setups, or can be done manually.

# --- CLOUD RUN SERVICES (Placeholders for deployment) ---

resource "google_cloud_run_service" "perception_service" {
  name     = "perception-service"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/perception-service:latest"
        resources {
          limits = {
            memory = "4Gi"
            cpu    = "2000m"
          }
        }
      }
    }
  }
  
  # Yüksek frekanslı çağrılar için sürekli ayakta kalması istenebilir
  # annotation: run.googleapis.com/minScale = "1"
}

resource "google_cloud_run_service" "dashboard_service" {
  name     = "dashboard-service"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/dashboard-service:latest"
      }
    }
  }
}

# --- CLOUD SCHEDULER ---

resource "google_cloud_scheduler_job" "surveillance_trigger" {
  name             = "surveillance-agent-trigger"
  description      = "Her 6 saatte bir Surveillance Agent'i tetikler."
  schedule         = "0 */6 * * *"
  time_zone        = "Europe/Istanbul"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "https://surveillance-service-url/scan" # Gerçek URL ile değiştirilmeli
    
    # OIDC auth eklenecek
  }
}

resource "google_cloud_scheduler_job" "arxiv_nightly" {
  name             = "arxiv-nightly-scan"
  description      = "Her gece arXiv taraması."
  schedule         = "0 2 * * *"
  time_zone        = "Europe/Istanbul"

  pubsub_target {
    topic_name = google_pubsub_topic.agent_results.id
    data       = base64encode("{\"action\": \"start_arxiv_scan\"}")
  }
}
