---
name: derive-known-values
description: A list of values the code already defines is derived from that definition.
---

# Derive known values

A list of values the code already defines in one place is derived from that definition,
not written out again.

## Violation

A list, set, tuple, union type or the keys of a mapping, written by hand, whose items are
the members of a definition the code already has. It is reported on the line that writes
the items out.

## Not a violation

- Values that match a definition's members by coincidence but mean something else.
- The definition itself.

## Why

A hand-written copy goes stale when a member is added to the definition, and nothing fails:
the new member is silently missing wherever the copy is used.
