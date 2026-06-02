resource "null_resource" "kind_cluster" {
  provisioner "local-exec" {
    command = "kind create cluster --name chaos-demo-cluster"
  }

  provisioner "local-exec" {
    when    = destroy
    command = "kind delete cluster --name chaos-demo-cluster"
  }
}
