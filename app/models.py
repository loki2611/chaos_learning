# =============================================================================
# FILE: app/models.py
# PURPOSE: SQLAlchemy database models (Account, User, Trade).
#
# HOW MODELS WORK:
#   Each class maps to one database table.
#   Each class attribute maps to one column.
#   SQLAlchemy handles all the SQL — you write Python, it writes SQL.
#
# TABLE RELATIONSHIPS:
#   Account ──< User    (one account has many users)
#   Account ──< Trade   (one account has many trades)
#   User    ──< Trade   (one user places many trades)
#
# FOREIGN KEYS:
#   User.account_id  → accounts.id
#   Trade.account_id → accounts.id
#   Trade.user_id    → users.id
# =============================================================================

from app import db           # the SQLAlchemy instance from app/__init__.py
from datetime import datetime
import random
import string


# ── Helper: generate a random reference string ───────────────────────────────
def _gen_ref(prefix, n):
    """
    Creates a random reference like 'TRDAB3X9K2'.
    prefix: leading string (e.g. 'TRD', 'ACC')
    n:      number of random characters to append
    """
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))


# =============================================================================
# MODEL: Account
# TABLE: accounts
# PURPOSE: Represents a trading account (like a brokerage account).
#          An account belongs to one holder but can have multiple users/traders.
# =============================================================================
class Account(db.Model):
    __tablename__ = 'accounts'

    # Primary key — auto-incrementing integer ID
    id             = db.Column(db.Integer, primary_key=True)

    # Unique account number like ACC12345678, generated automatically
    account_number = db.Column(
        db.String(20), unique=True, nullable=False,
        default=lambda: 'ACC' + ''.join(random.choices(string.digits, k=8))
    )

    # The account holder's full name
    holder_name    = db.Column(db.String(100), nullable=False)

    # Email must be unique across all accounts
    email          = db.Column(db.String(120), unique=True, nullable=False)

    phone          = db.Column(db.String(20), default='')

    # individual / corporate / institutional
    account_type   = db.Column(db.String(20), default='individual')

    # Current balance in the account
    balance        = db.Column(db.Float, default=0.0)

    # 3-letter currency code: USD, EUR, GBP, INR
    currency       = db.Column(db.String(3), default='USD')

    # active / suspended / closed
    status         = db.Column(db.String(20), default='active')

    # Timestamp when the record was created (set once, never updated)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships — SQLAlchemy populates these automatically.
    # backref='account' means you can do user.account to get the Account object.
    # lazy=True means related records are only loaded when you access them.
    users  = db.relationship('User',  backref='account', lazy=True)
    trades = db.relationship('Trade', backref='account', lazy=True)

    def to_dict(self):
        """Convert to plain dict so Flask can JSON-serialise it."""
        return dict(
            id=self.id,
            account_number=self.account_number,
            holder_name=self.holder_name,
            email=self.email,
            phone=self.phone,
            account_type=self.account_type,
            balance=self.balance,
            currency=self.currency,
            status=self.status,
            created_at=self.created_at.isoformat()
        )


# =============================================================================
# MODEL: User
# TABLE: users
# PURPOSE: Represents a person who can log in and place trades on an account.
#          One account can have multiple users (e.g. analyst + trader).
# =============================================================================
class User(db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)

    # Login handle — must be unique, e.g. "j.doe" or "john_trader"
    username   = db.Column(db.String(80),  unique=True, nullable=False)

    full_name  = db.Column(db.String(100), nullable=False)

    # Email — unique, used for notifications
    email      = db.Column(db.String(120), unique=True, nullable=False)

    # trader / analyst / admin / viewer
    role       = db.Column(db.String(20), default='trader')

    # FK to accounts.id — which account this user belongs to (can be null)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)

    # Set to False to disable without deleting (soft-disable)
    is_active  = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One user can place many trades
    trades = db.relationship('Trade', backref='user', lazy=True)

    def to_dict(self):
        return dict(
            id=self.id, username=self.username, full_name=self.full_name,
            email=self.email, role=self.role, account_id=self.account_id,
            is_active=self.is_active, created_at=self.created_at.isoformat()
        )


# =============================================================================
# MODEL: Trade
# TABLE: trades
# PURPOSE: Represents a single buy or sell order placed on an account.
#          A trade belongs to both an account and a user.
# =============================================================================
class Trade(db.Model):
    __tablename__ = 'trades'

    id = db.Column(db.Integer, primary_key=True)

    # Unique human-readable reference like TRD-AB3X9K2
    trade_ref   = db.Column(
        db.String(30), unique=True, nullable=False,
        default=lambda: _gen_ref('TRD', 8)
    )

    # Which account this trade is charged to
    account_id  = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)

    # Which user placed this trade
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Ticker symbol: AAPL, BTC, RELIANCE, etc.
    symbol      = db.Column(db.String(20), nullable=False)

    # BUY or SELL
    trade_type  = db.Column(db.String(10), nullable=False)

    # Number of units (shares, coins, contracts)
    quantity    = db.Column(db.Float, nullable=False)

    # Price per unit at execution time
    price       = db.Column(db.Float, nullable=False)

    # quantity × price — stored to avoid recalculating
    total_value = db.Column(db.Float, nullable=False)

    # pending / executed / cancelled
    status      = db.Column(db.String(20), default='executed')

    # Currency of the trade — inherited from the account at booking time.
    # Stored on the trade so the record is self-contained even if the account
    # currency is later changed. Defaults to USD for any legacy rows.
    currency    = db.Column(db.String(3), default='USD')

    notes       = db.Column(db.Text, default='')

    # When the trade record was created in our system
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # When the trade was actually executed on the market (can differ from created_at)
    executed_at = db.Column(db.DateTime)

    def to_dict(self):
        return dict(
            id=self.id, trade_ref=self.trade_ref,
            account_id=self.account_id, user_id=self.user_id,
            symbol=self.symbol, trade_type=self.trade_type,
            quantity=self.quantity, price=self.price,
            total_value=self.total_value,
            currency=self.currency,          # <-- now returned in every response
            status=self.status,
            notes=self.notes,
            created_at=self.created_at.isoformat(),
            executed_at=self.executed_at.isoformat() if self.executed_at else None
        )