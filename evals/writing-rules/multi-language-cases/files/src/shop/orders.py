from enum import Enum


class OrderStatus(Enum):
    OPEN = "open"
    PAID = "paid"
    SHIPPED = "shipped"


STATUS_CHOICES = tuple(status.value for status in OrderStatus)
