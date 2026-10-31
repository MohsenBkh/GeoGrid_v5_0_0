from pathlib import Path
import pytest
from openpyxl import load_workbook
from switchloc.methodology import rank_feeders
from switchloc.excel_io import create_template, load_feeders, export_ranking, import_outages


def feeder(name, connections):
    return dict(feeder=name, connections=connections, ep=1, tl=1, load_priority=1, failure_rate=1, outage_duration=1)


def test_guide_table16_example():
    rows = rank_feeders([feeder(str(i), x) for i, x in enumerate([1, 2, 0, 4])])
    vals = {r['feeder']: r['criteria']['connections']['normalized'] for r in rows}
    assert [round(vals[str(i)], 3) for i in range(4)] == [.085, .043, .851, .021]
    assert rows[0]['feeder'] == '2'


def test_reject_invalid_and_duplicate():
    with pytest.raises(ValueError): rank_feeders([feeder('a', -1)])
    with pytest.raises(ValueError): rank_feeders([feeder('a', 1), feeder('a', 2)])
    with pytest.raises(ValueError): rank_feeders([feeder('a', float('nan'))])


def test_zero_sum_warns():
    x = feeder('a', 1); x['ep'] = 0
    row = rank_feeders([x])[0]
    assert row['criteria']['ep']['contribution'] == 0 and row['warnings']


def test_excel_roundtrip(tmp_path):
    template = tmp_path / 'in.xlsx'; output = tmp_path / 'out.xlsx'
    create_template(template); data = load_feeders(template); export_ranking(output, rank_feeders(data))
    wb = load_workbook(output, read_only=True, data_only=True)
    assert wb['ranking'].max_row == 3
    assert 'connections_contribution' in next(wb['ranking'].values)
    wb.close()


def test_real_outages():
    path = next(Path(__file__).resolve().parents[1].glob('*1405.xlsx'))
    rows, warnings = import_outages(path)
    assert len(rows) > 1000 and len({r['sheet'] for r in rows}) == 2
    assert rows[0]['event_id'] == 10045773 and rows[0]['duration_hours'] == 0
    assert any('شش سال' in w for w in warnings)


def test_exploratory_radial_placement_and_excel(tmp_path):
    from switchloc.network_io import create_network_template, load_network, export_placement
    source = tmp_path / 'network.xlsx'; out = tmp_path / 'result.xlsx'
    create_network_template(source); result = load_network(source)
    assert result['examined'] == 3
    assert len(result['proposals']) == 1 and len(result['zones']) == 2
    assert sum(z['load_kw'] for z in result['zones']) == 300
    assert sum(z['u_hours_per_year'] for z in result['zones']) == 3
    assert result['warnings']
    export_placement(out, result)
    wb = load_workbook(out, read_only=True)
    assert {'proposals', 'zones', 'warnings'} <= set(wb.sheetnames)
    wb.close()


def test_placement_rejects_loops_open_missing_data():
    from switchloc.placement import analyze
    nodes = [{'id': 's', 'load_kw': 0}, {'id': 'a', 'load_kw': 1}, {'id': 'b', 'load_kw': 2}]
    def branch(id, a, b):
        return dict(id=id, from_node=a, to_node=b, status='closed', candidate=True, existing_switch=False, lambda_per_year=1, repair_hours=1)
    branches = [branch('1', 's', 'a'), branch('2', 'a', 'b')]
    with pytest.raises(ValueError): analyze(nodes, branches + [branch('3', 'b', 's')], 's', 1)
    with pytest.raises(ValueError): analyze(nodes, [dict(branches[0], status='open'), branches[1]], 's', 1)
    with pytest.raises(ValueError): analyze(nodes, [dict(branches[0], repair_hours=None), branches[1]], 's', 1)
    with pytest.raises(ValueError): analyze(nodes, branches, 's', 3)


