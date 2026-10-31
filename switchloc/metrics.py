"""TAV122-02/00 guide §7-7-4 tables 14–15, from reviewed N-1 cases."""
from math import isfinite


def calculate_ep_tl(total_load_kw, cases):
    """Use independently verified case data; no topology assumptions made here.

    EP and TL are respectively maximum interrupted and transferable load
    divided by total feeder load, as stated in table 14. This function does
    not perform the N-1 study itself.
    """
    try: total = float(total_load_kw)
    except (ValueError, TypeError) as exc: raise ValueError('کل بار فیدر نامعتبر است') from exc
    if not isfinite(total) or total <= 0: raise ValueError('کل بار فیدر باید مثبت و متناهی باشد')
    if not cases: raise ValueError('حداقل یک سناریو لازم است')
    rows = []; seen = set()
    for case in cases:
        name = str(case.get('zone') or '').strip()
        if not name or name in seen: raise ValueError('شناسه زون خالی یا تکراری است')
        seen.add(name)
        try: interrupted, transferred = float(case['interrupted_kw']), float(case['transferable_kw'])
        except (KeyError, ValueError, TypeError) as exc: raise ValueError(f'مقادیر زون {name} نامعتبر است') from exc
        if not isfinite(interrupted) or not isfinite(transferred) or min(interrupted, transferred) < 0 or interrupted + transferred > total + 1e-9 * total:
            raise ValueError(f'مقادیر زون {name} خارج از حدود بار کل فیدر است')
        rows.append({'zone': name, 'interrupted_kw': interrupted, 'transferable_kw': transferred,
                     'interrupted_percent': interrupted / total * 100, 'transferable_percent': transferred / total * 100})
    return {'total_load_kw': total, 'cases': rows,
            'ep_percent': max(r['interrupted_percent'] for r in rows),
            'tl_percent': max(r['transferable_percent'] for r in rows),
            'warning': 'مقادیر سناریو باید مستقلاً از مطالعه N-1 و محدودیت‌های مانور و ظرفیت تأیید شوند؛ این بخش مطالعه شبکه را انجام نمی‌دهد.'}
