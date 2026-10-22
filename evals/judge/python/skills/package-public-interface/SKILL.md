---
name: package-public-interface
description: Code outside a package imports from the package root.
---

# Package public interface

Code outside a package imports what the package exports from the package root (`from billing import InvoiceTotal`), not from the module that defines it (`from billing.invoice_total import InvoiceTotal`).

The exception is a cycle. Before reporting an import from a module, read the package's `__init__.py`: when it imports the file under review, importing through the root would create a cycle, so importing the module is correct.