def test_existing_switch_is_a_fixed_boundary():
    from switchloc.placement import analyze
    nodes = [{'id': x, 'load_kw': 1} for x in ('s', 'a', 'b')]
    branches = [dict(id='1', from_node='s', to_node='a', status='closed', candidate=False, existing_switch=True, lambda_per_year=1, repair_hours=1),
                dict(id='2', from_node='a', to_node='b', status='closed', candidate=True, existing_switch=False, lambda_per_year=1, repair_hours=1)]
    result = analyze(nodes, branches, 's', 1)
    assert result['proposals'][0]['branch'] == '2'
    assert len(result['zones']) == 3


def test_npw_equation_two():
    from switchloc.economics import net_present_worth
    result = net_present_worth(100, 20, 5, 30, 5, .1, .1, 3)
    assert result['npw'] == pytest.approx(-30)
    assert result['annual_discounted_cashflows'] == pytest.approx([30, 30, 30])
    with pytest.raises(ValueError): net_present_worth(1, 1, 1, 1, 1, -1, .1, 3)


def test_outage_review_actual_and_exclusions(tmp_path):
    from switchloc.outages import export_review, read_review, summarize
    path = next(Path(__file__).resolve().parents[1].glob('*1405.xlsx'))
    events, _ = import_outages(path)
    review = tmp_path / 'review.xlsx'; export_review(review, events[:5])
    rows = read_review(review)
    assert rows[0]['event_id'] == events[0]['event_id']
    assert summarize(rows)['included'] == 5
    wb = load_workbook(review); ws = wb['outages']; ws['I2'] = 'حذف‌شده'; wb.save(review); wb.close()
    with pytest.raises(ValueError): read_review(review)
    wb = load_workbook(review); wb['outages']['J2'] = 'تکراری'; wb.save(review); wb.close()
    assert summarize(read_review(review))['excluded'] == 1


def test_projects_revision_provenance(tmp_path):
    from switchloc.projects import save_project, load_project
    source = tmp_path / 'input.txt'; source.write_text('original')
    path = tmp_path / 'study.sqlite'
    save_project(path, 'مطالعه', {'value': 1}, [source])
    first = load_project(path)
    assert first['revision'] == 1 and len(first['sources'][0]['sha256']) == 64
    source.unlink()
    save_project(path, 'مطالعه', {'value': 2}, previous_sources=first['sources'])
    second = load_project(path)
    assert second['revision'] == 2 and second['data']['value'] == 2 and second['sources'] == first['sources']
    with pytest.raises(ValueError): save_project(path, '', {})


def test_csv_output_warns(tmp_path):
    import csv
    from switchloc.csv_io import export_placement_csv
    path = tmp_path / 'points.csv'
    export_placement_csv(path, {'proposals': [{'branch': 'b1', 'from_node': 's', 'to_node': 'a', 'x': 1, 'y': 2, 'telecom': 'نامشخص', 'reason': 'test'}], 'warnings': ['اکتشافی']})
    with path.open(encoding='utf-8-sig', newline='') as f: row = next(csv.DictReader(f))
    assert row['branch'] == 'b1' and row['warnings'] == 'اکتشافی'


def test_project_will_not_modify_other_database(tmp_path):
    import sqlite3
    from switchloc.projects import save_project
    path = tmp_path / 'other.sqlite'
    with sqlite3.connect(path) as db: db.execute('CREATE TABLE other (x INTEGER)')
    with pytest.raises(ValueError): save_project(path, 'مطالعه', {})
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [('other',)]


