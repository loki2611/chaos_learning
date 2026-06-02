output "namespace" {
  value = kubernetes_namespace.tradesphere.metadata[0].name
}

output "service_name" {
  value = kubernetes_service.app.metadata[0].name
}
