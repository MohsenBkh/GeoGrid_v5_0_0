"""Explicit Excel network schema; no topology inferred from geography."""
from openpyxl import Workbook, load_workbook
from .placement import analyze

NODE_HEADERS = ['id', 'load_kw', 'x', 'y']
BRANCH_HEADERS = ['id', 'from_node', 'to_node', 'status', 'existing_switch', 'candidate', 'lambda_per_year', 'repair_hours']

def create_network_template(path):
    wb = Workbook(); ns = wb.active; ns.title = 'nodes'; ns.append(NODE_HEADERS)
    for row in [('source', 0, 0, 0), ('n1', 100, 1, 0), ('n2', 100, 2, 0), ('n3', 100, 3, 0)]: ns.append(row)
    bs = wb.create_sheet('branches'); bs.append(BRANCH_HEADERS)
    for row in [('b1', 'source', 'n1', 'closed', False, True, 1, 1), ('b2', 'n1', 'n2', 'closed', False, True, 1, 1), ('b3', 'n2', 'n3', 'closed', False, True, 1, 1)]: bs.append(row)
    ws = wb.create_sheet('settings'); ws.append(['root', 'new_switches']); ws.append(['source', 1])
    note = wb.create_sheet('راهنما'); note.append(['داده‌ها صرفاً نمونه هستند و باید با داده واقعی و تأییدشده جایگزین شوند.'])
    note.append(['lambda_per_year بر حسب خرابی در سال و repair_hours بر حسب ساعت است. بار متوسط بر حسب kW.'])
    note.append(['محدود به شبکه شعاعی بسته و بدون پشتیبان. مختصات انتهای پایین‌دست محل دقیق نصب نیست.'])
    wb.save(path)

def read_network(path):
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        def rows(sheet, headers):
            if sheet not in wb: raise ValueError(f'برگه {sheet} یافت نشد')
            iterator = iter(wb[sheet].values); cols = next(iterator, ())
            if len(set(x for x in cols if x is not None)) != len([x for x in cols if x is not None]): raise ValueError(f'ستون تکراری در {sheet}')
            if set(headers) - set(cols): raise ValueError(f'ستون‌های لازم {sheet}: {headers}')
            return [dict(zip(cols, r)) for r in iterator if any(v is not None for v in r)]
        nodes = rows('nodes', NODE_HEADERS); branches = rows('branches', BRANCH_HEADERS); settings = rows('settings', ['root', 'new_switches'])
        if len(settings) != 1: raise ValueError('برگه settings باید دقیقاً یک ردیف داشته باشد')
        s = settings[0]; count = s['new_switches']
        if not isinstance(count, int) or isinstance(count, bool): raise ValueError('تعداد کلید باید عدد صحیح باشد')
        return nodes, branches, str(s['root'] or '').strip(), count
    finally: wb.close()

def load_network(path):
    nodes, branches, root, count = read_network(path)
    return analyze(nodes, branches, root, count)


def export_placement(path, result):
    wb = Workbook(); ws = wb.active; ws.title = 'proposals'
    columns = ['branch', 'from_node', 'to_node', 'x', 'y', 'telecom', 'reason']
    ws.append(columns)
    for p in result['proposals']: ws.append([p[c] for c in columns])
    ws = wb.create_sheet('zones'); ws.append(['root', 'nodes', 'load_kw', 'u_hours_per_year', 'up_kwh_per_year', 'downstream_load_kw', 'ens_kwh_per_year'])
    for z in result['zones']: ws.append([z['root'], ', '.join(z['nodes']), z['load_kw'], z['u_hours_per_year'], z['up_kwh_per_year'], z['downstream_load_kw'], z['ens_kwh_per_year']])
    ws = wb.create_sheet('warnings'); ws.append(['هشدارها و فرضیات']);
    for w in result['warnings']: ws.append([w])
    ws.append([f"حالات بررسی‌شده: {result['examined']}"])
    wb.save(path)
