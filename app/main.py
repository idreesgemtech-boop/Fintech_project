from datetime import datetime, timedelta
import os
from decimal import Decimal
import json, hashlib

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db.database import Base, engine, get_db
from .models import *
from .services.ledger import post_double_entry
from .services.providers import provider_quotes
from .services.trading import find_matches

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SynxEx Assessment MVP", version="1.0.0")

# ---------- Schemas ----------
class UserIn(BaseModel):
    email: str
    jurisdiction: str = "PK"

class AccountIn(BaseModel):
    user_id: int
    currency: str
    vertical: str = "banking"

class DepositIn(BaseModel):
    amount: Decimal = Field(gt=0)

class CardIn(BaseModel):
    user_id: int
    card_type: str = "VIRTUAL"

class CardControls(BaseModel):
    online: bool = True
    international: bool = False
    atm: bool = True
    daily_limit: Decimal = Field(default=1000, gt=0)

class FXIn(BaseModel):
    source_currency: str
    destination_currency: str
    source_amount: Decimal = Field(gt=0)

class RemittanceIn(BaseModel):
    source_amount: Decimal = Field(gt=0)
    corridor: str

class TransferIn(BaseModel):
    user_id: int
    source_account_id: int
    destination_account_id: int
    amount: Decimal = Field(gt=0)
    currency: str
    provider: str = "ProviderB"

class WalletIn(BaseModel):
    user_id: int
    network: str

class DepositInstructionIn(BaseModel):
    wallet_id: int
    tx_hash: str
    memo_tag: str | None = None
    confirmations: int = Field(default=0, ge=0)

class OrderIn(BaseModel):
    user_id: int
    symbol: str
    asset_class: str
    side: str
    order_type: str = "LIMIT"
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)

class AgentIn(BaseModel):
    name: str
    strategy: str
    sharpe: Decimal = 0
    max_position: Decimal = 0
    paper_trading: bool = True

# ---------- Health ----------
@app.get("/health")
def health():
    return {"status": "ok", "service": "synxex-mvp"}

