# TypeScript

Keeps the convention:

- A type taken from an `as const` array: `type Size = (typeof SIZES)[number]`.
- `Object.values(Size)` over an `enum`.

Breaks it:

- A union type such as `"s" | "m" | "l"` written out beside an `as const` array that
  holds those values.
- An array of an `enum`'s values written out beside the `enum`.
