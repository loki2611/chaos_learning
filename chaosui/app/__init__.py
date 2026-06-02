from flask import Flask
import os
 
 
def create_app():
    app = Flask(__name__)
 
    # Where is TradeSphere running?
    # Inside K8s this will be the internal service DNS name.
    # Locally set this in your shell: export TARGET_APP_URL=http://localhost:5000
    app.config['TARGET_APP_URL'] = os.environ.get(
        'TARGET_APP_URL', 'http://localhost:8080'
    )
 
    # Kubernetes namespace where TradeSphere lives
    app.config['APP_NAMESPACE'] = os.environ.get(
        'APP_NAMESPACE', 'tradesphere'
    )
 
    # Secret key for Flask sessions (not critical for this tool)
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 'chaosui-dev-key'
    )
 
    # Register the two blueprints:
    #   views_bp  → serves the HTML page at /
    #   api_bp    → REST endpoints the UI calls for experiments and results
    from app.views import views_bp
    from app.api   import api_bp
 
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
 
    return app