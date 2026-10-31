"""Explicit templates and read-only import; original inputs are never changed."""
from datetime import time, timedelta
from pathlib import Path
from openpyxl import Workbook, load_workbook
from .methodology import CRITERIA, rank_feeders

HEADERS = ['feeder'] + [c[0] for c in CRITERIA]


def create_template(path):
    wb = Workbook(); ws = wb.active; ws.title = 'feeders'
    ws.append(HEADERS)
    ws.append(['example-1', 1, 72, 28, 4, 2, 1.5])
    ws.append(['example-2', 0, 80, 20, 3, 1, 2])
    note = wb.create_sheet('راهنما')
    for row in [('نمونه است؛ پیش از مطالعه جایگزین شود',), ('EP و TL باید جداگانه طبق دستورالعمل محاسبه و بررسی شوند.',), ('مقادیر خام معیارها را وارد کنید؛ معکوس و نرمال‌سازی خودکار است.',)]: note.append(row)
    wb.save(path)


def load_feeders(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if 'feeders' not in wb: raise ValueError('برگه feeders یافت نشد')
        rows = iter(wb['feeders'].values)
        headers = next(rows, ())
        if len(set(x for x in headers if x is not None)) != len([x for x in headers if x is not None]):
            raise ValueError('ستون تکراری در فایل ورودی')
        missing = set(HEADERS) - set(headers)
        if missing: raise ValueError('ستون‌های لازم: ' + ', '.join(sorted(missing)))
        data = [dict(zip(headers, row)) for row in rows if any(v is not None for v in row)]
        rank_feeders(data)  # validate before returning
        return data
    finally: wb.close()


def export_ranking(path, results):
    wb = Workbook(); ws = wb.active; ws.title = 'ranking'
    ws.append(['rank', 'feeder', 'score'] + [f'{key}_{suffix}' for key, *_ in CRITERIA for suffix in ('raw', 'transformed', 'normalized', 'weight', 'contribution')] + ['warnings'])
    for index, row in enumerate(results, 1):
        ws.append([index, row['feeder'], row['score']] + [row['criteria'][key][suffix] for key, *_ in CRITERIA for suffix in ('raw', 'transformed', 'normalized', 'weight', 'contribution')] + ['; '.join(row['warnings'])])
    wb.save(path)


def import_outages(path):
    """Read the supplied 1405 workbook layout. Durations are Excel time fractions.

    Preserve Persian dates verbatim; no automatic classification or year coverage claims.
    """
    wb = load_workbook(path, read_only=True, data_only=True)
    output, warnings = [], []
    try:
        for sheet in wb:
            rows = iter(sheet.values); headers = next(rows, ())
            def normalize(s): return str(s or '').replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', '').strip()
            columns = {normalize(v): i for i, v in enumerate(headers) if v is not None}
            required = ['شماره حادثه', 'نام فیدر', 'مدت قطع', 'تاریخ حادثه', 'علت قطع']
            if any(x not in columns for x in required):
                warnings.append(f'{sheet.title}: ستون‌های لازم یافت نشد'); continue
            for number, row in enumerate(rows, 2):
                if not any(v is not None for v in row): continue
                def get(name):
                    i = columns.get(name); return row[i] if i is not None and i < len(row) else None
                duration = get('مدت قطع')
                if isinstance(duration, time): duration = (duration.hour * 3600 + duration.minute * 60 + duration.second) / 3600
                elif isinstance(duration, timedelta): duration = duration.total_seconds() / 3600
                elif isinstance(duration, (int, float)): duration = duration * 24
                else: duration = None
                if duration is None or duration < 0: warnings.append(f'{sheet.title} ردیف {number}: مدت نامعتبر')
                output.append({'source': str(Path(path).name), 'sheet': sheet.title, 'row': number,
                    'event_id': get('شماره حادثه'), 'feeder': get('نام فیدر'), 'date_jalali': get('تاریخ حادثه'),
                    'cause': get('علت قطع'), 'duration_hours': duration, 'classification': 'نیازمند بررسی دستی'})
    finally: wb.close()
    warnings.append('پوشش حداقل شش سال و قابلیت کاهش رخدادها باید جداگانه بررسی شود؛ طبقه‌بندی خودکار انجام نشده است.')
    return output, warnings
