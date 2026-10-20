from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    price: int
    quantity: int


@dataclass(frozen=True)
class Order:
    lines: tuple[Line, ...]

    def total(self) -> int:
        return sum(line.price * line.quantity for line in self.lines)
