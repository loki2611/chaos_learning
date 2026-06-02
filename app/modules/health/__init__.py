# app/modules/health/__init__.py
# Kubernetes health check endpoints
# Registered in app/__init__.py with url_prefix='/health'
#
# /health/live  → liveness probe  (is the process alive?)
# /health/ready → readiness probe (is the DB connected?)

from flask import Blueprint, jsonify
from app import db
import time

# This is what app/__init__.py imports:
# from app.modules.health import health_bp
health_bp = Blueprint('health', __name__)


@health_bp.route('/live', methods=['GET'])
def liveness():
    # Always returns 200 as long as Flask is running
    return jsonify(status='alive', timestamp=time.time())


@health_bp.route('/ready', methods=['GET'])
def readiness():
    # Returns 200 only if DB is reachable, else 503
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify(status='ready', db='connected', timestamp=time.time())
    except Exception as e:
        return jsonify(status='not_ready', db='error', error=str(e)), 503