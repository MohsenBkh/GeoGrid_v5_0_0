"""Multi-feeder discrete planning with explicit ties and shared reserves.

The NetworkX flow restoration is an optimistic screening model, not a power
flow, radial switching plan, or validated TAV engineering result.
"""
from itertools import combinations
from math import comb, isfinite
from .placement import analyze
from .n1 import calculate as n1_calculate


def _number(value, what):
    try: v = float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f'{what}: مقدار عددی لازم است') from exc
    if not isfinite(v) or v < 0: raise ValueError(f'{what}: باید متناهی و نامنفی باشد')
    return v


def validate_model(model):
    feeders, nodes, branches, ties = model['feeders'], model['nodes'], model['branches'], model['ties']
    fmap = {}; nmap = {}; bmap = {}; tids = set()
    for f in feeders:
        fid = str(f.get('id') or '').strip(); root = str(f.get('root') or '').strip()
        if not fid or not root or fid in fmap: raise ValueError('شناسه یا مبدأ فیدر خالی یا تکراری است')
        fmap[fid] = dict(f, id=fid, root=root, reserve_kw=_number(f.get('reserve_kw'), f'رزرو {fid}'))
    if len(fmap) < 2: raise ValueError('حداقل دو فیدر لازم است')
    for n in nodes:
        nid = str(n.get('id') or '').strip(); fid = str(n.get('feeder') or '').strip()
        if not nid or nid in nmap or fid not in fmap: raise ValueError('شناسه گره تکراری یا فیدر نامعتبر است')
        _number(n.get('load_kw'), f'بار گره {nid}')
        for coord in ('x', 'y'):
            try: v = float(n[coord])
            except (KeyError, ValueError, TypeError) as exc: raise ValueError(f'مختصات {coord} گره {nid} لازم است') from exc
            if not isfinite(v): raise ValueError(f'مختصات گره {nid} نامعتبر است')
        nmap[nid] = dict(n, id=nid, feeder=fid)
    for fid, f in fmap.items():
        if f['root'] not in nmap or nmap[f['root']]['feeder'] != fid: raise ValueError(f'مبدأ فیدر {fid} نامعتبر است')
    for b in branches:
        bid = str(b.get('id') or '').strip(); fid = str(b.get('feeder') or '').strip()
        a = str(b.get('from_node') or '').strip(); z = str(b.get('to_node') or '').strip()
        if not bid or bid in bmap or fid not in fmap or a not in nmap or z not in nmap or nmap[a]['feeder'] != fid or nmap[z]['feeder'] != fid:
            raise ValueError('شناسه، فیدر یا دو سر شاخه نامعتبر است')
        _number(b.get('capacity_kw'), f'ظرفیت شاخه {bid}')
        bmap[bid] = dict(b, id=bid, feeder=fid, from_node=a, to_node=z)
    valid_ties = []
    for t in ties:
        tid = str(t.get('id') or '').strip(); a = str(t.get('node_a') or '').strip(); b = str(t.get('node_b') or '').strip()
        if not tid or tid in tids or a not in nmap or b not in nmap or nmap[a]['feeder'] == nmap[b]['feeder']:
            raise ValueError('شناسه یا دو سر رابط بین فیدرها نامعتبر است')
        tids.add(tid)
        if str(t.get('normal_status') or '').strip().lower() != 'open' or type(t.get('automated')) is not bool:
            raise ValueError(f'{tid}: وضعیت باید open و اتوماسیون بولی باشد')
        valid_ties.append(dict(t, id=tid, node_a=a, node_b=b,
                               capacity_kw=_number(t.get('capacity_kw'), f'ظرفیت رابط {tid}'), normal_status='open'))
    if not valid_ties: raise ValueError('حداقل یک اتصال رابط بین فیدرها لازم است')
    # Require each feeder radial and all branch data valid even before search.
    for fid, f in fmap.items():
        analyze([n for n in nmap.values() if n['feeder'] == fid],
                [b for b in bmap.values() if b['feeder'] == fid], f['root'], 0, forced=[])
    return fmap, nmap, bmap, valid_ties


