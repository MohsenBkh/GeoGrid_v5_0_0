"""Guide section 7-8-1, equations 2–4; amounts must share currency units."""
from math import isfinite


def net_present_worth(cost_new, cost_replace, annual_maintenance, annual_ens_income,
                      annual_loss_income, interest, inflation, years):
    """Constant annual cash flow, nominal rates as fractions (0.2 = 20%).

    This is NPW, not the ambiguous CE/CN ranking index. All costs and income
    must be entered and checked independently by the engineer.
    """
    vals = (cost_new, cost_replace, annual_maintenance, annual_ens_income, annual_loss_income, interest, inflation)
    try: vals = tuple(float(v) for v in vals)
    except (ValueError, TypeError) as exc: raise ValueError('همه مقادیر اقتصادی باید عددی باشند') from exc
    if any(not isfinite(x) for x in vals): raise ValueError('مقادیر اقتصادی باید متناهی باشند')
    new, replace, maintenance, ens, loss, interest, inflation = vals
    if min(new, replace, maintenance) < 0 or interest <= -1 or inflation <= -1:
        raise ValueError('هزینه‌ها باید نامنفی و نرخ‌ها بزرگ‌تر از منفی صد درصد باشند')
    if not isinstance(years, int) or isinstance(years, bool) or not 1 <= years <= 100:
        raise ValueError('طول عمر باید عدد صحیح بین ۱ و ۱۰۰ سال باشد')
    try:
        cashflows = [(ens + loss - maintenance) * ((1 + inflation) / (1 + interest)) ** t for t in range(1, years + 1)]
        value = -new - replace + sum(cashflows)
    except OverflowError as exc: raise ValueError('سرریز در محاسبه اقتصادی') from exc
    if not isfinite(value): raise ValueError('سرریز در محاسبه اقتصادی')
    return {'npw': value, 'annual_discounted_cashflows': cashflows,
            'assumption': 'درآمد و هزینه نگهداری سالانه ثابت؛ نرخ بهره و تورم ثابت؛ معادله ۲ راهنما'}
