#!/bin/bash
set -e

CLUSTER_NAME="chaos-demo-cluster"
IMAGE_NAME="tradesphere:latest"

echo "🔹 Cleaning up old cluster..."
kind delete cluster --name $CLUSTER_NAME || true

echo "🔹 Resetting Terraform state..."
rm -rf .terraform terraform.tfstate terraform.tfstate.backup
terraform init

echo "🔹 Creating KIND cluster with Terraform..."
terraform apply -target=null_resource.kind_cluster -auto-approve

echo "🔹 Building Docker image..."
docker build -t $IMAGE_NAME ..

echo "🔹 Loading image into KIND..."
kind load docker-image $IMAGE_NAME --name $CLUSTER_NAME

echo "🔹 Applying Kubernetes resources with Terraform..."
terraform apply -auto-approve

echo "🔹 Verifying pods..."
kubectl get pods -n tradesphere
