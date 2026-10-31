"""Manual audit workflow for outages; never classify an event by guessing."""
from collections import Counter
from math import isfinite
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

CATEGORIES = ('نیازمند بررسی دستی', 'قابل کاهش با اتوماسیون', 'نیازمند تعمیر', 'مشکل حفاظتی', 'برنامه‌ریزی‌شده', 'سایر', 'حذف‌شده')
HEADERS = ['source', 'sheet', 'row', 'event_id', 'feeder', 'date_jalali', 'cause', 'duration_hours', 'classification', 'exclusion_reason']


def export_review(path, events):
    wb = Workbook(); ws = wb.active; ws.title = 'outages'; ws.append(HEADERS)
    for event in events:
        ws.append([event.get(key) for key in HEADERS])
    ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
    # Long Persian lists exceed Excel's inline validation limit. Use a hidden sheet.
    choices = wb.create_sheet('categories')
    for category in CATEGORIES: choices.append([category])
    choices.sheet_state = 'hidden'
    validation = DataValidation(type='list', formula1="'categories'!$A$1:$A$7")
    ws.add_data_validation(validation); validation.add(f'I2:I{max(2, len(events)+1)}')
    wb.save(path)


def read_review(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if 'outages' not in wb: raise ValueError('برگه outages وجود ندارد')
        rows = iter(wb['outages'].values); headers = next(rows, ())
        if any(h not in headers for h in HEADERS): raise ValueError('ستون‌های فایل بازبینی ناقص هستند')
        result = []
        for number, values in enumerate(rows, 2):
            if not any(x is not None for x in values): continue
            row = dict(zip(headers, values)); category = row['classification']
            if category not in CATEGORIES: raise ValueError(f'ردیف {number}: طبقه‌بندی نامعتبر')
            if category == 'حذف‌شده' and not str(row['exclusion_reason'] or '').strip():
                raise ValueError(f'ردیف {number}: علت حذف لازم است')
            duration = row['duration_hours']
            if duration is not None:
                if isinstance(duration, bool): raise ValueError(f'ردیف {number}: مدت نامعتبر')
                try: duration = float(duration)
                except (ValueError, TypeError) as exc: raise ValueError(f'ردیف {number}: مدت نامعتبر') from exc
                if not isfinite(duration) or duration < 0: raise ValueError(f'ردیف {number}: مدت نامعتبر')
                row['duration_hours'] = duration
            result.append(row)
        return result
    finally: wb.close()


def summarize(events):
    """Describe observed durations; no annual rate or ENS inferred."""
    active = [r for r in events if r['classification'] != 'حذف‌شده']
    durations = [r['duration_hours'] for r in active if r['duration_hours'] is not None]
    return {'events': len(events), 'included': len(active), 'excluded': len(events)-len(active),
            'duration_hours': sum(durations), 'mean_hours': sum(durations)/len(durations) if durations else None,
            'missing_duration': len(active)-len(durations),
            'categories': dict(Counter(r['classification'] for r in events)),
            'warning': 'صرفاً خلاصه داده‌های ثبت‌شده؛ نرخ سالانه و انرژی توزیع‌نشده از این داده‌ها استنتاج نشده است.'}
