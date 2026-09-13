#!/usr/bin/env python3
from __future__ import annotations
import csv, gzip, hashlib, json, sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
ROOT = Path(__file__).resolve().parents[1]
SELF_SERVE = ('explorer_lite_v1','starter_kit_v1','explorer_studio_v1')

def load(path): return json.loads((ROOT/path).read_text())
def canonical(url):
    p=urlsplit(url); return urlunsplit((p.scheme,p.netloc,p.path,p.query if not p.query.startswith('utm_') else '',p.fragment))
def fail(msg): raise AssertionError(msg)
def indexed(rows): return {row['id']: row for row in rows}

def validate():
    catalog=load('agent/catalog.json'); product=load('agent/product.json'); purchase=load('agent/purchase.json'); intents=load('agent/buyer-intents.json')
    c=indexed(catalog['products']); p=indexed(product['products']); o=indexed(purchase['offers']); i=indexed(intents['product_family'])
    for label, rows in [('catalog',c),('product',p),('buyer_intents',i)]:
        if tuple(rows) != SELF_SERVE: fail(f'{label}: self-serve IDs/order drifted: {tuple(rows)}')
    purchase_self_serve = tuple(pid for pid in o if pid in SELF_SERVE)
    if purchase_self_serve != SELF_SERVE:
        fail(f'purchase: self-serve IDs/order drifted: {purchase_self_serve}')
    for pid in SELF_SERVE:
        price=c[pid]['price_usd']; checkout=c[pid]['checkout_url']; url=c[pid]['url']
        if p[pid]['price'] != {'currency':'USD','amount':price}: fail(f'{pid}: product price drift')
        if o[pid]['price_usd'] != price or i[pid]['price_usd'] != price: fail(f'{pid}: agent price drift')
        if any(row['checkout_url'] != checkout for row in (p[pid],o[pid],i[pid])): fail(f'{pid}: checkout URL drift')
        if p[pid]['url'] != url or i[pid]['url'] != url: fail(f'{pid}: product URL drift')
        if not (p[pid]['available_for_sale'] and p[pid]['requires_shipping'] is False): fail(f'{pid}: sale/shipping readiness drift')
        if c[pid]['availability'] != {'available':True,'status':'in_stock'} or c[pid]['requires'] != {'shipping':False}: fail(f'{pid}: catalog readiness drift')
    service=catalog['service']; quick=o.get(service['id'])
    if not quick: fail('Quickstart missing from purchase offers')
    for key in ('price_usd','checkout_url'):
        if quick[key] != service[key]: fail(f'Quickstart {key} drift')
    feed=[json.loads(line) for line in (ROOT/'feeds/openai-products.jsonl').read_text().splitlines() if line.strip()]
    with (ROOT/'feeds/google-products.csv').open(newline='') as google_file:
        google=list(csv.DictReader(google_file))
    if len(feed) != 3 or len(google) != 3: fail('feed record count drift')
    by_price={c[pid]['price_usd']:pid for pid in SELF_SERVE}
    for row in feed:
        amount=int(float(row['price'].split()[0])); pid=by_price.get(amount)
        if not pid: fail(f'OpenAI feed unexpected price {row["price"]}')
        if canonical(row['url']) != c[pid]['url']: fail(f'{pid}: OpenAI product URL drift')
        if row['image_url'] != p[pid]['image_url']: fail(f'{pid}: OpenAI image drift')
        if not row['is_eligible_search'] or row['is_eligible_checkout']: fail(f'{pid}: OpenAI eligibility drift')
    for row in google:
        amount=int(float(row['price'].split()[0])); pid=by_price.get(amount)
        if not pid: fail(f'Google feed unexpected price {row["price"]}')
        if canonical(row['link']) != c[pid]['url']: fail(f'{pid}: Google product URL drift')
        if row['image_link'] != p[pid]['image_url']: fail(f'{pid}: Google image drift')
    stale_tokens = ('Starter Kit v1', 'planned Agency License', 'Studio Pack v1')
    for page in ROOT.glob('*.html'):
        text = page.read_text()
        for token in stale_tokens:
            if token in text: fail(f'{page.name}: stale public product copy: {token}')
    raw=(ROOT/'feeds/openai-products.jsonl').read_bytes(); compressed=(ROOT/'feeds/openai-products.jsonl.gz').read_bytes(); manifest=load('feeds/feed-manifest.json')
    if gzip.decompress(compressed) != raw: fail('compressed feed is not byte-identical to JSONL source')
    if manifest['record_count'] != len(feed): fail('feed manifest record_count drift')
    if manifest['sha256_uncompressed'] != hashlib.sha256(raw).hexdigest(): fail('feed manifest SHA-256 drift')
    return {'products':len(SELF_SERVE),'service':service['id'],'feed_records':len(feed),'sha256':hashlib.sha256(raw).hexdigest()}

if __name__=='__main__':
    try: result=validate()
    except (AssertionError, KeyError, TypeError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(f'COMMERCE_CONSISTENCY_FAIL: {exc}', file=sys.stderr); raise SystemExit(2)
    print('COMMERCE_CONSISTENCY_PASS ' + json.dumps(result, sort_keys=True))
