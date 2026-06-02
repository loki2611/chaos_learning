#!/bin/bash
set -e

CLUSTER_NAME="chaos-demo-cluster"
IMAGE_NAME="tradesphere:latest"

echo "🔹 Deleting KIND cluster..."
kind delete cluster --name $CLUSTER_NAME || true

echo "🔹 Resetting Terraform state..."
rm -rf .terraform terraform.tfstate terraform.tfstate.backup
terraform init

echo "🔹 Removing local Docker image (optional)..."
docker rmi $IMAGE_NAME || true

echo "✅ Cleanup complete. You can now run ./deploy.sh to redeploy everything fresh."
