"""Pinned visible-depth fill helper from PR149; public market observations only."""
import math
MAX_QUOTE_AGE_MS = 5000

def depth_fill(book: dict, quantity: float, buy: bool, now: int) -> float:
    if not 0 <= now-int(book['ts']) <= MAX_QUOTE_AGE_MS:
        raise ValueError('stale_or_future_quote')
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValueError('invalid_quantity')
    bids, asks = book['b'], book['a']
    if not bids or not asks or float(bids[0][0]) >= float(asks[0][0]):
        raise ValueError('empty_or_crossed_book')
    for levels, sign in [(bids, -1), (asks, 1)]:
        prior = None
        for px, sz in levels:
            px, sz = float(px), float(sz)
            if not math.isfinite(px+sz) or px <= 0 or sz <= 0:
                raise ValueError('invalid_depth')
            if prior is not None and sign*(px-prior) <= 0:
                raise ValueError('unsorted_depth')
            prior = px
    remain = quantity; amount = 0.
    for px, size in asks if buy else bids:
        take = min(remain, float(size)); amount += take*float(px); remain -= take
        if remain <= quantity*1e-12:
            return amount/quantity
    raise ValueError('insufficient_visible_depth')
