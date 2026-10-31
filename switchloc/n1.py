"""N-1 zone restoration upper bound; not a power-flow or switching study.

All supplies, zonal connections and reserves must be explicitly supplied.
No EP/TL aggregation is inferred from this simplified flow model.
"""
from math import isfinite
import networkx as nx


def _num(value, field):
    try: n = float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f'{field}: عدد لازم است') from exc
    if not isfinite(n) or n < 0: raise ValueError(f'{field}: باید متناهی و نامنفی باشد')
    return n


def calculate(zones, links, ties, feeder, source_zone):
    """Simulate each faulted zone with graph max flow and finite tie reserves.

    Healthy zones connected to source are restored by source. The other
    zones can be restored from explicit backup feeder ties and shared feeder
    reserves. Fractional loads, multiple parallel supplies and link flows
    are permitted. This is an upper bound: radial switching, sequence,
    voltage, protection and actual automation are not verified.
    """
    zmap = {}
    for item in zones:
        zid = str(item.get('zone') or '').strip()
        if not zid or zid in zmap: raise ValueError('شناسه زون خالی یا تکراری است')
        if str(item.get('feeder') or '').strip() != feeder: raise ValueError('همه زون‌ها باید متعلق به فیدر انتخابی باشند')
        zmap[zid] = _num(item.get('load_kw'), f'بار {zid}')
    if not zmap or source_zone not in zmap: raise ValueError('زون مبدأ نامعتبر است')
    edges = []; seen = set()
    for item in links:
        a = str(item.get('from_zone') or '').strip(); b = str(item.get('to_zone') or '').strip()
        if a not in zmap or b not in zmap or a == b: raise ValueError('اتصال زون نامعتبر است')
        key = tuple(sorted((a, b)))
        if key in seen: raise ValueError('اتصال زون تکراری است')
        seen.add(key)
        if type(item.get('switchable')) is not bool: raise ValueError('وضعیت قابلیت مانور اتصال باید بولی باشد')
        if not item['switchable']: raise ValueError('همه مرزهای زون باید قابل جداسازی تأییدشده باشند')
        edges.append((a, b, _num(item.get('capacity_kw'), 'ظرفیت اتصال')))
    base = nx.Graph(); base.add_nodes_from(zmap); base.add_edges_from((a, b) for a, b, _ in edges)
    if not nx.is_tree(base): raise ValueError('گراف زون‌های فیدر باید شعاعی و متصل باشد')
    reserves = {}; valid_ties = []; ids = set()
    for item in ties:
        tid = str(item.get('id') or '').strip(); backup = str(item.get('backup_feeder') or '').strip()
        zone = str(item.get('zone') or '').strip()
        if not tid or tid in ids or not backup or backup == feeder or zone not in zmap: raise ValueError('مشخصات کلید رابط نامعتبر است')
        ids.add(tid)
        if item.get('normal_status') != 'open' or type(item.get('automated')) is not bool:
            raise ValueError(f'{tid}: وضعیت باید open و اتوماسیون بولی باشد')
        reserve = _num(item.get('reserve_kw'), f'رزرو {backup}')
        capacity = _num(item.get('capacity_kw'), f'ظرفیت {tid}')
        if backup in reserves and reserves[backup] != reserve: raise ValueError(f'رزرو فیدر {backup} ناسازگار است')
        reserves[backup] = reserve
        if item['automated']: valid_ties.append((tid, backup, zone, capacity))
    total = sum(zmap.values())
    if not isfinite(total): raise ValueError('سرریز مجموع بار')
    results = []
    for failed in sorted(zmap):
        healthy = base.copy(); healthy.remove_node(failed)
        from_source = nx.node_connected_component(healthy, source_zone) if failed != source_zone else set()
        source_load = sum(zmap[z] for z in from_source)
        target = set(healthy.nodes) - set(from_source)
        g = nx.DiGraph(); source = ('source',); sink = ('sink',)
        g.add_nodes_from([source, sink])
        for z in target: g.add_edge(('zone', z), sink, capacity=zmap[z])
        for a,b,cap in edges:
            if a in target and b in target:
                g.add_edge(('zone', a), ('zone', b), capacity=cap)
                g.add_edge(('zone', b), ('zone', a), capacity=cap)
        for backup,reserve in reserves.items(): g.add_edge(source, ('backup', backup), capacity=reserve)
        for tid,backup,zone,cap in valid_ties:
            if zone in target:
                g.add_edge(('backup', backup), ('tie', tid), capacity=cap)
                g.add_edge(('tie', tid), ('zone', zone), capacity=cap)
        flow_value, flows = nx.maximum_flow(g, source, sink)
        restored = {z: flows.get(('zone', z), {}).get(sink, 0.0) for z in sorted(target)}
        backups = {b: flows.get(source, {}).get(('backup', b), 0.0) for b in sorted(reserves)}
        interrupted = total - source_load - flow_value
        results.append({'failed_zone': failed, 'total_kw': total, 'source_restored_kw': source_load,
                        'backup_restored_kw': flow_value, 'interrupted_kw': max(0.0, interrupted),
                        'restored_by_zone': restored, 'backup_by_feeder': backups})
    return {'feeder': feeder, 'scenarios': results, 'warnings': [
        'کران بالای انتقال بار با جریان شبکه؛ تقسیم بار، چند منبع همزمان و حلقه احتمالی مجاز فرض شده است.',
        'افت ولتاژ، حفاظت، توالی مانور، پخش بار، ظرفیت مسیر اصلی و امکان شعاعی‌سازی بررسی نشده‌اند؛ برای بهره‌برداری معتبر نیست.',
        'فقط رابط اتوماسیون با وضعیت عادی باز و ظرفیت و رزرو صریح وارد محاسبه می‌شود؛ EP و TL به‌صورت خودکار تعیین نمی‌شوند.']}
