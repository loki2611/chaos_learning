variable "kubeconfig_path" {
  description = "Path to kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "Kubernetes context to use"
  type        = string
  default     = "kind-chaos-demo-cluster"
}

variable "namespace" {
  description = "Namespace for the app"
  type        = string
  default     = "tradesphere"
}

variable "secret_key" {
  description = "Secret key for the app"
  type        = string
  default     = "my-production-secret-key"
}
