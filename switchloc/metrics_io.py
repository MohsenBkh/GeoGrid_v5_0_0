from openpyxl import Workbook, load_workbook
from .metrics import calculate_ep_tl


def create_metrics_template(path):
    wb = Workbook(); ws = wb.active; ws.title = 'settings'; ws.append(['total_load_kw']); ws.append([2500])
    ws = wb.create_sheet('cases'); ws.append(['zone', 'interrupted_kw', 'transferable_kw'])
    for row in [('Zone0', 1800, 700), ('Zone1', 600, 400), ('Zone2', 300, 400), ('Zone3', 200, 200), ('Zone4', 200, 0)]: ws.append(row)
    ws = wb.create_sheet('راهنما'); ws.append(['مثال جدول ۱۵: اعداد را با نتایج تأییدشده مطالعه N-1 جایگزین کنید.'])
    wb.save(path)


def load_metrics(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if 'settings' not in wb or 'cases' not in wb: raise ValueError('برگه‌های settings و cases لازم است')
        def rows(sheet, expected):
            it = iter(wb[sheet].values); headers = next(it, ()); fields = [x for x in headers if x is not None]
            if len(fields) != len(set(fields)) or set(expected) - set(headers): raise ValueError(f'ستون‌های برگه {sheet} نامعتبر است')
            return [dict(zip(headers, row)) for row in it if any(x is not None for x in row)]
        settings = rows('settings', ['total_load_kw'])
        if len(settings) != 1: raise ValueError('تنظیمات باید یک ردیف داشته باشد')
        return calculate_ep_tl(settings[0]['total_load_kw'], rows('cases', ['zone', 'interrupted_kw', 'transferable_kw']))
    finally: wb.close()


def export_metrics(path, result):
    wb = Workbook(); ws = wb.active; ws.title = 'metrics'
    ws.append(['total_load_kw', 'ep_percent', 'tl_percent']); ws.append([result[k] for k in ('total_load_kw', 'ep_percent', 'tl_percent')])
    ws = wb.create_sheet('cases'); cols = ['zone', 'interrupted_kw', 'transferable_kw', 'interrupted_percent', 'transferable_percent']; ws.append(cols)
    for row in result['cases']: ws.append([row[k] for k in cols])
    ws = wb.create_sheet('warnings'); ws.append([result['warning']]); wb.save(path)
