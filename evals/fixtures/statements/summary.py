from billing.invoice_total import InvoiceTotal


def summarize(amounts):
    return InvoiceTotal(amount=sum(amounts))