def test_n1_reserve_shared_and_fault_isolation(tmp_path):
    from switchloc.n1 import calculate
    zones = [dict(zone=z, feeder='F', load_kw=load) for z, load in [('s', 40), ('a', 100), ('b', 100)]]
    links = [dict(from_zone='s', to_zone='a', switchable=True, capacity_kw=300), dict(from_zone='a', to_zone='b', switchable=True, capacity_kw=300)]
    ties = [dict(id='T1', zone='a', backup_feeder='B', reserve_kw=50, capacity_kw=50, normal_status='open', automated=True),
            dict(id='T2', zone='b', backup_feeder='B', reserve_kw=50, capacity_kw=50, normal_status='open', automated=True)]
    result = calculate(zones, links, ties, 'F', 's')
    failed_source = next(r for r in result['scenarios'] if r['failed_zone'] == 's')
    assert failed_source['backup_restored_kw'] == pytest.approx(50)
    assert failed_source['interrupted_kw'] == pytest.approx(190)
    assert failed_source['backup_by_feeder']['B'] == pytest.approx(50)
    failed_a = next(r for r in result['scenarios'] if r['failed_zone'] == 'a')
    assert failed_a['source_restored_kw'] == 40
    assert failed_a['backup_restored_kw'] == 50
    assert failed_a['interrupted_kw'] == 150
    with pytest.raises(ValueError): calculate(zones, links, [dict(ties[0], reserve_kw=20), ties[1]], 'F', 's')


def test_n1_excel_roundtrip(tmp_path):
    from switchloc.n1_io import create_n1_template, load_n1, export_n1
    src = tmp_path / 'n1.xlsx'; dst = tmp_path / 'n1_out.xlsx'
    create_n1_template(src); result = load_n1(src); export_n1(dst, result)
    assert len(result['scenarios']) == 3
    wb = load_workbook(dst, read_only=True); assert 'warnings' in wb.sheetnames; wb.close()


def test_report_contains_warnings_and_results(tmp_path):
    from docx import Document
    from switchloc.report import create_report
    path = tmp_path / 'report.docx'
    create_report(path, 'test', {'results': rank_feeders([feeder('f', 1)]), 'events': None}, [])
    doc = Document(path)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'اکتشافی' in text and 'EP و TL' in text and 'تکمیل‌نشده' in text
    assert len(doc.tables) == 1


def test_placement_ens_matches_equation8_and_branching():
    from switchloc.placement import analyze
    nodes = [{'id': k, 'load_kw': v} for k, v in [('s', 1), ('a', 2), ('b', 3), ('c', 4)]]
    def edge(name, a, b): return dict(id=name, from_node=a, to_node=b, status='closed', existing_switch=True, candidate=False, lambda_per_year=1, repair_hours=1)
    # Fault at a disconnects a and b, not sibling c. Root has no fault U.
    result = analyze(nodes, [edge('1', 's', 'a'), edge('2', 'a', 'b'), edge('3', 's', 'c')], 's', 0)
    assert result['score'] == pytest.approx((2+3) + 3 + 4)
    assert sum(z['ens_kwh_per_year'] for z in result['zones']) == pytest.approx(12)


def test_compare_scenarios_and_export(tmp_path):
    from switchloc.network_io import read_network, create_network_template
    from switchloc.scenarios import compare, export_comparison
    src = tmp_path / 'network.xlsx'; dst = tmp_path / 'plans.xlsx'
    create_network_template(src)
    nodes, branches, root, _ = read_network(src)
    result = compare(nodes, branches, root, [0, 1, 2])
    assert len(result['plans']) == 3
    assert result['plans'][0]['improvement_kwh_per_year'] == 0
    assert result['plans'][2]['e2_kwh_per_year'] <= result['plans'][1]['e2_kwh_per_year']
    export_comparison(dst, result)
    wb = load_workbook(dst, read_only=True)
    assert wb['plans'].max_row == 4 and 'warnings' in wb.sheetnames
    wb.close()


def test_metrics_guideline_table_15(tmp_path):
    from switchloc.metrics_io import create_metrics_template, load_metrics, export_metrics
    from switchloc.metrics import calculate_ep_tl
    path = tmp_path / 'metrics.xlsx'; out = tmp_path / 'out.xlsx'; create_metrics_template(path)
    result = load_metrics(path)
    assert result['ep_percent'] == pytest.approx(72) and result['tl_percent'] == pytest.approx(28)
    export_metrics(out, result)
    wb = load_workbook(out, read_only=True); assert wb['cases'].max_row == 6; wb.close()
    with pytest.raises(ValueError): calculate_ep_tl(100, [{'zone': 'a', 'interrupted_kw': 100, 'transferable_kw': 1}])


