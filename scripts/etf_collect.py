"""Independent ETF collectors. Percentages are provider values, never price-derived."""
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))
QUOTE_KEYS = ('price', 'change_pct', 'amount')
RETURN_KEYS = ('return_1y',)

def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def snapshots(data):
    paths = [data / 'latest.json', *sorted((data / 'history').glob('*.json'), reverse=True)]
    result = []
    for path in paths:
        try:
            payload = json.loads(path.read_text('utf-8'))
            if isinstance(payload.get('etf'), list):
                result.append(payload)
        except (OSError, ValueError, AttributeError):
            continue
    return result

def previous_valid(history, code, keys):
    for payload in history:
        for row in payload.get('etf', []):
            if row.get('code') == code and all(numeric(row.get(k)) for k in keys):
                return row
    return {}

def request_retry(operation, deadline, attempts=3):
    errors = []
    for attempt in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0.1:
            break
        try:
            return operation(min(2.5, remaining))
        except Exception as exc:
            errors.append(str(exc))
            if attempt + 1 < attempts:
                time.sleep(min(0.2 * 2**attempt, max(0, deadline - time.monotonic())))
    raise RuntimeError('; '.join(errors) or 'collection deadline exceeded')

def fetch_etf_quote(code, get, deadline):
    market = 1 if code.startswith(('5', '6')) else 0
    url = (f'https://push2.eastmoney.com/api/qt/stock/get?secid={market}.{code}'
           '&fields=f43,f48,f57,f59,f86,f170')
    def load(timeout):
        d = json.loads(get(url, timeout=timeout)).get('data') or {}
        if str(d.get('f57')) != code:
            raise ValueError('quote code mismatch or empty data')
        precision = int(d['f59'])
        if precision < 0 or precision > 6:
            raise ValueError('invalid quote precision')
        result = {'price': float(d['f43']) / 10**precision,
                  'change_pct': float(d['f170']) / 100,
                  'amount': float(d['f48'])}
        if not all(numeric(v) for v in result.values()) or result['price'] <= 0 or result['amount'] < 0:
            raise ValueError('invalid quote values')
        stamp = datetime.fromtimestamp(int(d['f86']), TZ)
        if stamp.year < 2000 or stamp > datetime.now(TZ) + timedelta(days=1):
            raise ValueError('invalid quote timestamp')
        return {**result, 'quote_effective_date': stamp.date().isoformat(),
                'quote_source': url, 'quote_status': 'live'}
    try:
        return request_retry(load, deadline)
    except Exception as primary:
        prefix = 'sh' if market else 'sz'
        secondary_url = f'https://qt.gtimg.cn/q={prefix}{code}'
        def secondary(timeout):
            raw = get(secondary_url, timeout=timeout)
            match = re.search(r'="([^"\r\n]+)"', raw)
            fields = match[1].split('~') if match else []
            if len(fields) < 38 or fields[2] != code:
                raise ValueError('Tencent quote code mismatch')
            # Provider's price/volume/amount tuple reports amount directly in CNY.
            amount = float(fields[35].split('/')[2])
            values = {'price': float(fields[3]), 'change_pct': float(fields[32]), 'amount': amount}
            if not all(numeric(v) for v in values.values()) or values['price'] <= 0 or amount < 0:
                raise ValueError('invalid Tencent quote')
            stamp = datetime.strptime(fields[30], '%Y%m%d%H%M%S').replace(tzinfo=TZ)
            if stamp.year < 2000 or stamp > datetime.now(TZ) + timedelta(days=1):
                raise ValueError('invalid Tencent timestamp')
            return {**values, 'quote_effective_date': stamp.date().isoformat(),
                    'quote_source': secondary_url, 'quote_status': 'live',
                    'quote_primary_error': str(primary)}
        try:
            return request_retry(secondary, deadline, attempts=1)
        except Exception as secondary_error:
            raise RuntimeError(f'Eastmoney: {primary}; Tencent: {secondary_error}') from secondary_error

def parse_pingzhong(raw, code):
    match = re.search(r'\bvar\s+fS_code\s*=\s*[\"\'](\d+)[\"\']', raw)
    if not match or match[1] != code:
        raise ValueError('fund code mismatch')
    # 1n means one YEAR; 1y means one MONTH in this provider's schema.
    match = re.search(r'\bvar\s+syl_1n\s*=\s*[\"\']([-+]?\d+(?:\.\d+)?)[\"\']', raw)
    if not match:
        raise ValueError('missing syl_1n')
    trend = re.search(r'\bvar\s+Data_netWorthTrend\s*=\s*(\[.*?\])\s*;', raw, re.S)
    points = json.loads(trend[1]) if trend else []
    if not points:
        raise ValueError('missing NAV date for return')
    date = datetime.fromtimestamp(max(p['x'] for p in points) / 1000, TZ).date().isoformat()
    value = float(match[1])
    if not numeric(value):
        raise ValueError('invalid annual return')
    return value, date

