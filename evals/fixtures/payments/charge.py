def charge(gateway, amount: int) -> None:
    try:
        gateway.charge(amount)
    except Exception:
        pass