def evaluate(model, selected, _validated=None):
    fmap, nmap, bmap, ties = _validated or validate_model(model)
    selected = list(selected)
    eligible = {k for k, b in bmap.items() if b['candidate'] and not b['existing_switch']}
    if len(set(selected)) != len(selected) or not set(selected) <= eligible: raise ValueError('کلید پیشنهادی نامعتبر یا تکراری است')
    feeder_results = []; proposals = []
    for fid in sorted(fmap):
        f = fmap[fid]; nodes = [n for n in nmap.values() if n['feeder'] == fid]
        branches = [b for b in bmap.values() if b['feeder'] == fid]
        selected_here = [b for b in selected if bmap[b]['feeder'] == fid]
        plan = analyze(nodes, branches, f['root'], len(selected_here), forced=selected_here)
        for p in plan['proposals']:
            p['feeder'] = fid; p['reason'] = 'بهینه‌سازی مدل اکتشافی چندفیدری و ظرفیت رزرو'
            proposals.append(p)
        node_zone = {node: z['root'] for z in plan['zones'] for node in z['nodes']}
        zone_items = [{'zone': z['root'], 'feeder': fid, 'load_kw': z['load_kw']} for z in plan['zones']]
        zone_links = []
        for b in branches:
            a = node_zone[b['from_node']]; z = node_zone[b['to_node']]
            if a != z:
                zone_links.append({'from_zone': a, 'to_zone': z, 'switchable': True, 'capacity_kw': b['capacity_kw']})
        zone_ties = []
        for t in ties:
            a = nmap[t['node_a']]; b = nmap[t['node_b']]
            if a['feeder'] == fid: target, backup = t['node_a'], b['feeder']
            elif b['feeder'] == fid: target, backup = t['node_b'], a['feeder']
            else: continue
            zone_ties.append({'id': t['id'], 'zone': node_zone[target], 'backup_feeder': backup,
                'reserve_kw': fmap[backup]['reserve_kw'], 'capacity_kw': t['capacity_kw'],
                'normal_status': t['normal_status'], 'automated': t['automated']})
        faults = n1_calculate(zone_items, zone_links, zone_ties, fid, node_zone[f['root']])
        zone_by_id = {z['root']: z for z in plan['zones']}
        for scenario in faults['scenarios']:
            scenario['u_hours_per_year'] = zone_by_id[scenario['failed_zone']]['u_hours_per_year']
            scenario['ens_kwh_per_year'] = scenario['u_hours_per_year'] * scenario['interrupted_kw']
        ens = sum(x['ens_kwh_per_year'] for x in faults['scenarios'])
        if not isfinite(ens): raise ValueError('سرریز در انرژی توزیع نشده')
        feeder_results.append({'feeder': fid, 'zones': plan['zones'], 'scenarios': faults['scenarios'], 'ens_kwh_per_year': ens})
    total = sum(f['ens_kwh_per_year'] for f in feeder_results)
    if not isfinite(total): raise ValueError('سرریز در انرژی کل')
    return {'selected': sorted(selected), 'proposals': proposals, 'feeders': feeder_results, 'ens_kwh_per_year': total,
        'warnings': ['نتیجه غربالگری اکتشافی و خوش‌بینانه است؛ جریان بیشینه امکان تقسیم بار و تغذیه حلقوی را می‌دهد.',
                     'تأیید شعاعی‌سازی، توالی مانور، پخش بار، ولتاژ، حفاظت و ظرفیت مسیر اصلی انجام نشده است.',
                     'رزرو هر فیدر و ظرفیت کلید رابط ورودی کارشناسی است؛ تأمین متقابل هنگام خطا به‌صورت مستقل بررسی می‌شود.',
                     'مختصات خروجی مربوط به گره پایین‌دست است، نه الزاماً محل نصب و پوشش مخابرات نامشخص است.']}


def optimize(model, count, limit=10000):
    valid = validate_model(model); bmap = valid[2]
    candidates = sorted(k for k, b in bmap.items() if b['candidate'] and not b['existing_switch'])
    if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > len(candidates): raise ValueError('تعداد کلید نامعتبر است')
    n = comb(len(candidates), count)
    if n > limit: raise ValueError(f'فضای جستجو {n} حالت است و از سقف {limit} بیشتر است')
    best = None
    for choice in combinations(candidates, count):
        result = evaluate(model, choice, _validated=valid)
        if best is None or (result['ens_kwh_per_year'], tuple(choice)) < (best['ens_kwh_per_year'], tuple(best['selected'])): best = result
    best['examined'] = n
    return best
