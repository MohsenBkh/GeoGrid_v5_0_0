"""Export preliminary proposal points as shapefile with an explicit CRS."""
from math import isfinite
from pathlib import Path
import shapefile


def export_points_shapefile(path, result, crs_wkt):
    path = Path(path).with_suffix('.shp')
    if not crs_wkt or not str(crs_wkt).strip(): raise ValueError('فایل سیستم مختصات PRJ الزامی است')
    proposals = result.get('proposals', [])
    if not proposals: raise ValueError('نقطه پیشنهادی وجود ندارد')
    # Validate all before touching the output dataset.
    checked = []
    for row in proposals:
        try: x = float(row['x']); y = float(row['y'])
        except (KeyError, TypeError, ValueError) as exc: raise ValueError(f"مختصات شاخه {row.get('branch')} نامشخص است") from exc
        if not isfinite(x) or not isfinite(y): raise ValueError('مختصات نامعتبر است')
        checked.append((row, x, y))
    # Never overwrite any part of an existing shapefile dataset.
    for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
        if path.with_suffix(ext).exists(): raise ValueError(f'خروجی موجود است: {path.with_suffix(ext)}')
    with shapefile.Writer(str(path), shapeType=shapefile.POINT, encoding='utf-8') as writer:
        for name, size in [('BRANCH', 80), ('FROM_NODE', 80), ('TO_NODE', 80), ('TELECOM', 80), ('STATUS', 40)]:
            writer.field(name, 'C', size=size)
        for row,x,y in checked:
            writer.point(x,y)
            writer.record(str(row['branch']), str(row['from_node']), str(row['to_node']), 'unknown', 'PRELIMINARY')
    path.with_suffix('.prj').write_text(str(crs_wkt), encoding='utf-8')
    path.with_suffix('.cpg').write_text('UTF-8', encoding='ascii')
