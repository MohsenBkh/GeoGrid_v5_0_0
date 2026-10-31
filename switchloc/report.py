"""Editable preliminary Word report; no claim of validated design."""
from docx import Document
from .methodology import CRITERIA
from .outages import summarize


def create_report(path, name, state, sources=()):
    doc = Document()
    doc.add_heading('گزارش اولیه SwitchLoc', 0)
    doc.add_paragraph(f'نام پروژه: {name or "نامشخص"}')
    doc.add_paragraph('این گزارش اکتشافی است و بدون بررسی کارشناس و تکمیل کنترل‌های مهندسی برای تصمیم اجرایی معتبر نیست.')
    doc.add_heading('منابع و قابلیت ردیابی', 1)
    if not sources: doc.add_paragraph('اطلاعات منبع هنوز در پروژه ذخیره نشده است.')
    for source in sources: doc.add_paragraph(f"{source['path']} — SHA-256: {source['sha256']}")
    ranking = state.get('results')
    doc.add_heading('اولویت‌بندی فیدرها', 1)
    if ranking:
        table = doc.add_table(rows=1, cols=3); table.style = 'Table Grid'
        for c, value in zip(table.rows[0].cells, ('رتبه', 'فیدر', 'امتیاز')): c.text = value
        for i, row in enumerate(ranking, 1):
            cells = table.add_row().cells
            for cell, value in zip(cells, (i, row['feeder'], f"{row['score']:.6f}")): cell.text = str(value)
            for key, label, *_ in CRITERIA:
                detail = row['criteria'][key]
                doc.add_paragraph(f"{row['feeder']} — {label}: خام {detail['raw']}, نرمال {detail['normalized']:.4f}, وزن {detail['weight']}, سهم {detail['contribution']:.4f}")
            for warning in row['warnings']: doc.add_paragraph('هشدار: ' + warning)
        doc.add_paragraph('EP و TL ورودی خارجی‌اند و تأیید مستقل لازم دارند.')
    else: doc.add_paragraph('محاسبه نشده است.')
    doc.add_heading('خاموشی‌ها', 1)
    if state.get('events') is not None:
        result = summarize(state['events'])
        doc.add_paragraph(f"رخداد: {result['events']}؛ حذف‌شده: {result['excluded']}؛ مجموع مدت معتبر: {result['duration_hours']:.2f} ساعت")
        for name_, n in result['categories'].items(): doc.add_paragraph(f'{name_}: {n}')
        doc.add_paragraph(result['warning'])
    else: doc.add_paragraph('داده‌ای وارد نشده است.')
    doc.add_heading('نقاط جایابی و زون‌ها', 1)
    placement = state.get('placement')
    if placement is None: doc.add_paragraph('محاسبه نشده است.')
    else:
        for warning in placement['warnings']: doc.add_paragraph('هشدار: ' + warning)
        for item in placement['proposals']:
            doc.add_paragraph(f"شاخه {item['branch']}، گره پایین‌دست {item['to_node']}، مختصات گره ({item['x']}, {item['y']})، مخابرات {item['telecom']}")
        for z in placement['zones']:
            doc.add_paragraph(f"زون {z['root']}: بار {z['load_kw']:.2f} kW، U {z['u_hours_per_year']:.2f} ساعت/سال، U×P {z['up_kwh_per_year']:.2f} kWh/سال")
    doc.add_heading('بررسی انتقال بار N-1', 1)
    n1 = state.get('n1')
    if n1 is None: doc.add_paragraph('محاسبه نشده است.')
    else:
        for warning in n1['warnings']: doc.add_paragraph('هشدار: ' + warning)
        for row in n1['scenarios']:
            doc.add_paragraph(f"خطا در {row['failed_zone']}: بازگشت از پشتیبان {row['backup_restored_kw']:.2f} kW؛ قطع باقی‌مانده {row['interrupted_kw']:.2f} kW")
    doc.add_heading('EP و TL بر اساس سناریوهای واردشده', 1)
    metrics = state.get('metrics')
    if metrics is None: doc.add_paragraph('محاسبه نشده است.')
    else:
        doc.add_paragraph(f"EP: {metrics['ep_percent']:.2f}%، TL: {metrics['tl_percent']:.2f}%")
        doc.add_paragraph(metrics['warning'])
    doc.add_heading('مقایسه طرح‌های شعاعی', 1)
    comparison = state.get('comparison')
    if comparison is None: doc.add_paragraph('محاسبه نشده است.')
    else:
        for warning in comparison['warnings']: doc.add_paragraph('هشدار: ' + warning)
        for plan in comparison['plans']:
            doc.add_paragraph(f"کلید جدید: {plan['new_switches']}؛ ENS پایه {plan['e1_kwh_per_year']:.2f}؛ ENS طرح {plan['e2_kwh_per_year']:.2f} kWh/سال")
    doc.add_heading('جایابی چندفیدری اکتشافی', 1)
    multi = state.get('multi_result')
    if multi is None: doc.add_paragraph('محاسبه نشده است.')
    else:
        for warning in multi['warnings']: doc.add_paragraph('هشدار: ' + warning)
        doc.add_paragraph(f"ENS اکتشافی کل: {multi['ens_kwh_per_year']:.2f} kWh/سال")
        for point in multi['proposals']:
            doc.add_paragraph(f"فیدر {point['feeder']}، شاخه {point['branch']}، گره {point['to_node']}، مختصات ({point['x']}, {point['y']})")
    doc.add_heading('بخش‌های تکمیل‌نشده', 1)
    doc.add_paragraph('کنترل پخش بار، ولتاژ و حفاظت، طرح‌های کامل چندفیدری، محاسبات کامل خودکار EP/TL، مقایسه اقتصادی و تأیید انطباق با دستورالعمل در این گزارش انجام نشده است.')
    doc.save(path)
