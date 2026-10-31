"""TAV122-02/00, guide section 7-7-5, equation 1 and table 16.

Inputs are measured/independently verified values, not inferred EP or TL.
"""
from math import isfinite

CRITERIA = (
    ('connections', 'معکوس تعداد ارتباطات', 1, True),
    ('ep', 'EP', 2, False),
    ('tl', 'معکوس TL', 2, True),
    ('load_priority', 'مجموع اولویت بار', 3, False),
    ('failure_rate', 'نرخ خرابی', 1, False),
    ('outage_duration', 'متوسط مدت خاموشی', 1, False),
)
LOAD_WEIGHTS = {'شهری': 2, 'روستایی': 1, 'کشاورزی': 1.5, 'صنعتی': 1.5, 'خاص': 4}


def rank_feeders(feeders, weights=None):
    """Return scores with raw, transformed, normalized and weighted values.

    Zero-sum criteria are reported as zero contributions, not fabricated data.
    """
    feeders = list(feeders)
    if not feeders:
        raise ValueError('حداقل یک فیدر لازم است')
    names = [str(f.get('feeder', '')).strip() for f in feeders]
    if any(not n for n in names) or len(set(names)) != len(names):
        raise ValueError('شناسه فیدر خالی یا تکراری است')
    weights = weights or {}
    unknown = set(weights) - {c[0] for c in CRITERIA}
    if unknown:
        raise ValueError('معیار ناشناخته: ' + ', '.join(sorted(unknown)))
    result = [{'feeder': n, 'score': 0.0, 'criteria': {}, 'warnings': []} for n in names]
    for key, label, default, inverse in CRITERIA:
        try:
            weight = float(weights.get(key, default))
            values = [float(f[key]) for f in feeders]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'مقدار عددی معتبر برای {label} لازم است') from exc
        if not isfinite(weight) or weight < 0 or any(not isfinite(v) or v < 0 for v in values):
            raise ValueError(f'مقادیر و وزن {label} باید متناهی و نامنفی باشند')
        transformed = [(10.0 if v == 0 else 1 / v) if inverse else v for v in values]
        total = sum(transformed)
        if not isfinite(total):
            raise ValueError(f'سرریز در معیار {label}')
        for row, raw, x in zip(result, values, transformed):
            normalized = x / total if total else 0.0
            contribution = normalized * weight
            row['criteria'][key] = {'raw': raw, 'transformed': x, 'normalized': normalized,
                                    'weight': weight, 'contribution': contribution}
            row['score'] += contribution
            if not total:
                row['warnings'].append(f'مجموع معیار {label} صفر است؛ سهم آن صفر در نظر گرفته شد')
    return sorted(result, key=lambda row: (-row['score'], row['feeder']))
