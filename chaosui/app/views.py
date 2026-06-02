from flask import Blueprint, render_template, current_app

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    """
    Render the Chaos Control Center HTML page.
    Passes the target app URL so the frontend knows where TradeSphere is.
    """
    return render_template(
        'index.html',
        target_url=current_app.config['TARGET_APP_URL'],
        namespace=current_app.config['APP_NAMESPACE']
    )