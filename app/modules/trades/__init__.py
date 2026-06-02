# =============================================================================
# FILE: app/modules/trades/__init__.py
# PURPOSE: Trade Execution API — place and manage buy/sell orders.
#
# ROUTES (all prefixed with /api/trades):
#   GET  /api/trades/                  → list all trades (newest first)
#   POST /api/trades/                  → execute a new trade
#   GET  /api/trades/<id>              → get one trade
#   POST /api/trades/<id>/cancel       → cancel a trade
#   GET  /api/trades/account/<acct_id> → get all trades for one account
# =============================================================================

from flask import Blueprint, request, jsonify
from app import db
from app.models import Trade, Account, User
from datetime import datetime
import random
import string

trades_bp = Blueprint('trades', __name__)


def _trade_ref():
    """
    Generate a unique trade reference like TRD-AB3X9K2Z.
    This is the human-readable ID shown in confirmations and reports.
    """
    return 'TRD' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ── GET /api/trades/ ──────────────────────────────────────────────────────────
@trades_bp.route('/', methods=['GET'])
def list_trades():
    """
    Return all trades, newest first.
    Used by the Dashboard (last 10) and the Trades tab (full list).
    Also used by JMeter load tests as a read-heavy endpoint.
    """
    rows = Trade.query.order_by(Trade.created_at.desc()).all()
    return jsonify(trades=[r.to_dict() for r in rows], total=len(rows))


# ── POST /api/trades/ ─────────────────────────────────────────────────────────
@trades_bp.route('/', methods=['POST'])
def create_trade():
    """
    Execute a new trade.

    Expected JSON body:
    {
        "account_id": 1,       (required — must exist)
        "user_id":    1,       (required — must exist)
        "symbol":     "AAPL",  (required — ticker/coin/instrument)
        "trade_type": "BUY",   (required — BUY or SELL)
        "quantity":   100,     (required — number of units)
        "price":      182.50,  (required — price per unit)
        "notes":      "..."    (optional)
    }

    total_value is calculated as quantity × price and stored.
    The trade is immediately marked 'executed' (no order queue in this demo).
    """
    data = request.get_json() or {}

    # All six fields are required
    for field in ['account_id', 'user_id', 'symbol', 'trade_type', 'quantity', 'price']:
        if field not in data:
            return jsonify(error=f'Missing required field: {field}'), 400

    # Validate trade direction
    if data['trade_type'].upper() not in ('BUY', 'SELL'):
        return jsonify(error='trade_type must be BUY or SELL'), 400

    # Foreign key validation — verify referenced records exist
    account = Account.query.get(data['account_id'])
    if not account:
        return jsonify(error='Account not found'), 404
    if not User.query.get(data['user_id']):
        return jsonify(error='User not found'), 404

    # ── Currency logic ────────────────────────────────────────────────────────
    # The trade currency should always match the account currency.
    # 1. If the caller explicitly passes a currency, we accept it BUT warn if
    #    it does not match the account currency (mismatch = data quality issue).
    # 2. If no currency is passed (normal case from the UI), we automatically
    #    inherit the currency from the account — so an INR account always books
    #    trades in INR.
    account_currency = account.currency or 'USD'

    if 'currency' in data and data['currency']:
        requested_currency = data['currency'].upper()
        if requested_currency != account_currency:
            # Reject mismatches — prevents accidentally booking USD trades on INR accounts
            return jsonify(
                error=f"Currency mismatch: account currency is {account_currency} "
                      f"but trade currency {requested_currency} was requested. "
                      f"Use {account_currency} or omit the currency field."
            ), 400
        trade_currency = requested_currency
    else:
        # Auto-inherit from account — this is the normal path from the UI
        trade_currency = account_currency

    qty   = float(data['quantity'])
    price = float(data['price'])

    trade = Trade(
        trade_ref=_trade_ref(),
        account_id=data['account_id'],
        user_id=data['user_id'],
        symbol=data['symbol'].upper(),
        trade_type=data['trade_type'].upper(),
        quantity=qty,
        price=price,
        total_value=round(qty * price, 2),
        currency=trade_currency,             # stored on the trade record
        status='executed',
        notes=data.get('notes', ''),
        executed_at=datetime.utcnow()
    )
    db.session.add(trade)
    db.session.commit()
    return jsonify(message='Trade executed', trade=trade.to_dict()), 201


# ── GET /api/trades/<id> ──────────────────────────────────────────────────────
@trades_bp.route('/<int:tid>', methods=['GET'])
def get_trade(tid):
    return jsonify(Trade.query.get_or_404(tid).to_dict())


# ── POST /api/trades/<id>/cancel ──────────────────────────────────────────────
@trades_bp.route('/<int:tid>/cancel', methods=['POST'])
def cancel_trade(tid):
    """
    Cancel a trade — sets status to 'cancelled'.
    Does not delete the record (audit trail).
    Returns 400 if already cancelled.
    """
    trade = Trade.query.get_or_404(tid)
    if trade.status == 'cancelled':
        return jsonify(error='Trade is already cancelled'), 400
    trade.status = 'cancelled'
    db.session.commit()
    return jsonify(message='Trade cancelled', trade=trade.to_dict())


# ── GET /api/trades/account/<account_id> ─────────────────────────────────────
@trades_bp.route('/account/<int:aid>', methods=['GET'])
def trades_by_account(aid):
    """
    Return all trades for a specific account.
    Verifies the account exists first (returns 404 if not).
    """
    Account.query.get_or_404(aid)
    rows = Trade.query.filter_by(account_id=aid).order_by(Trade.created_at.desc()).all()
    return jsonify(trades=[r.to_dict() for r in rows], total=len(rows))