"""Inspect shapefile layers using GeoGrid's existing shapefile reader.

This is an inventory only: proximity is not proof of electrical connectivity.
"""
from pathlib import Path
from shp2dgs.core.shapefile_io import read_layer


def inspect_layers(directory):
    layers = []
    for path in sorted(Path(directory).rglob('*.shp')):
        records, shapes = read_layer(str(path.parent), path.stem)
        prj = path.with_suffix('.prj')
        layers.append({'path': str(path), 'records': len(records), 'shapes': len(shapes),
                       'fields': sorted(records[0].keys()) if records else [],
                       'crs_wkt': prj.read_text(errors='replace') if prj.exists() else None})
    return layers
