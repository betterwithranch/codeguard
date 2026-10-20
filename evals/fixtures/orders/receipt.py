from orders.order import Order


def receipt(customer_name: str, order: Order) -> str:
    return f"{customer_name}: {order.total()}"
