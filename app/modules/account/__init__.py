# app/modules/account/__init__.py
# Handles all account-related API routes
# Registered in app/__init__.py with url_prefix='/api/accounts'

from flask import Blueprint, request, jsonify
from app import db
from app.models import Account
import random
import string

# This is what app/__init__.py imports:
# from app.modules.account import account_bp
account_bp = Blueprint('accounts', __name__)


def _make_account_number():
    # Generates ACC followed by 8 random digits e.g. ACC84729103
    return 'ACC' + ''.join(random.choices(string.digits, k=8))


@account_bp.route('/', methods=['GET'])
def list_accounts():
    rows = Account.query.all()
    return jsonify(accounts=[r.to_dict() for r in rows], total=len(rows))


@account_bp.route('/', methods=['POST'])
def create_account():
    data = request.get_json()
    if not data:
        return jsonify(error='No data provided'), 400
    for field in ['holder_name', 'email']:
        if field not in data:
            return jsonify(error=f'Missing required field: {field}'), 400
    if Account.query.filter_by(email=data['email']).first():
        return jsonify(error='Email already registered'), 409
    account = Account(
        account_number=_make_account_number(),
        holder_name=data['holder_name'],
        email=data['email'],
        phone=data.get('phone', ''),
        account_type=data.get('account_type', 'individual'),
        balance=float(data.get('initial_balance', 0)),
        currency=data.get('currency', 'USD')
    )
    db.session.add(account)
    db.session.commit()
    return jsonify(message='Account created', account=account.to_dict()), 201


@account_bp.route('/<int:aid>', methods=['GET'])
def get_account(aid):
    return jsonify(Account.query.get_or_404(aid).to_dict())


@account_bp.route('/<int:aid>', methods=['PUT'])
def update_account(aid):
    account = Account.query.get_or_404(aid)
    data = request.get_json() or {}
    for field in ['holder_name', 'phone', 'account_type', 'status', 'balance']:
        if field in data:
            setattr(account, field, data[field])
    db.session.commit()
    return jsonify(account=account.to_dict())


@account_bp.route('/<int:aid>', methods=['DELETE'])
def delete_account(aid):
    account = Account.query.get_or_404(aid)
    db.session.delete(account)
    db.session.commit()
    return jsonify(message='Account deleted')