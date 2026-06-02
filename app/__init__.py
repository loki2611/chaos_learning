from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///trading_platform.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    from app.modules.account import account_bp
    from app.modules.users import users_bp
    from app.modules.trades import trades_bp
    from app.modules.health import health_bp

    app.register_blueprint(account_bp, url_prefix='/api/accounts')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(trades_bp, url_prefix='/api/trades')
    app.register_blueprint(health_bp, url_prefix='/health')

    from app.views import views_bp
    app.register_blueprint(views_bp)

    with app.app_context():
        db.create_all()

    return app