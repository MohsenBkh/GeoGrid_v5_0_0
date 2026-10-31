"""Compare discrete no-backup switch plans on one radial feeder."""
from openpyxl import Workbook
from .placement import analyze


def compare(nodes, branches, root, counts):
    """Calculate zero-new-switch baseline and distinct switch-count plans.

    E1/E2 are expected annual unserved energy under the simplified radial
    model. This does not evaluate backups, feasible switching or economics.
    """
    if not counts or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in counts):
        raise ValueError('تعداد کلیدها باید اعداد صحیح نامنفی باشد')
    if len(set(counts)) != len(counts): raise ValueError('طرح تکراری است')
    baseline = analyze(nodes, branches, root, 0)
    plans = []
    for n in counts:
        result = baseline if n == 0 else analyze(nodes, branches, root, n)
        plans.append({'new_switches': n, 'e1_kwh_per_year': baseline['score'],
                      'e2_kwh_per_year': result['score'],
                      'improvement_kwh_per_year': baseline['score'] - result['score'],
                      'placement': result})
    return {'plans': plans, 'warnings': [
        'مقایسه فقط برای فیدر شعاعی بدون پشتیبان، با فرض زمان مانور صفر و ظرفیت نامحدود انجام شده است.',
        'مقادیر E1 و E2 صرفاً ENS تخمینی مدل بوده و با درستی نرخ خرابی و بار و فرضیات آن معتبرند.',
        'پوشش مخابرات، حفاظت، ولتاژ، هزینه و انتخاب طرح نهایی بررسی نشده‌اند.']}


def export_comparison(path, result):
    wb = Workbook(); ws = wb.active; ws.title = 'plans'
    columns = ['new_switches', 'e1_kwh_per_year', 'e2_kwh_per_year', 'improvement_kwh_per_year']
    ws.append(columns)
    for plan in result['plans']: ws.append([plan[x] for x in columns])
    ws = wb.create_sheet('proposals'); ws.append(['new_switches', 'branch', 'from_node', 'to_node', 'x', 'y', 'telecom', 'reason'])
    for plan in result['plans']:
        for p in plan['placement']['proposals']:
            ws.append([plan['new_switches']] + [p[x] for x in ('branch', 'from_node', 'to_node', 'x', 'y', 'telecom', 'reason')])
    ws = wb.create_sheet('zones'); ws.append(['new_switches', 'zone', 'nodes', 'load_kw', 'u_hours_per_year', 'downstream_load_kw', 'ens_kwh_per_year'])
    for plan in result['plans']:
        for z in plan['placement']['zones']:
            ws.append([plan['new_switches'], z['root'], ', '.join(z['nodes']), z['load_kw'], z['u_hours_per_year'], z['downstream_load_kw'], z['ens_kwh_per_year']])
    ws = wb.create_sheet('warnings')
    for warning in result['warnings'] + result['plans'][0]['placement']['warnings']: ws.append([warning])
    wb.save(path)
