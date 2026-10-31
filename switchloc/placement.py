"""Exploratory radial single-feeder sectionalising, based on guide appendix B.

Discrete branch-end candidates and branch-to-zone allocation are modelling
assumptions; the no-backup objective generalizes equation 8 to a radial tree.
"""
from collections import defaultdict
from itertools import combinations
from math import comb, isfinite


def _number(value, label):
    try: number = float(value)
    except (TypeError, ValueError) as exc: raise ValueError(f'{label}: مقدار عددی لازم است') from exc
    if not isfinite(number) or number < 0: raise ValueError(f'{label}: مقدار باید نامنفی و متناهی باشد')
    return number


def analyze(nodes, branches, root, count, limit=100000, forced=None):
    """Search candidate branch boundaries on a connected radial feeder.

    Each branch's lambda*r belongs to its downstream node's zone. Existing
    closed sectionalizers are fixed boundaries. No backup, switching time,
    voltage, protection, telecom feasibility, or electrical constraints modeled.
    """
    node_map = {}
    for n in nodes:
        name = str(n.get('id') or '').strip()
        if not name or name in node_map: raise ValueError('شناسه گره خالی یا تکراری است')
        node_map[name] = dict(n, id=name, load_kw=_number(n.get('load_kw'), f'بار گره {name}'))
    if root not in node_map: raise ValueError('گره مبدأ یافت نشد')
    if not isinstance(count, int) or isinstance(count, bool) or count < 0: raise ValueError('تعداد کلید نامعتبر است')
    adjacency = defaultdict(list); branch_map = {}
    for b in branches:
        name = str(b.get('id') or '').strip(); a = str(b.get('from_node') or '').strip(); z = str(b.get('to_node') or '').strip()
        if not name or name in branch_map: raise ValueError('شناسه شاخه خالی یا تکراری است')
        if a not in node_map or z not in node_map or a == z: raise ValueError(f'دو سر شاخه {name} نامعتبر است')
        status = str(b.get('status') or '').strip().lower()
        if status != 'closed': raise ValueError(f'وضعیت شاخه {name} باید closed باشد؛ شبکه باز و چندفیدری پشتیبانی نمی‌شود')
        existing = b.get('existing_switch'); candidate = b.get('candidate')
        if type(existing) is not bool or type(candidate) is not bool: raise ValueError(f'وضعیت کلید و کاندید شاخه {name} باید بولی باشد')
        if existing and candidate: raise ValueError(f'شاخه {name} دارای کلید موجود نمی‌تواند کاندید کلید جدید باشد')
        branch_map[name] = dict(b, id=name, from_node=a, to_node=z,
                                u=_number(b.get('lambda_per_year'), f'نرخ خرابی {name}') * _number(b.get('repair_hours'), f'زمان تعمیر {name}'))
        if not isfinite(branch_map[name]['u']): raise ValueError(f'سرریز نرخ و زمان خرابی شاخه {name}')
        adjacency[a].append((z, name)); adjacency[z].append((a, name))
    if len(branch_map) != len(node_map) - 1: raise ValueError('شبکه باید یک درخت شعاعی متصل باشد')
    parent = {root: None}; edge_for = {}; order = [root]
    for node in order:
        for child, edge in adjacency[node]:
            if child == parent[node]: continue
            if child in parent: raise ValueError('حلقه یا اتصال موازی در شبکه وجود دارد')
            parent[child] = node; edge_for[child] = edge; order.append(child)
    if len(order) != len(node_map): raise ValueError('شبکه دارای گره جداافتاده است')
    candidates = sorted(k for k, v in branch_map.items() if v['candidate'])
    if count > len(candidates): raise ValueError('تعداد کاندیدهای معتبر کافی نیست')
    if forced is not None:
        if len(set(forced)) != count or not set(forced).issubset(candidates): raise ValueError('انتخاب دستی شامل شاخه نامعتبر یا تکراری است')
        choices = [tuple(sorted(forced))]
    else:
        if comb(len(candidates), count) > limit: raise ValueError(f'فضای جستجو بیش از {limit} حالت است؛ کاندیدها را محدود کنید')
        choices = combinations(candidates, count)
    existing = {k for k, v in branch_map.items() if v['existing_switch']}
    def zones(cuts):
        zone_of = {root: root}; groups = {root: {'root': root, 'nodes': [], 'load_kw': 0.0, 'u_hours_per_year': 0.0}}
        for node in order:
            if node != root:
                edge = edge_for[node]
                zone_of[node] = node if edge in cuts else zone_of[parent[node]]
                groups.setdefault(zone_of[node], {'root': zone_of[node], 'nodes': [], 'load_kw': 0.0, 'u_hours_per_year': 0.0})
                groups[zone_of[node]]['u_hours_per_year'] += branch_map[edge]['u']
            group = groups[zone_of[node]]; group['nodes'].append(node); group['load_kw'] += node_map[node]['load_kw']
        # The tree of zones is rooted in the source zone. A fault in a zone
        # interrupts that zone and all descendants (no backup and zero switching time).
        for group in groups.values():
            group['up_kwh_per_year'] = group['load_kw'] * group['u_hours_per_year']
            group['downstream_load_kw'] = group['load_kw']
        for node in reversed(order):
            if node != root and zone_of[node] == node:
                groups[zone_of[parent[node]]]['downstream_load_kw'] += groups[node]['downstream_load_kw']
        for group in groups.values():
            group['ens_kwh_per_year'] = group['downstream_load_kw'] * group['u_hours_per_year']
        return list(groups.values())
    best = None
    for choice in choices:
        z = zones(existing | set(choice))
        score = sum(group['ens_kwh_per_year'] for group in z)
        if not isfinite(score): raise ValueError('سرریز در محاسبه ENS')
        if best is None or (score, choice) < (best[0], best[1]): best = (score, choice, z)
    warnings = ['نتیجه اکتشافی است؛ تابع ENS تعمیم درختی رابطه ۸ برای نقاط گسسته است و صحت آن برای شبکه واقعی باید توسط کارشناس تأیید شود.',
                'فقط یک فیدر شعاعی بدون پشتیبان؛ زمان مانور صفر، تلفات و قیود ولتاژ، حفاظت و مخابرات مدل نشده‌اند.',
                'U شاخه در زون گره پایین‌دست منظور شده است؛ صحت توزیع λ و r و بار باید بررسی شود.']
    proposals = []
    for edge in best[1]:
        b = branch_map[edge]; child = next(n for n, e in edge_for.items() if e == edge)
        proposals.append({'branch': edge, 'from_node': parent[child], 'to_node': child,
                          'x': node_map[child].get('x'), 'y': node_map[child].get('y'),
                          'telecom': 'نامشخص', 'reason': 'کمینه‌سازی ENS در نقاط گسسته مجاز'})
    return {'proposals': proposals, 'zones': best[2], 'score': best[0], 'warnings': warnings,
            'examined': 1 if forced is not None else comb(len(candidates), count)}
