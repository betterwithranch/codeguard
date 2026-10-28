# Python

Keeps the convention:

- `tuple(Color)`, `frozenset(Color)` or `[color.value for color in Color]` over an `Enum`.
- `typing.get_args(Size)` for the values of a `Literal` alias.

Breaks it:

- A tuple, list or set of an `Enum`'s values written out beside the `Enum`.
- `Literal["s", "m", "l"]` written again where a `Size` alias already lists those values.
