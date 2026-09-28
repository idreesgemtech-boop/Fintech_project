from decimal import Decimal

def find_matches(db, incoming):
    from ..models import Order, Trade
    matches = db.query(Order).filter(
        Order.symbol == incoming.symbol,
        Order.status == "OPEN",
        Order.side != incoming.side
    ).order_by(Order.created_at.asc()).all()

    for other in matches:
        compatible = (
            incoming.side == "BUY" and Decimal(str(incoming.price)) >= Decimal(str(other.price))
        ) or (
            incoming.side == "SELL" and Decimal(str(incoming.price)) <= Decimal(str(other.price))
        )
        if not compatible:
            continue

        qty = min(Decimal(str(incoming.remaining_quantity)), Decimal(str(other.remaining_quantity)))
        if qty <= 0:
            continue

        price = Decimal(str(other.price))
        db.add(Trade(
            buy_order_id=incoming.id if incoming.side == "BUY" else other.id,
            sell_order_id=incoming.id if incoming.side == "SELL" else other.id,
            symbol=incoming.symbol,
            quantity=qty,
            price=price
        ))
        incoming.remaining_quantity -= qty
        other.remaining_quantity -= qty
        incoming.status = "FILLED" if incoming.remaining_quantity == 0 else "PARTIALLY_FILLED"
        other.status = "FILLED" if other.remaining_quantity == 0 else "PARTIALLY_FILLED"
        if incoming.remaining_quantity == 0:
            break
