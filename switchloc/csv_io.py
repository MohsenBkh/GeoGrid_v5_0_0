"""Interoperable UTF-8 CSV exports of already-calculated preliminary results."""
import csv
from .methodology import CRITERIA


def export_ranking_csv(path, results):
    fields = ['rank', 'feeder', 'score'] + [f'{key}_{part}' for key, *_ in CRITERIA for part in ('raw', 'transformed', 'normalized', 'weight', 'contribution')] + ['warnings']
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f); writer.writerow(fields)
        for i, row in enumerate(results, 1):
            writer.writerow([i, row['feeder'], row['score']] + [row['criteria'][key][part] for key, *_ in CRITERIA for part in ('raw', 'transformed', 'normalized', 'weight', 'contribution')] + ['; '.join(row['warnings'])])


def export_placement_csv(path, result):
    fields = ['branch', 'from_node', 'to_node', 'x', 'y', 'telecom', 'reason', 'warnings']
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for row in result['proposals']:
            writer.writerow(dict(row, warnings='; '.join(result['warnings'])))
