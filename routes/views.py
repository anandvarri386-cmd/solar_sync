from flask import Blueprint, render_template, session, send_from_directory
from utils.calibrations import load_config
from routes.auth import login_required, get_current_user
import os

views_bp = Blueprint('views', __name__)

@views_bp.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@views_bp.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@views_bp.route('/')
@views_bp.route('/dashboard')
@login_required
def dashboard():
    config = load_config()
    current_user = get_current_user()
    return render_template('index.html', config=config, current_user=current_user)

@views_bp.route('/history')
@login_required
def history():
    config = load_config()
    current_user = get_current_user()
    return render_template('history.html', config=config, current_user=current_user)

@views_bp.route('/settings')
@login_required
def settings():
    config = load_config()
    current_user = get_current_user()
    return render_template('settings.html', config=config, current_user=current_user)

@views_bp.route('/about')
@login_required
def about():
    config = load_config()
    current_user = get_current_user()
    return render_template('about.html', config=config, current_user=current_user)
