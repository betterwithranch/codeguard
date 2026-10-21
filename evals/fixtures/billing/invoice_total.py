from dataclasses import dataclass


@dataclass(frozen=True)
class InvoiceTotal:
    amount: int
