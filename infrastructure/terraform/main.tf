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

# --- SECRET MANAGER ---
resource "google_secret_manager_secret" "linkedin_token" {
  secret_id = "linkedin-access-token"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret" "instagram_token" {
  secret_id = "instagram-access-token"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  replication {
    automatic = true
  }
}

# --- CLOUD RUN: ORCHESTRATOR ---
resource "google_cloud_run_service" "orchestrator_service" {
  name     = "orchestrator-service"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/orchestrator-service:latest"
        env {
          name = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
      }
    }
  }
}

# --- PUB/SUB TOPICS ---
resource "google_pubsub_topic" "code_review_topic" {
  name = "code-review-topic"
}

# --- CLOUD SCHEDULER: ORCHESTRATOR CYCLES ---
resource "google_cloud_scheduler_job" "sponsor_daily" {
  name             = "sponsor-daily-cycle"
  description      = "Daily Sponsor Outreach Cycle"
  schedule         = "0 10 * * 1-5" # Weekdays at 10:00
  time_zone        = "Europe/Istanbul"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.orchestrator_service.status[0].url}/sponsor"
  }
}

resource "google_cloud_scheduler_job" "social_weekly" {
  name             = "social-weekly-cycle"
  description      = "Weekly Social Media Update"
  schedule         = "0 18 * * 5" # Friday at 18:00
  time_zone        = "Europe/Istanbul"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.orchestrator_service.status[0].url}/social"
  }
}
