"""Seleção de compras com validade conhecida para consulta de códigos."""
from datetime import datetime, timedelta

import pytz


TZ = pytz.timezone('America/Sao_Paulo')


def purchase_expiry(purchase):
    try:
        if purchase.get('expira_em'):
            expiry = datetime.fromisoformat(purchase['expira_em'])
            return TZ.localize(expiry) if expiry.tzinfo is None else expiry
        days = int(purchase['duracao'])
        if days <= 0:
            return None
        date = str(purchase['data']).replace(' às ', ' ').replace(' as ', ' ')
        return TZ.localize(datetime.strptime(date, '%d/%m/%Y %H:%M:%S')) + timedelta(days=days)
    except (KeyError, ValueError, TypeError, OverflowError):
        return None


def active_purchases(purchases, now=None):
    now = now or datetime.now(TZ)
    result = []
    for index, purchase in enumerate(purchases):
        expiry = purchase_expiry(purchase)
        if expiry is not None and expiry > now and purchase.get('email'):
            result.append((index, purchase, expiry))
    return list(reversed(result))
