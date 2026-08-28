from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from models.user import create_user, get_user_by_email, get_user_by_id, verify_password
from utils.calibrations import load_config

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to require authenticated customer session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized", "message": "Authentication required."}), 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Helper to fetch the currently authenticated customer record."""
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            return user
        session.clear()
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Customer Login view & handler."""
    if 'user_id' in session:
        return redirect(url_for('views.dashboard'))
        
    config = load_config()
    error = None
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        if not email or not password:
            error = "Please enter both your email address and password."
        else:
            user = get_user_by_email(email)
            if user and verify_password(user, password):
                # Set session credentials
                session.permanent = remember
                session['user_id'] = user['id']
                session['user_email'] = user['email']
                session['user_name'] = user['name']
                session['pump_device_id'] = user['pump_device_id']
                
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect(url_for('views.dashboard'))
            else:
                error = "Invalid email or password. Please check your credentials."
                
    return render_template('login.html', config=config, error=error)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Customer Sign Up view & handler."""
    if 'user_id' in session:
        return redirect(url_for('views.dashboard'))
        
    config = load_config()
    error = None
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        pump_device_id = request.form.get('pump_device_id', '').strip()
        pump_name = request.form.get('pump_name', 'Smart Solar DC Pump').strip()
        
        if not name or not email or not password:
            error = "All fields marked with an asterisk are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters long."
        elif password != confirm_password:
            error = "Passwords do not match. Please re-enter."
        else:
            user, err_msg = create_user(
                email=email,
                password=password,
                name=name,
                pump_device_id=pump_device_id if pump_device_id else None,
                pump_name=pump_name if pump_name else "Smart Solar DC Pump"
            )
            
            if user:
                # Log customer in immediately upon registration
                session.permanent = True
                session['user_id'] = user['id']
                session['user_email'] = user['email']
                session['user_name'] = user['name']
                session['pump_device_id'] = user['pump_device_id']
                return redirect(url_for('views.dashboard'))
            else:
                error = err_msg
                
    return render_template('signup.html', config=config, error=error)

@auth_bp.route('/logout')
def logout():
    """Clears customer session and redirects to login."""
    session.clear()
    return redirect(url_for('auth.login'))