# ---------- Users/KYC ----------
@app.post("/users")
def create_user(data: UserIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(409, "User already exists")
    u = User(email=data.email, jurisdiction=data.jurisdiction)
    db.add(u); db.commit(); db.refresh(u)
    db.add(KYCProfile(user_id=u.id, tier=0, status="NOT_STARTED",
                      requirements=json.dumps(["identity"])))
    db.commit()
    return {"id": u.id, "email": u.email, "jurisdiction": u.jurisdiction}

@app.post("/kyc/start/{user_id}")
def start_kyc(user_id: int, db: Session = Depends(get_db)):
    k = db.query(KYCProfile).filter_by(user_id=user_id).first()
    if not k: raise HTTPException(404, "User not found")
    k.status = "IN_PROGRESS"; k.tier = max(k.tier, 1)
    k.requirements = json.dumps(["identity", "date_of_birth"])
    db.commit()
    return kyc_out(k)

@app.post("/kyc/{user_id}/advance")
def advance_kyc(user_id: int, db: Session = Depends(get_db)):
    k = db.query(KYCProfile).filter_by(user_id=user_id).first()
    if not k: raise HTTPException(404, "KYC profile not found")
    if k.tier < 5: k.tier += 1
    k.status = "VERIFIED" if k.tier == 5 else "IN_PROGRESS"
    reqs = {
        1:["identity"], 2:["identity","address"], 3:["source_of_funds"],
        4:["enhanced_due_diligence"], 5:[]
    }
    k.requirements = json.dumps(reqs[k.tier])
    db.commit()
    return kyc_out(k)

@app.get("/kyc/{user_id}")
def get_kyc(user_id: int, db: Session = Depends(get_db)):
    k = db.query(KYCProfile).filter_by(user_id=user_id).first()
    if not k: raise HTTPException(404, "KYC profile not found")
    return kyc_out(k)

def kyc_out(k):
    return {"user_id": k.user_id, "tier": k.tier, "status": k.status,
            "progress": k.tier * 20, "requirements": json.loads(k.requirements or "[]")}

# ---------- Accounts/Ledger ----------
@app.post("/accounts")
def create_account(data: AccountIn, db: Session = Depends(get_db)):
    iban = f"DEMO-{data.currency}-{data.user_id}-{datetime.utcnow().strftime('%H%M%S%f')[-8:]}"
    a = Account(user_id=data.user_id, currency=data.currency.upper(), vertical=data.vertical, iban=iban)
    db.add(a); db.flush()
    la = LedgerAccount(account_id=a.id, name=f"{data.currency.upper()}:{data.vertical}:{data.user_id}")
    db.add(la); db.commit(); db.refresh(a)
    return {"id": a.id, "currency": a.currency, "vertical": a.vertical, "iban": a.iban}

@app.get("/accounts/{user_id}")
def accounts(user_id: int, db: Session = Depends(get_db)):
    return [{"id":a.id,"currency":a.currency,"vertical":a.vertical,"iban":a.iban}
            for a in db.query(Account).filter_by(user_id=user_id).all()]

@app.post("/accounts/{account_id}/deposit")
def dev_deposit(account_id: int, data: DepositIn, db: Session = Depends(get_db)):
    a = db.get(Account, account_id)
    if not a: raise HTTPException(404, "Account not found")
    la = db.query(LedgerAccount).filter_by(account_id=account_id).first()
    # Demo funding: debit customer asset and credit a synthetic funding account.
    funding = LedgerAccount(account_id=account_id, name="DEMO_FUNDING")
    db.add(funding); db.flush()
    txid = post_double_entry(db, funding.id, la.id, data.amount, a.currency)
    db.commit()
    return {"transaction_id":txid,"credited":str(data.amount),"currency":a.currency}

@app.get("/ledger/account/{account_id}")
def ledger(account_id: int, db: Session = Depends(get_db)):
    la = db.query(LedgerAccount).filter_by(account_id=account_id).first()
    if not la: raise HTTPException(404, "Ledger account not found")
    rows = db.query(LedgerEntry).filter_by(ledger_account_id=la.id).all()
    balance = sum((Decimal(str(x.credit))-Decimal(str(x.debit))) for x in rows)
    return {"account_id":account_id,"currency":rows[0].currency if rows else None,
            "balance":str(balance),"entries":[
                {"transaction_id":x.transaction_id,"debit":str(x.debit),"credit":str(x.credit)}
                for x in rows]}

# ---------- Cards ----------
@app.post("/cards")
def create_card(data: CardIn, db: Session = Depends(get_db)):
    c = Card(user_id=data.user_id, card_type=data.card_type.upper(), last4=str((data.user_id*7919)%10000).zfill(4))
    db.add(c); db.commit(); db.refresh(c)
    return {"id":c.id,"type":c.card_type,"last4":c.last4,"status":c.status}

@app.post("/cards/{card_id}/freeze")
def freeze(card_id:int, db:Session=Depends(get_db)):
    c=db.get(Card,card_id)
    if not c: raise HTTPException(404,"Card not found")
    c.status="FROZEN"; db.commit(); return {"id":c.id,"status":c.status}

@app.post("/cards/{card_id}/unfreeze")
def unfreeze(card_id:int, db:Session=Depends(get_db)):
    c=db.get(Card,card_id)
    if not c: raise HTTPException(404,"Card not found")
    c.status="ACTIVE"; db.commit(); return {"id":c.id,"status":c.status}

@app.patch("/cards/{card_id}/controls")
def controls(card_id:int, data:CardControls, db:Session=Depends(get_db)):
    c=db.get(Card,card_id)
    if not c: raise HTTPException(404,"Card not found")
    c.online=data.online;c.international=data.international;c.atm=data.atm;c.daily_limit=data.daily_limit
    db.commit()
    return {"id":c.id,"online":c.online,"international":c.international,"atm":c.atm,"daily_limit":str(c.daily_limit)}

# ---------- FX ----------
@app.post("/fx/quote")
def fx_quote(data:FXIn, db:Session=Depends(get_db)):
    rates={("USD","PKR"):Decimal("278"),("EUR","USD"):Decimal("1.08"),("GBP","USD"):Decimal("1.27")}
    rate=rates.get((data.source_currency.upper(),data.destination_currency.upper()))
    if rate is None: raise HTTPException(400,"Demo FX pair not configured")
    fee=Decimal("2"); spread=Decimal("0.005")
    gross=data.source_amount*rate
    destination=gross*(Decimal("1")-spread)-fee
    q=FXQuote(source_currency=data.source_currency.upper(),destination_currency=data.destination_currency.upper(),
              source_amount=data.source_amount,rate=rate,fee=fee,spread=spread,
              destination_amount=destination,expires_at=datetime.utcnow()+timedelta(seconds=60))
    db.add(q);db.commit();db.refresh(q)
    return {"quote_id":q.id,"rate":str(rate),"fee":str(fee),"spread":str(spread),
            "destination_amount":str(destination),"expires_at":q.expires_at.isoformat()}

@app.post("/fx/hedge/lock")
def hedge_lock(data:FXIn, db:Session=Depends(get_db)):
    q = fx_quote(data, db)
    quote=db.get(FXQuote,q["quote_id"])
    h=FXHedge(quote_id=quote.id,status="LOCKED",locked_rate=quote.rate,expires_at=quote.expires_at)
    db.add(h);db.commit();db.refresh(h)
    return {"hedge_id":h.id,"status":h.status,"locked_rate":str(h.locked_rate),"expires_at":h.expires_at.isoformat()}

@app.get("/fx/hedge/{hedge_id}")
def get_hedge(hedge_id:int, db:Session=Depends(get_db)):
    h=db.get(FXHedge,hedge_id)
    if not h: raise HTTPException(404,"Hedge not found")
    if datetime.utcnow()>h.expires_at and h.status=="LOCKED": h.status="EXPIRED";db.commit()
    return {"id":h.id,"status":h.status,"locked_rate":str(h.locked_rate),"expires_at":h.expires_at.isoformat()}

# ---------- Remittance ----------
@app.post("/remittance/quote")
def remittance_quote(data:RemittanceIn):
    quotes=provider_quotes(data.source_amount,data.corridor)
    best=min(quotes,key=lambda x:x["total_cost"])
    return {"selected":best,"all_quotes":quotes,"routing_reason":"lowest total customer cost among mock eligible providers"}

# ---------- Transfers ----------
@app.post("/transfers")
def transfer(data:TransferIn, idempotency_key:str=Header(...,alias="Idempotency-Key"), db:Session=Depends(get_db)):
    existing=db.query(Transfer).filter_by(idempotency_key=idempotency_key).first()
    if existing:
        return {"id":existing.id,"status":existing.status,"idempotent_replay":True}
    s=db.get(Account,data.source_account_id); d=db.get(Account,data.destination_account_id)
    if not s or not d: raise HTTPException(404,"Account not found")
    if s.currency != data.currency or d.currency != data.currency:
        raise HTTPException(400,"Demo transfer requires matching currencies")
    t=Transfer(user_id=data.user_id,source_account_id=s.id,destination_account_id=d.id,
               amount=data.amount,currency=data.currency,provider=data.provider,
               status="PROCESSING",idempotency_key=idempotency_key,attempts=1)
    db.add(t);db.flush()
    # Mock settlement succeeds for ProviderB, retries twice for ProviderA.
    if data.provider=="ProviderA":
        t.status="RETRYING";t.attempts=3
    else:
        src=db.query(LedgerAccount).filter_by(account_id=s.id).first()
        dst=db.query(LedgerAccount).filter_by(account_id=d.id).first()
        post_double_entry(db,src.id,dst.id,data.amount,data.currency)
        t.status="SETTLED"
    db.commit()
    return {"id":t.id,"status":t.status,"attempts":t.attempts,"provider":t.provider}

@app.get("/transfers/{transfer_id}")
def get_transfer(transfer_id:int,db:Session=Depends(get_db)):
    t=db.get(Transfer,transfer_id)
    if not t: raise HTTPException(404,"Transfer not found")
    return {"id":t.id,"status":t.status,"amount":str(t.amount),"currency":t.currency,"provider":t.provider,"attempts":t.attempts}

# ---------- Wallet ----------
MEMO_NETWORKS={"XRP","STELLAR","TON"}
@app.post("/wallets")
def create_wallet(data:WalletIn,db:Session=Depends(get_db)):
    network=data.network.upper()
    address=f"DEMO_{network}_{data.user_id}_{datetime.utcnow().timestamp():.0f}"
    memo="123456" if network in MEMO_NETWORKS else None
    w=Wallet(user_id=data.user_id,network=network,address=address,memo_tag=memo)
    db.add(w);db.commit();db.refresh(w)
    return {"id":w.id,"network":network,"address":address,"memo_tag":memo}

@app.post("/wallets/{wallet_id}/deposit-instructions")
def deposit_instruction(wallet_id:int,data:DepositInstructionIn,db:Session=Depends(get_db)):
    w=db.get(Wallet,wallet_id)
    if not w: raise HTTPException(404,"Wallet not found")
    if w.network in MEMO_NETWORKS and data.memo_tag != w.memo_tag:
        raise HTTPException(400,"Required memo/tag is missing or incorrect")
    required={"BTC":3,"ETH":12,"XRP":1,"STELLAR":1,"TON":20}.get(w.network,12)
    status="AVAILABLE" if data.confirmations>=required else "PENDING"
    dep=BlockchainDeposit(wallet_id=w.id,tx_hash=data.tx_hash,confirmations=data.confirmations,
                          required_confirmations=required,status=status)
    db.add(dep);db.commit();db.refresh(dep)
    return {"deposit_id":dep.id,"status":dep.status,"confirmations":dep.confirmations,"required":required}

@app.get("/wallets/gas")
def gas(network:str="ETH",urgency:str="standard"):
    tiers={"economy":{"fee":"0.0015","eta":"5-10m"},"standard":{"fee":"0.0021","eta":"2-5m"},"fast":{"fee":"0.0035","eta":"<2m"}}
    if urgency not in tiers: raise HTTPException(400,"urgency must be economy, standard or fast")
    return {"network":network.upper(),"urgency":urgency,**tiers[urgency]}

# ---------- Trading ----------
@app.post("/trading/orders")
def order(data:OrderIn,db:Session=Depends(get_db)):
    if data.side.upper() not in {"BUY","SELL"}: raise HTTPException(400,"side must be BUY or SELL")
    o=Order(user_id=data.user_id,symbol=data.symbol.upper(),asset_class=data.asset_class.upper(),
            side=data.side.upper(),order_type=data.order_type.upper(),quantity=data.quantity,
            remaining_quantity=data.quantity,price=data.price)
    db.add(o);db.flush();find_matches(db,o);db.commit();db.refresh(o)
    return {"order_id":o.id,"status":o.status,"remaining_quantity":str(o.remaining_quantity)}

@app.get("/trading/orders/{order_id}")
def get_order(order_id:int,db:Session=Depends(get_db)):
    o=db.get(Order,order_id)
    if not o: raise HTTPException(404,"Order not found")
    return {"id":o.id,"symbol":o.symbol,"side":o.side,"quantity":str(o.quantity),"remaining":str(o.remaining_quantity),"status":o.status}

# ---------- Margin/risk ----------
@app.post("/margin/collateral")
def add_collateral(user_id:int,asset:str,market_value_usd:Decimal,haircut:Decimal=1,db:Session=Depends(get_db)):
    c=Collateral(user_id=user_id,asset=asset,market_value_usd=market_value_usd,haircut=haircut)
    db.add(c);db.commit()
    return {"user_id":user_id,"asset":asset,"adjusted_value":str(market_value_usd*haircut)}

@app.get("/margin/{user_id}")
def margin(user_id:int,db:Session=Depends(get_db)):
    rows=db.query(Collateral).filter_by(user_id=user_id).all()
    adjusted=sum(Decimal(str(x.market_value_usd))*Decimal(str(x.haircut)) for x in rows)
    return {"user_id":user_id,"adjusted_collateral_usd":str(adjusted)}

@app.get("/risk/leverage")
def leverage(jurisdiction:str="PK",client_type:str="retail",asset_class:str="crypto"):
    # Placeholder configuration only; not a statement of real regulatory limits.
    table={"PK":{"retail":{"crypto":2,"forex":2,"stocks":1},"professional":{"crypto":5,"forex":5,"stocks":2}}}
    value=table.get(jurisdiction,table["PK"]).get(client_type,table["PK"]["retail"]).get(asset_class,1)
    return {"jurisdiction":jurisdiction,"client_type":client_type,"asset_class":asset_class,
            "configured_limit":value,"note":"Assessment placeholder; verify applicable law before production use."}

# ---------- AI agents ----------
@app.post("/agents")
def create_agent(data:AgentIn,db:Session=Depends(get_db)):
    a=Agent(name=data.name,strategy=data.strategy,sharpe=data.sharpe,max_position=data.max_position,
            paper_trading=data.paper_trading,verified=False)
    db.add(a);db.commit();db.refresh(a)
    return {"id":a.id,"name":a.name,"sharpe":str(a.sharpe),"paper_trading_badge":a.paper_trading,"verified":a.verified}

@app.get("/agents")
def agents(db:Session=Depends(get_db)):
    return [{"id":a.id,"name":a.name,"strategy":a.strategy,"sharpe":str(a.sharpe),
             "max_position":str(a.max_position),"paper_trading":a.paper_trading,"verified":a.verified}
            for a in db.query(Agent).all()]

# ---------- Transparency ----------
@app.post("/transparency/proof-of-reserves")
def proof_of_reserves(db:Session=Depends(get_db)):
    # Mock snapshot. In production this would require auditable asset/liability sources.
    assets=Decimal("1000000")
    liabilities=Decimal("850000")
    r=ReserveSnapshot(total_assets_usd=assets,total_liabilities_usd=liabilities)
    db.add(r);db.commit();db.refresh(r)
    return {"snapshot_id":r.id,"assets_usd":str(assets),"liabilities_usd":str(liabilities),
            "coverage_ratio":str(assets/liabilities),"status":"MOCK_ASSESSMENT_DATA"}

@app.get("/transparency/proof-of-reserves")
def latest_reserve(db:Session=Depends(get_db)):
    r=db.query(ReserveSnapshot).order_by(ReserveSnapshot.id.desc()).first()
    if not r: return {"message":"No snapshot yet"}
    return {"snapshot_id":r.id,"assets_usd":str(r.total_assets_usd),
            "liabilities_usd":str(r.total_liabilities_usd),
            "coverage_ratio":str(Decimal(str(r.total_assets_usd))/Decimal(str(r.total_liabilities_usd))),
            "created_at":r.created_at.isoformat()}


@app.get("/demo/bootstrap")
def demo_bootstrap(email: str = "demo@fintech.local", db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=email).first()
    if not user:
        u = User(email=email, jurisdiction="PK")
        db.add(u); db.commit(); db.refresh(u)
        db.add(KYCProfile(user_id=u.id, tier=0, status="NOT_STARTED",
                          requirements=json.dumps(["identity"])))
        db.commit()
        user = u
    return {"id": user.id, "email": user.email, "jurisdiction": user.jurisdiction}

# ---------- Single-server frontend ----------
# After `npm run build`, FastAPI serves the React application from frontend/dist.
# API routes above remain available at the same host, so the browser uses one origin.
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(os.path.join(FRONTEND_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="frontend-assets")

@app.get("/", include_in_schema=False)
def frontend_home():
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "SynxEx MVP API is running. Build the frontend with: cd frontend; npm install; npm run build"}

@app.get("/{frontend_path:path}", include_in_schema=False)
def frontend_fallback(frontend_path: str):
    # Let React Router handle browser-side routes such as /accounts and /trading.
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")

