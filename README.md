TradeSphere — SRE/DevOps Demo Platform
A 3-tier trading platform built to demonstrate a full DevOps/SRE lifecycle:
Code → Build → Infrastructure → Deploy → Chaos → Load Test

Architecture
┌─────────────────────────────────────────┐
│            Browser (UI)                  │  ← Vanilla HTML/CSS/JS
│    Dashboard | Accounts | Users | Trades │
└──────────────────┬──────────────────────┘
                   │ HTTP REST
┌──────────────────▼──────────────────────┐
│         Flask Application (Python)       │  ← 3 Modules + Health
│  /api/accounts  /api/users  /api/trades  │
│  /health/live   /health/ready            │
└──────────────────┬──────────────────────┘
                   │ SQLAlchemy ORM
┌──────────────────▼──────────────────────┐
│        SQLite (dev) / PostgreSQL (prod)  │
│    accounts   users   trades             │
└─────────────────────────────────────────┘

Quick Start (Local)
bash# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python run.py

# 3. Open browser
open http://localhost:5000

REST API
MethodEndpointDescriptionGET/api/accounts/List all accountsPOST/api/accounts/Create accountGET/api/accounts/:idGet accountPUT/api/accounts/:idUpdate accountDELETE/api/accounts/:idDelete accountGET/api/users/List all usersPOST/api/users/Create userGET/api/trades/List all tradesPOST/api/trades/Execute tradePOST/api/trades/:id/cancelCancel tradeGET/health/liveLiveness probeGET/health/readyReadiness probe

DevOps Pipeline
1. Docker — Build the Image
bashdocker build -t tradesphere:latest .
docker run -p 5000:5000 tradesphere:latest
2. Terraform — Provision Infrastructure
bashcd terraform
terraform init
terraform plan
terraform apply
3. Ansible — Install Dependencies
bashcd ansible
ansible-playbook -i inventory.ini playbook.yml
4. Helm — Package & Deploy to Kubernetes
bash# Install
helm upgrade --install tradesphere ./helm/tradesphere \
  --namespace tradesphere --create-namespace

# Check status
kubectl get pods -n tradesphere
kubectl logs -n tradesphere -l app=tradesphere

# Port forward for local access
kubectl port-forward svc/tradesphere-svc 5000:80 -n tradesphere
5. ChaosToolkit — Fault Injection
bash# Run pod kill experiment
chaos run chaos/pod_kill_experiment.json

# Run scale-down experiment
chaos run chaos/scale_down_experiment.json

# Generate HTML report
chaos report --export-format=html5 journal.json report.html
6. JMeter — Load Testing
bash# CLI mode (headless)
jmeter -n -t jmeter/tradesphere_load_test.jmx \
       -l jmeter/results/results.jtl \
       -e -o jmeter/results/html-report

# Or open in JMeter GUI
jmeter -t jmeter/tradesphere_load_test.jmx

GitHub Actions CI/CD
The .github/workflows/main.yml pipeline runs on every push to main:

Test — pytest with coverage
Build — Docker image pushed to GHCR
Deploy — Helm upgrade on Kubernetes


Project Structure
chaos_learning/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py            # SQLAlchemy models
│   ├── views.py             # UI routes
│   ├── modules/
│   │   ├── account/         # Account CRUD API
│   │   ├── users/           # User management API
│   │   ├── trades/          # Trade execution API
│   │   └── health/          # K8s health probes
│   └── templates/
│       └── index.html       # Single-page frontend
├── run.py                   # Entry point
├── requirements.txt
├── Dockerfile               # Multi-stage Docker build
├── .github/workflows/
│   └── main.yml             # CI/CD pipeline
├── terraform/
│   └── main.tf              # K8s infra provisioning
├── ansible/
│   └── playbook.yml         # Dependency installation
├── helm/tradesphere/        # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       └── deployment.yaml
├── chaos/
│   ├── pod_kill_experiment.json
│   └── scale_down_experiment.json
└── jmeter/
    └── tradesphere_load_test.jmx