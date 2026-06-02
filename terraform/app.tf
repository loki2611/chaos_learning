# Namespace
resource "kubernetes_namespace" "tradesphere" {
  metadata {
    name   = "tradesphere"
    labels = { app = "tradesphere" }
  }
}

# Secret
resource "kubernetes_secret" "app_secrets" {
  metadata {
    name      = "tradesphere-secrets"
    namespace = kubernetes_namespace.tradesphere.metadata[0].name
  }
  data = {
    secret_key = "my-production-secret-key"
  }
}

# Persistent Volume Claim
resource "kubernetes_persistent_volume_claim" "db" {
  metadata {
    name      = "tradesphere-db"
    namespace = kubernetes_namespace.tradesphere.metadata[0].name
  }
  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = { storage = "1Gi" }
    }
  }
  wait_until_bound = false
}

# Deployment
resource "kubernetes_deployment" "app" {
  metadata {
    name      = "tradesphere-app"
    namespace = kubernetes_namespace.tradesphere.metadata[0].name
    labels    = { app = "tradesphere" }
  }
  spec {
    replicas = 2
    selector {
      match_labels = { app = "tradesphere" }
    }
    template {
      metadata {
        labels = { app = "tradesphere" }
      }
      spec {
        container {
          name  = "tradesphere"
          image = "tradesphere:latest"
          image_pull_policy = "Never"

          port {
            container_port = 5000
          }

          env {
            name = "SECRET_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.app_secrets.metadata[0].name
                key  = "secret_key"
              }
            }
          }

          # Mount the PVC inside the container
          volume_mount {
            name       = "db-storage"
            mount_path = "/data"
          }

          liveness_probe {
            http_get {
              path = "/health/live"
              port = 5000
            }
            initial_delay_seconds = 10
            period_seconds        = 15
          }

          readiness_probe {
            http_get {
              path = "/health/ready"
              port = 5000
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          resources {
            requests = { cpu = "100m", memory = "128Mi" }
            limits   = { cpu = "500m", memory = "512Mi" }
          }
        }

        # Define the volume that uses the PVC
        volume {
          name = "db-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.db.metadata[0].name
          }
        }
      }
    }
  }
}

# Service
resource "kubernetes_service" "app" {
  metadata {
    name      = "tradesphere-svc"
    namespace = kubernetes_namespace.tradesphere.metadata[0].name
  }
  spec {
    selector = { app = "tradesphere" }
    port {
      port        = 80
      target_port = 5000
    }
    type = "NodePort"
  }
}


