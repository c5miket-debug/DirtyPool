#!/usr/bin/env python3
"""Free/delayed-ish price snapshot.

Crypto: CoinGecko simple price.
Stocks: Stooq (free) close/last; may be delayed.

Outputs JSON with keys.
"""

import argparse
import json
import ssl
import urllib.parse
import urllib.request


def fetch_json(url: str):
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
        return json.loads(r.read().decode('utf-8','ignore'))


def fetch_text(url: str):
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
        return r.read().decode('utf-8','ignore')


def stooq_quote(symbol: str):
    """Fetch last 2 daily bars from Stooq and compute day change vs previous close."""
    s = symbol.lower()
    # Historical daily CSV (header + many rows)
    url = f'https://stooq.com/q/d/l/?s={urllib.parse.quote(s)}&i=d'
    lines = [l for l in fetch_text(url).strip().splitlines() if l.strip()]
    if len(lines) < 3:
        return None
    header = lines[0].split(',')
    # Expect: Date,Open,High,Low,Close,Volume
    def parse_row(line: str):
        parts = line.split(',')
        if len(parts) < 6:
            return None
        date, o, h, lo, c, v = parts[:6]
        try:
            return {
                'date': date.replace('-', ''),
                'open': float(o) if o else None,
                'high': float(h) if h else None,
                'low': float(lo) if lo else None,
                'close': float(c) if c else None,
                'volume': int(float(v)) if v else None,
            }
        except Exception:
            return None

    last = parse_row(lines[-1])
    prev = parse_row(lines[-2])
    if not last:
        return None

    chg_abs = None
    chg_pct = None
    if prev and prev.get('close') is not None and last.get('close') is not None and prev.get('close') != 0:
        chg_abs = last['close'] - prev['close']
        chg_pct = (chg_abs / prev['close']) * 100.0

    return {
        'source': 'stooq',
        'symbol': symbol.upper(),
        'close': last.get('close'),
        'date': last.get('date'),
        'open': last.get('open'),
        'high': last.get('high'),
        'low': last.get('low'),
        'volume': last.get('volume'),
        'chg_1d_abs': chg_abs,
        'chg_1d_pct': chg_pct,
        'prev_close': prev.get('close') if prev else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--crypto', nargs='*', default=['bitcoin','solana'])
    ap.add_argument('--stocks', nargs='*', default=['TSLA','MSTR','PLTR','AMZN','GOOGL','NVDA'])
    args = ap.parse_args()

    # CoinGecko ids -> usd + 24h change
    # Note: HYPE = Hyperliquid token (CoinGecko id: "hyperliquid").
    cg_ids_list = list(dict.fromkeys([*args.crypto, 'hyperliquid']))
    cg_ids = ','.join(cg_ids_list)
    cg_url = 'https://api.coingecko.com/api/v3/simple/price?' + urllib.parse.urlencode({
        'ids': cg_ids,
        'vs_currencies': 'usd',
        'include_24hr_change': 'true'
    })
    crypto = fetch_json(cg_url)

    out = {'crypto': {}, 'stocks': {}}

    for cid in args.crypto:
        d = crypto.get(cid, {})
        usd = d.get('usd')
        pct = d.get('usd_24h_change')
        chg_abs = None
        if usd is not None and pct is not None:
            try:
                prev = usd / (1.0 + (pct/100.0))
                chg_abs = usd - prev
            except Exception:
                chg_abs = None
        out['crypto'][cid] = {
            'usd': usd,
            'chg_24h_abs': chg_abs,
            'chg_24h_pct': pct,
            'source': 'coingecko'
        }

    # HYPE: Hyperliquid (CoinGecko id: hyperliquid)
    hype = crypto.get('hyperliquid', {})
    hype_usd = hype.get('usd')
    hype_pct = hype.get('usd_24h_change')
    hype_abs = None
    if hype_usd is not None and hype_pct is not None:
        try:
            prev = hype_usd / (1.0 + (hype_pct/100.0))
            hype_abs = hype_usd - prev
        except Exception:
            hype_abs = None
    out['crypto']['hype'] = {
        'usd': hype_usd,
        'chg_24h_abs': hype_abs,
        'chg_24h_pct': hype_pct,
        'source': 'coingecko' if hype_usd is not None else 'n/a'
    }

    # Stocks: Stooq uses suffix .US for US tickers; GOOGL sometimes as GOOGL.US
    mapping = {
        'TSLA': 'tsla.us',
        'MSTR': 'mstr.us',
        'PLTR': 'pltr.us',
        'AMZN': 'amzn.us',
        'GOOGL': 'googl.us',
        'NVDA': 'nvda.us'
    }

    for sym in args.stocks:
        qsym = mapping.get(sym.upper())
        if not qsym:
            out['stocks'][sym] = None
            continue
        out['stocks'][sym] = stooq_quote(qsym)

    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
