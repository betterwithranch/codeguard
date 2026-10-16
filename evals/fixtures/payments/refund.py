import logging

logger = logging.getLogger(__name__)


def refund(gateway, amount: int) -> None:
    try:
        gateway.refund(amount)
    except gateway.Error:
        logger.exception("Refund failed")
        raise
