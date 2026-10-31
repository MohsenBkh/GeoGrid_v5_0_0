"""Small offline GUI for the implemented, explicitly preliminary workflow."""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from .excel_io import create_template, load_feeders, export_ranking, import_outages
from .methodology import rank_feeders
from .gis import inspect_layers
from .network_io import create_network_template, load_network, export_placement, read_network
from .outages import export_review, read_review, summarize
from .projects import save_project, load_project
from .csv_io import export_ranking_csv, export_placement_csv
from .economics import net_present_worth
from .n1_io import create_n1_template, load_n1, export_n1
from .report import create_report
from .scenarios import compare, export_comparison
from .metrics_io import create_metrics_template, load_metrics, export_metrics
from .geo_export import export_points_shapefile
from .multifeeder_io import create_template as create_multi_template, load_model as load_multi_model
from .multimap import MultiMap


def main():
    root = tk.Tk(); root.title('SwitchLoc — ابزار اولیه مطالعات'); root.geometry('1000x620')
    state = {'results': None, 'input': None, 'placement': None, 'network_input': None, 'events': None, 'outage_input': None, 'project': None, 'project_name': None, 'sources': [], 'n1': None, 'n1_input': None, 'comparison': None, 'comparison_input': None, 'metrics': None, 'metrics_input': None, 'multi_model': None, 'multi_count': None, 'multi_result': None, 'multi_input': None}
    bar = ttk.Frame(root, padding=8); bar.pack(fill='x')
    bar2 = ttk.Frame(root, padding=8); bar2.pack(fill='x')
    bar3 = ttk.Frame(root, padding=8); bar3.pack(fill='x')
    bar4 = ttk.Frame(root, padding=8); bar4.pack(fill='x')
    bar5 = ttk.Frame(root, padding=8); bar5.pack(fill='x')
    bar6 = ttk.Frame(root, padding=8); bar6.pack(fill='x')
    message = tk.StringVar(value='نسخه اکتشافی و غیرمعتبر مطالعاتی؛ محدودیت‌ها و فرضیات را پیش از استفاده بررسی کنید.')
    ttk.Label(root, textvariable=message, wraplength=950).pack(fill='x', padx=10, pady=8)
    columns = ('rank', 'feeder', 'score')
    table = ttk.Treeview(root, columns=columns, show='headings')
    for col, title in zip(columns, ('رتبه', 'فیدر', 'امتیاز')): table.heading(col, text=title); table.column(col, width=150)
    table.pack(fill='both', expand=True, padx=10, pady=10)
    def run(fn):
        try: fn()
        except Exception as exc: messagebox.showerror('خطا', str(exc), parent=root)
    def template():
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path:
            ensure_output(path); create_template(path); message.set('قالب نمونه ذخیره شد؛ داده نمونه باید جایگزین شود.')
    def load():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        state['results'] = None
        for item in table.get_children(): table.delete(item)
        results = rank_feeders(load_feeders(path)); state['results'] = results; state['input'] = Path(path).resolve()
        for i, row in enumerate(results, 1): table.insert('', 'end', values=(i, row['feeder'], f"{row['score']:.6f}"))
        message.set('رتبه‌بندی اولیه با داده‌های واردشده؛ EP و TL و فرضیات نیازمند تأیید مستقل هستند.')
    def ensure_output(path):
        protected = {str(Path(x).resolve()) for x in (state['input'], state['network_input'], state['outage_input'], state['project'], state['n1_input'], state['comparison_input'], state['metrics_input'], state['multi_input']) if x}
        protected.update(s['path'] for s in state['sources'])
        if str(Path(path).resolve()) in protected: raise ValueError('مسیر خروجی با یکی از فایل‌های ورودی یکسان است.')
    def save():
        if state['results'] is None: raise ValueError('ابتدا فیدرها را وارد کنید.')
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path:
            if state['input'] and Path(path).resolve() == state['input']: raise ValueError('مسیر خروجی باید با فایل ورودی متفاوت باشد.')
            ensure_output(path)
            export_ranking(path, state['results']); message.set('جزئیات رتبه‌بندی ذخیره شد.')
    def outages():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if path:
            rows, warnings = import_outages(path)
            state['events'] = rows; state['outage_input'] = str(Path(path).resolve())
            messagebox.showinfo('خاموشی', f'{len(rows)} رخداد خوانده شد.\n' + '\n'.join(warnings[:10]), parent=root)
    def outage_review():
        if state['events'] is None: raise ValueError('ابتدا فایل خاموشی را وارد کنید.')
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path:
            if state['outage_input'] and Path(path).resolve() == Path(state['outage_input']).resolve(): raise ValueError('فایل بازبینی باید با ورودی متفاوت باشد')
            ensure_output(path)
            export_review(path, state['events']); message.set('فایل بازبینی را ویرایش و سپس مجدداً وارد کنید.')
    def outage_summary():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        events = read_review(path); summary = summarize(events)
        state['events'] = events; state['outage_input'] = str(Path(path).resolve())
        counts = '\n'.join(f'{k}: {v}' for k, v in summary['categories'].items())
        messagebox.showinfo('خلاصه خاموشی', f"رخداد: {summary['events']}، حذف‌شده: {summary['excluded']}\nمجموع مدت معتبر: {summary['duration_hours']:.2f} ساعت\n{counts}\n{summary['warning']}", parent=root)
    def save_study():
        path = state['project'] or filedialog.asksaveasfilename(defaultextension='.sqlite', filetypes=[('SwitchLoc project', '*.sqlite')])
        if not path: return
        name = state['project_name'] or simpledialog.askstring('پروژه', 'نام پروژه:', parent=root)
        if not name: return
        sources = [str(state[k]) for k in ('input', 'network_input', 'outage_input', 'n1_input', 'comparison_input', 'metrics_input', 'multi_input') if state[k] and Path(state[k]).is_file()]
        snapshot = {k: state[k] for k in ('results', 'placement', 'events', 'n1', 'comparison', 'metrics', 'multi_model', 'multi_count', 'multi_result')}
        save_project(path, name, snapshot, sources, state['sources'])
        state['sources'] = load_project(path)['sources']
        state['project'] = str(Path(path).resolve()); state['project_name'] = name
        message.set('نسخه جدید پروژه و اثرانگشت فایل‌های موجود ذخیره شد.')
    def open_study():
        path = filedialog.askopenfilename(filetypes=[('SwitchLoc project', '*.sqlite')])
        if not path: return
        project = load_project(path); data = project['data']
        for key in ('results', 'placement', 'events', 'n1', 'comparison', 'metrics', 'multi_model', 'multi_count', 'multi_result'): state[key] = data.get(key)
        # Original paths are recorded in project provenance; do not silently reload changed inputs.
        for key in ('input', 'network_input', 'outage_input', 'n1_input', 'comparison_input', 'metrics_input', 'multi_input'): state[key] = None
        state['project'] = str(Path(path).resolve()); state['project_name'] = project['name']; state['sources'] = project['sources']
        for item in table.get_children(): table.delete(item)
        if state['results']:
            for i, row in enumerate(state['results'], 1): table.insert('', 'end', values=(i, row['feeder'], f"{row['score']:.6f}"))
        message.set(f"پروژه {project['name']}، نسخه {project['revision']} باز شد. منابع اصلی به‌طور خودکار بازخوانی نشده‌اند.")
    def gis():
        path = filedialog.askdirectory()
        if path:
            layers = inspect_layers(path)
            messagebox.showinfo('لایه‌ها', '\n'.join("{}: {} رکورد".format(x["path"], x["records"]) for x in layers) or 'لایه‌ای یافت نشد', parent=root)
    def network_template():
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path:
            ensure_output(path); create_network_template(path); message.set('قالب شبکه نمونه ذخیره شد؛ داده‌ها را با اطلاعات تأییدشده جایگزین کنید.')
    def placement():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        state['placement'] = None
        result = load_network(path); state['placement'] = result; state['network_input'] = Path(path).resolve()
        for item in table.get_children(): table.delete(item)
        for i, p in enumerate(result['proposals'], 1): table.insert('', 'end', values=(i, p['branch'], p['to_node']))
        message.set('جایابی اکتشافی: ستون فیدر شناسه شاخه و ستون امتیاز گره پایین‌دست است. خروجی و فرضیات را بررسی کنید.')
        messagebox.showwarning('محدودیت‌های جایابی', '\n'.join(result['warnings']), parent=root)
    def save_placement():
        if state['placement'] is None: raise ValueError('ابتدا شبکه را برای جایابی وارد کنید.')
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path:
            if state['network_input'] and Path(path).resolve() == state['network_input']: raise ValueError('مسیر خروجی باید با فایل ورودی متفاوت باشد.')
            ensure_output(path)
            export_placement(path, state['placement']); message.set('خروجی اکتشافی و فرضیات ذخیره شد.')
    def multi_template():
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path: ensure_output(path); create_multi_template(path); message.set('قالب شبکه چندفیدری نمونه ایجاد شد.')
    def multi_open():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        model, count = load_multi_model(path)
        state['multi_model'] = model; state['multi_count'] = count; state['multi_result'] = None
        state['multi_input'] = str(Path(path).resolve()); show_multimap()
    def show_multimap():
        if state['multi_model'] is None: raise ValueError('ابتدا شبکه چندفیدری را وارد کنید')
        protected = [state[k] for k in ('input','network_input','outage_input','n1_input','comparison_input','metrics_input','multi_input','project') if state[k]]
        protected += [s['path'] for s in state['sources']]
        def updated(result): state['multi_result'] = result
        # Project snapshots retain the model even when the original source is unavailable.
        source = state['multi_input'] or state['project'] or str(Path.cwd() / '__switchloc_no_source__')
        window = MultiMap(root, state['multi_model'], state['multi_count'], source, on_result=updated, protected=protected)
        if state['multi_result'] is not None: window.set_result(state['multi_result'])
    def shapefile_export():
        if state['placement'] is None: raise ValueError('ابتدا جایابی اکتشافی را اجرا کنید')
        prj = filedialog.askopenfilename(title='فایل PRJ منطبق با مختصات گره‌ها را انتخاب کنید', filetypes=[('Projection', '*.prj')])
        if not prj: return
        path = filedialog.asksaveasfilename(defaultextension='.shp', filetypes=[('Shapefile', '*.shp')])
        if path:
            ensure_output(path)
            export_points_shapefile(path, state['placement'], Path(prj).read_text(encoding='utf-8-sig'))
            messagebox.showwarning('نقاط اکتشافی', 'مختصات گره پایین‌دست لزوماً محل دقیق نصب نیست. صحت سیستم مختصات و پوشش مخابرات باید بررسی شود.', parent=root)
    def metrics_template():
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path: ensure_output(path); create_metrics_template(path); message.set('قالب جدول EP/TL ساخته شد؛ مثال جدول ۱۵ را جایگزین کنید.')
    def metrics_run():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        state['metrics'] = None
        result = load_metrics(path); state['metrics'] = result; state['metrics_input'] = Path(path).resolve()
        messagebox.showinfo('EP و TL', f"EP = {result['ep_percent']:.2f}%، TL = {result['tl_percent']:.2f}%\n{result['warning']}", parent=root)
    def metrics_save():
        if state['metrics'] is None: raise ValueError('ابتدا EP/TL را محاسبه کنید')
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path: ensure_output(path); export_metrics(path, state['metrics']); message.set('خروجی EP/TL ذخیره شد.')
    def compare_plans():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        text = simpledialog.askstring('مقایسه طرح‌ها', 'تعداد کلیدها را با ویرگول وارد کنید، مثلاً 0,1,2:', initialvalue='0,1,2', parent=root)
        if text is None: return
        try: counts = [int(x.strip()) for x in text.split(',')]
        except ValueError as exc: raise ValueError('تعداد کلیدها نامعتبر است') from exc
        state['comparison'] = None
        nodes, branches, root_node, _ = read_network(path)
        result = compare(nodes, branches, root_node, counts)
        state['comparison'] = result; state['comparison_input'] = Path(path).resolve()
        for item in table.get_children(): table.delete(item)
        for i, plan in enumerate(result['plans'], 1):
            table.insert('', 'end', values=(i, plan['new_switches'], f"{plan['e2_kwh_per_year']:.2f}"))
        message.set('مقایسه اکتشافی: ستون فیدر تعداد کلید جدید و ستون امتیاز ENS است.')
        messagebox.showwarning('محدودیت مقایسه', '\n'.join(result['warnings']), parent=root)
    def save_comparison():
        if state['comparison'] is None: raise ValueError('ابتدا طرح‌ها را مقایسه کنید')
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path: ensure_output(path); export_comparison(path, state['comparison']); message.set('نتایج مقایسه اکتشافی ذخیره شد.')
    def report():
        path = filedialog.asksaveasfilename(defaultextension='.docx', filetypes=[('Word', '*.docx')])
        if path:
            ensure_output(path); create_report(path, state['project_name'], state, state['sources'])
            message.set('گزارش اولیه و قابل ویرایش با هشدارهای مهندسی ذخیره شد.')
    def n1_template():
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path: ensure_output(path); create_n1_template(path); message.set('قالب نمونه N-1 ساخته شد؛ داده‌ها باید جایگزین شوند.')
    def n1_run():
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx')])
        if not path: return
        state['n1'] = None
        result = load_n1(path); state['n1'] = result; state['n1_input'] = Path(path).resolve()
        for item in table.get_children(): table.delete(item)
        for i, row in enumerate(result['scenarios'], 1):
            table.insert('', 'end', values=(i, row['failed_zone'], f"{row['interrupted_kw']:.2f}"))
        message.set('N-1 اکتشافی: ستون فیدر زون خطادیده و ستون امتیاز بار قطع‌شده است.')
        messagebox.showwarning('محدودیت تحلیل N-1', '\n'.join(result['warnings']), parent=root)
    def n1_save():
        if state['n1'] is None: raise ValueError('ابتدا تحلیل N-1 را اجرا کنید')
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path: ensure_output(path); export_n1(path, state['n1']); message.set('سناریوها و هشدارها ذخیره شد.')
    def csv_ranking():
        if state['results'] is None: raise ValueError('ابتدا رتبه‌بندی را اجرا کنید')
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if path: ensure_output(path); export_ranking_csv(path, state['results']); message.set('CSV رتبه‌بندی ذخیره شد.')
    def csv_placement():
        if state['placement'] is None: raise ValueError('ابتدا جایابی را اجرا کنید')
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if path: ensure_output(path); export_placement_csv(path, state['placement']); message.set('CSV نقاط ذخیره شد؛ هشدارها در خروجی Excel موجودند.')
    def economics():
        values = []
        for prompt in ('هزینه خرید و نصب', 'هزینه جابجایی', 'هزینه نگهداری سالانه', 'درآمد سالانه کاهش خاموشی', 'درآمد سالانه کاهش تلفات', 'نرخ بهره به صورت اعشار (مثلاً 0.2)', 'نرخ تورم به صورت اعشار'):
            value = simpledialog.askfloat('ارزش فعلی خالص', prompt, parent=root)
            if value is None: return
            values.append(value)
        years = simpledialog.askinteger('ارزش فعلی خالص', 'طول عمر به سال', parent=root, minvalue=1, maxvalue=100)
        if years is None: return
        result = net_present_worth(*values, years)
        messagebox.showinfo('ارزش فعلی خالص', f"NPW: {result['npw']:.2f}\n{result['assumption']}\nشاخص CE/CN و انتخاب طرح محاسبه نشده است.", parent=root)
    for label, fn in [('ساخت قالب Excel', template), ('ورود و رتبه‌بندی', load), ('خروجی Excel', save), ('CSV رتبه‌بندی', csv_ranking), ('بررسی خاموشی', outages), ('فهرست GIS', gis)]:
        ttk.Button(bar, text=label, command=lambda f=fn: run(f)).pack(side='right', padx=3)
    for label, fn in [('قالب شبکه', network_template), ('جایابی اکتشافی', placement), ('خروجی جایابی', save_placement), ('CSV نقاط', csv_placement), ('ارزش فعلی', economics)]:
        ttk.Button(bar2, text=label, command=lambda f=fn: run(f)).pack(side='right', padx=3)
    for label, fn in [('خروجی بازبینی خاموشی', outage_review), ('خلاصه بازبینی', outage_summary), ('ذخیره پروژه', save_study), ('بازکردن پروژه', open_study)]:
        ttk.Button(bar3, text=label, command=lambda f=fn: run(f)).pack(side='right', padx=3)
    for label, fn in [('قالب N-1', n1_template), ('تحلیل N-1 اکتشافی', n1_run), ('خروجی N-1', n1_save), ('گزارش Word', report), ('مقایسه طرح‌ها', compare_plans), ('خروجی مقایسه', save_comparison)]:
        ttk.Button(bar4, text=label, command=lambda f=fn: run(f)).pack(side='right', padx=3)
    for label, fn in [('قالب EP/TL', metrics_template), ('محاسبه EP/TL تأییدشده', metrics_run), ('خروجی EP/TL', metrics_save), ('خروجی Shapefile', shapefile_export)]:
        ttk.Button(bar5, text=label, command=lambda f=fn: run(f)).pack(side='right', padx=3)
    for label, fn in [('قالب چندفیدری', multi_template), ('ورود شبکه و نقشه', multi_open), ('بازکردن نقشه', show_multimap)]:
        ttk.Button(bar6, text=label, command=lambda f=fn: run(f)).pack(side='right', padx=3)
    root.mainloop()

if __name__ == '__main__': main()
