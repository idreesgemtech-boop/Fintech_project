from decimal import Decimal
from uuid import uuid4
from ..models import LedgerEntry, LedgerAccount

def post_double_entry(db, debit_account_id, credit_account_id, amount, currency):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Amount must be positive")
    txid = str(uuid4())
    db.add(LedgerEntry(transaction_id=txid, ledger_account_id=debit_account_id,
                       debit=amount, credit=0, currency=currency))
    db.add(LedgerEntry(transaction_id=txid, ledger_account_id=credit_account_id,
                       debit=0, credit=amount, currency=currency))
    return txid
