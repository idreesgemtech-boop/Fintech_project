from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from .db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    status = Column(String, default="ACTIVE")
    jurisdiction = Column(String, default="PK")
    created_at = Column(DateTime, default=datetime.utcnow)

class KYCProfile(Base):
    __tablename__ = "kyc_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    tier = Column(Integer, default=0)
    status = Column(String, default="NOT_STARTED")
    requirements = Column(Text, default="")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vertical = Column(String, default="banking")
    currency = Column(String, nullable=False)
    iban = Column(String, nullable=False)
    status = Column(String, default="ACTIVE")

class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    name = Column(String, nullable=False)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(String, nullable=False)
    ledger_account_id = Column(Integer, ForeignKey("ledger_accounts.id"), nullable=False)
    debit = Column(Numeric(20, 8), default=0)
    credit = Column(Numeric(20, 8), default=0)
    currency = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    card_type = Column(String, default="VIRTUAL")
    last4 = Column(String, nullable=False)
    status = Column(String, default="ACTIVE")
    online = Column(Boolean, default=True)
    international = Column(Boolean, default=False)
    atm = Column(Boolean, default=True)
    daily_limit = Column(Numeric(20, 2), default=1000)

class FXQuote(Base):
    __tablename__ = "fx_quotes"
    id = Column(Integer, primary_key=True)
    source_currency = Column(String, nullable=False)
    destination_currency = Column(String, nullable=False)
    source_amount = Column(Numeric(20, 8), nullable=False)
    rate = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), default=0)
    spread = Column(Numeric(20, 8), default=0)
    destination_amount = Column(Numeric(20, 8), nullable=False)
    expires_at = Column(DateTime, nullable=False)

class FXHedge(Base):
    __tablename__ = "fx_hedges"
    id = Column(Integer, primary_key=True)
    quote_id = Column(Integer, ForeignKey("fx_quotes.id"), nullable=False)
    status = Column(String, default="LOCKED")
    locked_rate = Column(Numeric(20, 8), nullable=False)
    expires_at = Column(DateTime, nullable=False)

class Provider(Base):
    __tablename__ = "providers"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    available = Column(Boolean, default=True)

class ProviderQuote(Base):
    __tablename__ = "provider_quotes"
    id = Column(Integer, primary_key=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    corridor = Column(String, nullable=False)
    source_amount = Column(Numeric(20, 8), nullable=False)
    fx_rate = Column(Numeric(20, 8), nullable=False)
    provider_fee = Column(Numeric(20, 8), nullable=False)
    network_fee = Column(Numeric(20, 8), nullable=False)
    fx_spread = Column(Numeric(20, 8), nullable=False)
    total_cost = Column(Numeric(20, 8), nullable=False)
    recipient_amount = Column(Numeric(20, 8), nullable=False)
    expires_at = Column(DateTime, nullable=False)

class Transfer(Base):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_account_id = Column(Integer, nullable=False)
    destination_account_id = Column(Integer, nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    status = Column(String, default="CREATED")
    idempotency_key = Column(String, unique=True, nullable=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    network = Column(String, nullable=False)
    address = Column(String, nullable=False)
    memo_tag = Column(String, nullable=True)

class BlockchainDeposit(Base):
    __tablename__ = "blockchain_deposits"
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    tx_hash = Column(String, nullable=False)
    confirmations = Column(Integer, default=0)
    required_confirmations = Column(Integer, default=12)
    status = Column(String, default="PENDING")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String, nullable=False)
    asset_class = Column(String, nullable=False)
    side = Column(String, nullable=False)
    order_type = Column(String, default="LIMIT")
    quantity = Column(Numeric(20, 8), nullable=False)
    remaining_quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    status = Column(String, default="OPEN")
    created_at = Column(DateTime, default=datetime.utcnow)

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    buy_order_id = Column(Integer, nullable=False)
    sell_order_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Collateral(Base):
    __tablename__ = "collateral"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    asset = Column(String, nullable=False)
    market_value_usd = Column(Numeric(20, 8), nullable=False)
    haircut = Column(Numeric(10, 6), default=1)

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    strategy = Column(String, nullable=False)
    sharpe = Column(Numeric(10, 4), default=0)
    max_position = Column(Numeric(20, 8), default=0)
    paper_trading = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    response_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ReserveSnapshot(Base):
    __tablename__ = "reserve_snapshots"
    id = Column(Integer, primary_key=True)
    total_assets_usd = Column(Numeric(20, 8), nullable=False)
    total_liabilities_usd = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
