from orders.order import Order


def invoice_amount(order: Order) -> int:
    return sum(line.price * line.quantity for line in order.lines)
