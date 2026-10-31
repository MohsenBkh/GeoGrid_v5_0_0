"""Excel interchange for explicit multi-feeder model and screening results."""
from openpyxl import Workbook, load_workbook
from .multifeeder import validate_model

SCHEMA = {'feeders': ['id', 'root', 'reserve_kw'],
          'nodes': ['id', 'feeder', 'load_kw', 'x', 'y'],
          'branches': ['id', 'feeder', 'from_node', 'to_node', 'status', 'existing_switch', 'candidate', 'lambda_per_year', 'repair_hours', 'capacity_kw'],
          'ties': ['id', 'node_a', 'node_b', 'normal_status', 'automated', 'capacity_kw'],
          'settings': ['new_switches', 'crs']}


def create_template(path):
    wb = Workbook(); wb.remove(wb.active)
    for name, cols in SCHEMA.items(): wb.create_sheet(name).append(cols)
    for row in [('F1', 'a0', 70), ('F2', 'b0', 80)]: wb['feeders'].append(row)
    for row in [('a0', 'F1', 0, 0, 0), ('a1', 'F1', 100, 100, 0), ('a2', 'F1', 80, 200, 0),
                ('b0', 'F2', 0, 0, 100), ('b1', 'F2', 90, 100, 100), ('b2', 'F2', 80, 200, 100)]: wb['nodes'].append(row)
    for row in [('a01', 'F1', 'a0', 'a1', 'closed', False, True, .5, 2, 200),
                ('a12', 'F1', 'a1', 'a2', 'closed', False, True, .5, 2, 200),
                ('b01', 'F2', 'b0', 'b1', 'closed', False, True, .5, 2, 200),
                ('b12', 'F2', 'b1', 'b2', 'closed', False, True, .5, 2, 200)]: wb['branches'].append(row)
    wb['ties'].append(['T1', 'a2', 'b2', 'open', True, 70]); wb['settings'].append([2, 'LOCAL'])
    ws = wb.create_sheet('راهنما')
    ws.append(['داده‌ها نمونه فرضی هستند. شناسه گره و شاخه در کل شبکه یکتا باشد؛ مقادیر واقعی تأییدشده را جایگزین کنید.'])
    ws.append(['بار و ظرفیت kW، نرخ خرابی در سال و زمان تعمیر ساعت است. اتصال بین فیدرها کلید معمولاً باز است.'])
    ws.append(['مختصات همه گره‌ها باید در یک سیستم مشترک باشد. تبدیل مختصات انجام نمی‌شود.'])
    ws.append(['نتیجه اکتشافی است؛ پخش بار، حفاظت، شعاعی‌سازی و پوشش مخابرات را کارشناس بررسی کند.'])
    wb.save(path)


def load_model(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        tables = {}
        for name, cols in SCHEMA.items():
            if name not in wb: raise ValueError(f'برگه {name} یافت نشد')
            it = iter(wb[name].values); header = next(it, ()); present = [h for h in header if h is not None]
            if len(set(present)) != len(present) or set(cols) - set(header): raise ValueError(f'ستون‌های برگه {name} نامعتبر است')
            tables[name] = [dict(zip(header, row)) for row in it if any(x is not None for x in row)]
        if len(tables['settings']) != 1: raise ValueError('تنظیمات باید یک ردیف داشته باشد')
        settings = tables.pop('settings')[0]
        count = settings['new_switches']
        if not isinstance(count, int) or isinstance(count, bool) or count < 0: raise ValueError('تعداد کلید باید صحیح و نامنفی باشد')
        tables['crs'] = str(settings['crs'] or '').strip()
        if not tables['crs']: raise ValueError('سیستم مختصات را مشخص کنید')
        feeders, nodes, branches, ties = validate_model(tables)
        tables['feeders'] = list(feeders.values()); tables['nodes'] = list(nodes.values())
        tables['branches'] = list(branches.values()); tables['ties'] = ties
        return tables, count
    finally: wb.close()


def export_result(path, result, crs):
    wb = Workbook(); ws = wb.active; ws.title = 'summary'
    ws.append(['ens_kwh_per_year', 'crs', 'examined']); ws.append([result['ens_kwh_per_year'], crs, result.get('examined', 1)])
    ws = wb.create_sheet('proposals'); cols = ['feeder', 'branch', 'from_node', 'to_node', 'x', 'y', 'telecom', 'reason']; ws.append(cols)
    for p in result['proposals']: ws.append([p[c] for c in cols])
    ws = wb.create_sheet('zones'); ws.append(['feeder', 'zone', 'nodes', 'load_kw', 'u_hours_per_year'])
    for f in result['feeders']:
        for z in f['zones']: ws.append([f['feeder'], z['root'], ', '.join(z['nodes']), z['load_kw'], z['u_hours_per_year']])
    ws = wb.create_sheet('n1'); cols = ['failed_zone', 'total_kw', 'source_restored_kw', 'backup_restored_kw', 'interrupted_kw', 'u_hours_per_year', 'ens_kwh_per_year']; ws.append(['feeder'] + cols)
    for f in result['feeders']:
        for scenario in f['scenarios']: ws.append([f['feeder']] + [scenario[c] for c in cols])
    ws = wb.create_sheet('backup'); ws.append(['feeder', 'failed_zone', 'backup_feeder', 'restored_kw'])
    for f in result['feeders']:
        for scenario in f['scenarios']:
            for feeder, kw in scenario['backup_by_feeder'].items(): ws.append([f['feeder'], scenario['failed_zone'], feeder, kw])
    ws = wb.create_sheet('warnings')
    for warning in result['warnings']: ws.append([warning])
    wb.save(path)
