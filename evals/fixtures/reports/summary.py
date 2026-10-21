from ledger.entry import Entry


def summarize(amounts):
    return Entry(amount=sum(amounts))
