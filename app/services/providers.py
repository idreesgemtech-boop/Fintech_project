from datetime import datetime, timedelta
from decimal import Decimal

MOCK_PROVIDERS = {
    "ProviderA": {"fee": Decimal("8"), "network": Decimal("1.5"), "spread": Decimal("3")},
    "ProviderB": {"fee": Decimal("5"), "network": Decimal("1"), "spread": Decimal("2")},
    "ProviderC": {"fee": Decimal("10"), "network": Decimal("0.5"), "spread": Decimal("4")},
}

def provider_quotes(source_amount, corridor):
    rate = Decimal("278")
    result = []
    for name, costs in MOCK_PROVIDERS.items():
        total = costs["fee"] + costs["network"] + costs["spread"]
        recipient = Decimal(str(source_amount)) * rate - total * rate / Decimal("100")
        result.append({
            "provider": name,
            "corridor": corridor,
            "fx_rate": rate,
            "provider_fee": costs["fee"],
            "network_fee": costs["network"],
            "fx_spread": costs["spread"],
            "total_cost": total,
            "recipient_amount": recipient,
            "expires_at": datetime.utcnow() + timedelta(seconds=60)
        })
    return result
