# app/modules/users/__init__.py
# Handles all user-related API routes
# Registered in app/__init__.py with url_prefix='/api/users'

from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Account

# This is what app/__init__.py imports:
# from app.modules.users import users_bp
users_bp = Blueprint('users', __name__)


@users_bp.route('/', methods=['GET'])
def list_users():
    rows = User.query.all()
    return jsonify(users=[r.to_dict() for r in rows], total=len(rows))


@users_bp.route('/', methods=['POST'])
def create_user():
    data = request.get_json() or {}
    for field in ['username', 'full_name', 'email']:
        if field not in data:
            return jsonify(error=f'Missing required field: {field}'), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify(error='Username already taken'), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify(error='Email already in use'), 409
    account_id = data.get('account_id')
    if account_id and not Account.query.get(account_id):
        return jsonify(error='Account not found'), 404
    user = User(
        username=data['username'],
        full_name=data['full_name'],
        email=data['email'],
        role=data.get('role', 'trader'),
        account_id=int(account_id) if account_id else None
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(message='User created', user=user.to_dict()), 201


@users_bp.route('/<int:uid>', methods=['GET'])
def get_user(uid):
    return jsonify(User.query.get_or_404(uid).to_dict())


@users_bp.route('/<int:uid>', methods=['PUT'])
def update_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json() or {}
    for field in ['full_name', 'role', 'account_id', 'is_active']:
        if field in data:
            setattr(user, field, data[field])
    db.session.commit()
    return jsonify(user=user.to_dict())


@users_bp.route('/<int:uid>', methods=['DELETE'])
def delete_user(uid):
    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    return jsonify(message='User deleted')