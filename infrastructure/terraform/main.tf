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
  name        = "arxiv-nightly-scan"
  description = "Her gece arXiv taraması."
  schedule    = "0 2 * * *"
  time_zone   = "Europe/Istanbul"

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
          name  = "GOOGLE_CLOUD_PROJECT"
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
  name        = "sponsor-daily-cycle"
  description = "Daily Sponsor Outreach Cycle"
  schedule    = "0 10 * * 1-5" # Weekdays at 10:00
  time_zone   = "Europe/Istanbul"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.orchestrator_service.status[0].url}/sponsor"
  }
}

resource "google_cloud_scheduler_job" "social_weekly" {
  name        = "social-weekly-cycle"
  description = "Weekly Social Media Update"
  schedule    = "0 18 * * 5" # Friday at 18:00
  time_zone   = "Europe/Istanbul"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.orchestrator_service.status[0].url}/social"
  }
}

# ================================================================
# SPRINT 3 — Event-Driven Mimari, LSTM, Chief Engineer
# ================================================================

resource "google_pubsub_topic" "component_update" {
  name   = "component-update-topic"
  labels = { system = "fcev-event-bus" }
}

resource "google_pubsub_topic" "state_update" {
  name                       = "state-update-topic"
  message_retention_duration = "600s"
  labels                     = { system = "fcev-chief-engineer", frequency = "high" }
}

resource "google_pubsub_topic" "safety_alert" {
  name                       = "safety-alert-topic"
  message_retention_duration = "604800s"
  labels                     = { system = "fcev-safety", priority = "critical" }
}

resource "google_pubsub_topic" "performance_update" {
  name   = "performance-update-topic"
  labels = { system = "fcev-performance" }
}

resource "google_pubsub_subscription" "safety_alert_sub" {
  name                 = "safety-alert-sub"
  topic                = google_pubsub_topic.safety_alert.name
  ack_deadline_seconds = 10
  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "10s"
  }
}

resource "google_pubsub_subscription" "fcev_events_sub" {
  name                 = "fcev-events-sub"
  topic                = google_pubsub_topic.component_update.name
  ack_deadline_seconds = 60
}

resource "google_cloud_run_service" "chief_engineer" {
  name     = "chief-engineer-agent"
  location = var.region
  template {
    metadata {
      annotations = {
        "run.googleapis.com/minScale" = "1"
        "run.googleapis.com/maxScale" = "3"
      }
    }
    spec {
      container_concurrency = 10
      timeout_seconds       = 300
      containers {
        image = "gcr.io/${var.project_id}/chief-engineer-agent:latest"
        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2000m"
          }
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "PUBSUB_TOPIC_STATE"
          value = "state-update-topic"
        }
        env {
          name  = "PUBSUB_TOPIC_SAFETY"
          value = "safety-alert-topic"
        }
      }
    }
  }
}

resource "google_cloud_run_service" "lstm_inference" {
  name     = "lstm-inference-service"
  location = var.region
  template {
    metadata {
      annotations = {
        "run.googleapis.com/minScale" = "0"
        "run.googleapis.com/maxScale" = "5"
      }
    }
    spec {
      container_concurrency = 20
      containers {
        image = "gcr.io/${var.project_id}/lstm-inference-service:latest"
        resources {
          limits = {
            memory = "4Gi"
            cpu    = "4000m"
          }
        }
        env {
          name  = "MODEL_PATH"
          value = "models/sensor_lstm.pt"
        }
        env {
          name  = "ANOMALY_THRESHOLD"
          value = "0.7"
        }
      }
    }
  }
}

resource "google_cloud_run_service" "event_router" {
  name     = "event-router-service"
  location = var.region
  template {
    metadata {
      annotations = {
        "run.googleapis.com/minScale" = "0"
        "run.googleapis.com/maxScale" = "10"
      }
    }
    spec {
      container_concurrency = 80
      containers {
        image = "gcr.io/${var.project_id}/event-router-service:latest"
        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1000m"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_service" "technical_agents" {
  name     = "technical-agents-service"
  location = var.region
  template {
    metadata {
      annotations = {
        "run.googleapis.com/minScale" = "0"
        "run.googleapis.com/maxScale" = "4"
      }
    }
    spec {
      containers {
        image = "gcr.io/${var.project_id}/technical-agents-service:latest"
        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2000m"
          }
        }
      }
    }
  }
}

resource "google_redis_instance" "fcev_cache" {
  name           = "fcev-system-cache"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  redis_version  = "REDIS_7_0"
  display_name   = "FCEV System State Cache"
  redis_configs  = { "maxmemory-policy" = "allkeys-lru" }
  labels         = { system = "fcev-chief-engineer", use = "state-cache" }
}

resource "google_cloud_scheduler_job" "health_check" {
  name             = "agent-health-check"
  description      = "Her 5 dakikada agent saglik kontrolu"
  schedule         = "*/5 * * * *"
  time_zone        = "Europe/Istanbul"
  attempt_deadline = "30s"
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.chief_engineer.status[0].url}/health"
  }
}

resource "google_cloud_scheduler_job" "lstm_retrain" {
  name             = "lstm-weekly-retrain"
  description      = "Haftalik LSTM model yeniden egitimi"
  schedule         = "0 3 * * 0"
  time_zone        = "Europe/Istanbul"
  attempt_deadline = "1800s"
  pubsub_target {
    topic_name = google_pubsub_topic.performance_update.id
    data       = base64encode("{\"action\": \"retrain_lstm\", \"model\": \"sensor\"}")
  }
}

# ================================================================
# SPRINT 4 — Observability, Memory, Eval, Security
# ================================================================

# Short-term memory Redis (araç anlık durumu, 5s TTL)
# NOT: Sprint 3'te redis zaten eklendi. Bu blok Firestore koleksiyonları
# ve Cloud Scheduler için.

# --- Cloud Scheduler: Weekly Eval Report ---
resource "google_cloud_scheduler_job" "weekly_eval_report" {
  name             = "weekly-eval-report"
  description      = "Her Pazartesi 09:00 haftalik agent eval raporu"
  schedule         = "0 9 * * 1"
  time_zone        = "Europe/Istanbul"
  attempt_deadline = "300s"

  pubsub_target {
    topic_name = google_pubsub_topic.agent_results.id
    data       = base64encode("{\"action\": \"generate_weekly_eval_report\"}")
  }
}

# --- Secret Manager: Audit ve Observability ---
resource "google_secret_manager_secret" "slack_webhook" {
  secret_id = "slack-webhook-url"
  replication {
    automatic = true
  }
  labels = { system = "fcev-observability" }
}

# --- Cloud Run: Observability Dashboard API ---
resource "google_cloud_run_service" "observability_api" {
  name     = "observability-api"
  location = var.region
  template {
    metadata {
      annotations = {
        "run.googleapis.com/minScale" = "0"
        "run.googleapis.com/maxScale" = "2"
      }
    }
    spec {
      containers {
        image = "gcr.io/${var.project_id}/observability-api:latest"
        resources { limits = { memory = "512Mi", cpu = "1000m" } }
        env { name = "GOOGLE_CLOUD_PROJECT", value = var.project_id }
      }
    }
  }
}

# --- IAM: Firestore audit_trail sadece append ---
# audit_trail koleksiyonu için delete yetkisi yok (immutable semantics)
# Bu Firestore Security Rules ile uygulanır (Terraform dışı)
