"""Excel model for the explicitly limited zone restoration flow study."""
from openpyxl import Workbook, load_workbook
from .n1 import calculate

ZONE_COLS = ['zone', 'feeder', 'load_kw']
LINK_COLS = ['from_zone', 'to_zone', 'switchable', 'capacity_kw']
TIE_COLS = ['id', 'zone', 'backup_feeder', 'reserve_kw', 'capacity_kw', 'normal_status', 'automated']


def create_n1_template(path):
    wb = Workbook(); ws = wb.active; ws.title = 'zones'; ws.append(ZONE_COLS)
    for row in [('Z0', 'F1', 100), ('Z1', 'F1', 100), ('Z2', 'F1', 100)]: ws.append(row)
    ws = wb.create_sheet('links'); ws.append(LINK_COLS)
    for row in [('Z0', 'Z1', True, 200), ('Z1', 'Z2', True, 200)]: ws.append(row)
    ws = wb.create_sheet('ties'); ws.append(TIE_COLS); ws.append(['T1', 'Z2', 'F2', 80, 80, 'open', True])
    ws = wb.create_sheet('settings'); ws.append(['feeder', 'source_zone']); ws.append(['F1', 'Z0'])
    ws = wb.create_sheet('راهنما'); ws.append(['نمونه فرضی است. مقادیر باید توسط کارشناس جایگزین و تأیید شود.'])
    ws.append(['این مدل کران بالای انتقال است و محدودیت‌های بهره‌برداری و الکتریکی را تأیید نمی‌کند.'])
    wb.save(path)


def load_n1(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        def read(name, cols):
            if name not in wb: raise ValueError(f'برگه {name} یافت نشد')
            rows = iter(wb[name].values); header = next(rows, ())
            nonempty = [x for x in header if x is not None]
            if len(set(nonempty)) != len(nonempty) or set(cols) - set(header): raise ValueError(f'ستون‌های برگه {name} نامعتبر است')
            return [dict(zip(header, row)) for row in rows if any(v is not None for v in row)]
        zones = read('zones', ZONE_COLS); links = read('links', LINK_COLS); ties = read('ties', TIE_COLS)
        settings = read('settings', ['feeder', 'source_zone'])
        if len(settings) != 1: raise ValueError('تنظیمات باید یک ردیف باشد')
        return calculate(zones, links, ties, str(settings[0]['feeder'] or '').strip(), str(settings[0]['source_zone'] or '').strip())
    finally: wb.close()


def export_n1(path, result):
    wb = Workbook(); ws = wb.active; ws.title = 'scenarios'
    columns = ['failed_zone', 'total_kw', 'source_restored_kw', 'backup_restored_kw', 'interrupted_kw']
    ws.append(['feeder'] + columns)
    for row in result['scenarios']: ws.append([result['feeder']] + [row[c] for c in columns])
    ws = wb.create_sheet('restored_by_zone'); ws.append(['failed_zone', 'zone', 'restored_kw'])
    for row in result['scenarios']:
        for zone, amount in row['restored_by_zone'].items(): ws.append([row['failed_zone'], zone, amount])
    ws = wb.create_sheet('backup'); ws.append(['failed_zone', 'backup_feeder', 'restored_kw'])
    for row in result['scenarios']:
        for feeder, amount in row['backup_by_feeder'].items(): ws.append([row['failed_zone'], feeder, amount])
    ws = wb.create_sheet('warnings')
    for warning in result['warnings']: ws.append([warning])
    wb.save(path)