def fetch_etf_return(code, get, parser, deadline):
    url = f'https://fund.eastmoney.com/pingzhongdata/{code}.js'
    try:
        value, date = request_retry(lambda timeout: parse_pingzhong(get(url, timeout=timeout), code), deadline, attempts=2)
    except Exception as first:
        # Exact table column + exact fund row; never a nearby arbitrary percentage.
        url = f'https://fund.eastmoney.com/{code}.html'
        def load(timeout):
            raw = get(url, timeout=timeout)
            table_parser = parser(); table_parser.feed(raw)
            date_match = re.search(r'id=[\"\']jdzfDate[\"\'][^>]*>\s*(\d{4}-\d{2}-\d{2})', raw)
            if not date_match:
                raise ValueError('missing stage return date')
            for table in table_parser.tables:
                if not table or '近1年' not in table[0]:
                    continue
                col = table[0].index('近1年')
                for row in table[1:]:
                    if row[0].strip() == '阶段涨幅' and len(row) > col:
                        m = re.fullmatch(r'\s*([-+]?\d+(?:\.\d+)?)%\s*', row[col])
                        if m:
                            return float(m[1]), date_match[1]
            raise ValueError('missing exact annual stage return column')
        try:
            value, date = request_retry(load, deadline, attempts=1)
        except Exception as second:
            raise RuntimeError(f'pingzhongdata: {first}; stage table: {second}') from second
    return {'return_1y': value, 'return_1y_date': date, 'return_1y_source': url,
            'return_1y_status': 'live', 'return_1y_stale': False}

def merge_etf_data(metadata, quote, returns, history, errors):
    code = metadata['code']
    row = {**metadata, 'market': 1 if code.startswith(('5', '6')) else 0,
           'updated_at': datetime.now(TZ).isoformat(timespec='seconds')}
    if quote is None:
        old_fields = {k: previous_valid(history, code, (k,)) for k in QUOTE_KEYS}
        quote = {k: old_fields[k].get(k) for k in QUOTE_KEYS}
        dates = {k: old_fields[k].get('quote_effective_date') for k in QUOTE_KEYS}
        source = next((r.get('quote_source') for r in old_fields.values() if r.get('quote_source')), None)
        quote.update(quote_status='fallback' if any(numeric(v) for v in quote.values()) else 'unavailable',
                     quote_effective_date=next(iter(dates.values())) if len(set(dates.values())) == 1 else None,
                     quote_field_dates=dates,
                     quote_source=source or ('legacy Eastmoney snapshot; effective date unknown' if any(old_fields.values()) else None))
    if returns is None:
        old = previous_valid(history, code, RETURN_KEYS)
        returns = {k: old.get(k) for k in ('return_1y', 'return_1y_date', 'return_1y_source')}
        returns.update(return_1y_status='stale' if old else 'unavailable', return_1y_stale=bool(old))
    row.update(quote); row.update(returns)
    if errors:
        row['collection_errors'] = errors
    return row

def collect_etfs(master, get, parser, history, deadline):
    results = {code: {} for code in master}
    errors = {code: [] for code in master}
    # A single shared pool caps ETF network concurrency at four across both sources.
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {}
        for code in master:
            jobs[pool.submit(fetch_etf_quote, code, get, deadline)] = (code, 'quote')
            jobs[pool.submit(fetch_etf_return, code, get, parser, deadline)] = (code, 'return')
        for job in as_completed(jobs):
            code, group = jobs[job]
            try:
                results[code][group] = job.result()
            except Exception as exc:
                errors[code].append({'source': group, 'error': str(exc)})
    return [merge_etf_data(meta, results[code].get('quote'), results[code].get('return'), history, errors[code])
            for code, meta in master.items()]

def sort_otc(rows):
    totals = {}
    for row in rows:
        key = (row['index'], row.get('fund_company') or row['code'])
        row['fund_total_quota'] = sum(row.get(k) if numeric(row.get(k)) else 0 for k in ('agency_limit', 'direct_limit'))
        totals[key] = totals.get(key, 0) + row['fund_total_quota']
    for row in rows:
        row['company_total_quota'] = totals[(row['index'], row.get('fund_company') or row['code'])]
    return sorted(rows, key=lambda x: (x['index'], -x['company_total_quota'], x.get('fund_company') or x['code'],
                                      -x['fund_total_quota'], x.get('share_class') or 'ZZ', x['code']))

def validate(payload, history):
    rows = payload['etf']
    codes = {r['code'] for r in rows}
    if len(codes) != len(rows):
        raise ValueError('duplicate ETF codes')
    for index, minimum in [('NDX100', 10), ('SP500', 4)]:
        if sum(r['index'] == index for r in rows) < minimum:
            raise ValueError(f'insufficient products: {index}')
    if not {'513100', '159941', '513300', '513500'} <= codes:
        raise ValueError('required ETFs missing')
    if history and not {r['code'] for r in history[0]['etf']} <= codes:
        raise ValueError('ETF product lost relative to previous snapshot')
    if sum(not numeric(r.get('price')) for r in rows) / len(rows) > 0.2:
        raise ValueError('over 20% ETF prices missing')
    if not any(numeric(r.get('return_1y')) for r in rows):
        raise ValueError('all ETF annual returns missing; collector broken')
    if len(payload['otc']) < 40:
        raise ValueError('insufficient OTC products')
    if history and not {r['code'] for r in history[0].get('otc', [])} <= {r['code'] for r in payload['otc']}:
        raise ValueError('OTC product lost relative to previous snapshot')

def publish(payload, data, history):
    validate(payload, history)
    content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    temp = data / 'latest.tmp.json'
    temp.write_text(content, 'utf-8')
    temp.replace(data / 'latest.json')
    target = data / 'history' / (payload['date'] + '.json')
    temp = target.with_suffix('.tmp')
    temp.write_text(content, 'utf-8'); temp.replace(target)