def test_shapefile_export_requires_crs_and_coordinates(tmp_path):
    import shapefile
    from switchloc.geo_export import export_points_shapefile
    path = tmp_path / 'points.shp'
    row = {'branch': 'b1', 'from_node': 's', 'to_node': 'a', 'x': 500, 'y': 900, 'telecom': 'نامشخص', 'reason': 'x'}
    with pytest.raises(ValueError): export_points_shapefile(path, {'proposals': [row]}, '')
    assert not path.exists()
    with pytest.raises(ValueError): export_points_shapefile(path, {'proposals': [dict(row, x=None)]}, 'wkt')
    export_points_shapefile(path, {'proposals': [row]}, 'PROJCS["sample"]')
    assert shapefile.Reader(str(path)).shapes()[0].points[0] == (500.0, 900.0)
    with pytest.raises(ValueError): export_points_shapefile(path, {'proposals': [row]}, 'wkt')


def test_multifeeder_optimization_and_manual_edit(tmp_path):
    from switchloc.multifeeder_io import create_template, load_model, export_result
    from switchloc.multifeeder import optimize, evaluate
    path = tmp_path / 'model.xlsx'; output = tmp_path / 'output.xlsx'
    create_template(path); model, count = load_model(path)
    base = evaluate(model, [])
    best = optimize(model, count)
    assert best['examined'] == 6 and len(best['proposals']) == count
    assert len(best['feeders']) == 2 and best['ens_kwh_per_year'] <= base['ens_kwh_per_year']
    manual = evaluate(model, best['selected'])
    assert manual['ens_kwh_per_year'] == pytest.approx(best['ens_kwh_per_year'])
    export_result(output, best, model['crs'])
    wb = load_workbook(output, read_only=True); assert {'n1', 'backup', 'warnings'} <= set(wb.sheetnames); wb.close()
    with pytest.raises(ValueError): evaluate(model, ['invalid'])


def test_multifeeder_reserve_and_tie_availability(tmp_path):
    from switchloc.multifeeder_io import create_template, load_model
    from switchloc.multifeeder import evaluate
    path = tmp_path / 'model.xlsx'; create_template(path); model, _ = load_model(path)
    with_tie = evaluate(model, ['a01', 'a12'])
    model['ties'][0]['automated'] = False
    without_tie = evaluate(model, ['a01', 'a12'])
    assert with_tie['ens_kwh_per_year'] <= without_tie['ens_kwh_per_year']
    assert any(x['backup_restored_kw'] > 0 for f in with_tie['feeders'] for x in f['scenarios'])
    model['feeders'][1]['reserve_kw'] = -1
    with pytest.raises(ValueError): evaluate(model, [])


def test_multifeeder_invalid_inputs_and_search_limit(tmp_path):
    from switchloc.multifeeder_io import create_template, load_model
    from switchloc.multifeeder import optimize, evaluate
    path = tmp_path / 'model.xlsx'; create_template(path); model, _ = load_model(path)
    with pytest.raises(ValueError): optimize(model, 2, limit=5)
    with pytest.raises(ValueError): evaluate(model, ['a01', 'a01'])
    model['ties'][0]['normal_status'] = 'closed'
    with pytest.raises(ValueError): evaluate(model, [])


def test_multifeeder_restoration_uses_reserve(tmp_path):
    from switchloc.multifeeder_io import create_template, load_model
    from switchloc.multifeeder import evaluate
    path = tmp_path / 'model.xlsx'; create_template(path); model, _ = load_model(path)
    result = evaluate(model, ['a01', 'a12'])
    for feeder in result['feeders']:
        for scenario in feeder['scenarios']:
            if feeder['feeder'] == 'F1':
                assert scenario['backup_restored_kw'] <= 70
            if feeder['feeder'] == 'F2':
                assert scenario['backup_restored_kw'] <= 70
            assert scenario['ens_kwh_per_year'] == pytest.approx(scenario['interrupted_kw'] * scenario['u_hours_per_year'])
