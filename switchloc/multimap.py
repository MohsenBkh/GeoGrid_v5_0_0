"""Offline interactive schematic in the supplied coordinate system.

This is a vector network view, not a basemap or a CRS transformer.
"""
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from .multifeeder import evaluate, optimize
from .multifeeder_io import export_result

PALETTE = ['#1670ad', '#df8130', '#098c68', '#a957a2', '#af3939', '#5960ad']


def segment_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1
    length = dx*dx + dy*dy
    t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy) / length)) if length else 0
    return math.hypot(px - (x1+t*dx), py - (y1+t*dy))


class MultiMap:
    def __init__(self, parent, model, count, source_path, on_result=None, protected=()):
        self.model = model; self.count = count; self.source_path = Path(source_path).resolve()
        self.on_result = on_result; self.protected = {Path(p).resolve() for p in protected if p}
        self.selected = set(); self.result = None; self.scale = 1.; self.offset_x = 0.; self.offset_y = 0.
        self.nodes = {str(n['id']): n for n in model['nodes']}
        self.colors = {f['id']: PALETTE[i % len(PALETTE)] for i, f in enumerate(model['feeders'])}
        self.win = tk.Toplevel(parent); self.win.title('نقشه شبکه و جایابی چندفیدری — اکتشافی'); self.win.geometry('1100x760')
        toolbar = ttk.Frame(self.win, padding=6); toolbar.pack(fill='x')
        ttk.Button(toolbar, text='بهینه‌سازی', command=self.run_optimization).pack(side='right', padx=3)
        ttk.Button(toolbar, text='محاسبه انتخاب دستی', command=self.run_manual).pack(side='right', padx=3)
        ttk.Button(toolbar, text='برازش نقشه', command=self.fit).pack(side='right', padx=3)
        ttk.Button(toolbar, text='خروجی Excel', command=self.save).pack(side='right', padx=3)
        self.status = tk.StringVar(value='روی شاخه کاندید کلیک کنید؛ چرخ ماوس بزرگ‌نمایی و دکمه راست جابه‌جایی نقشه است.')
        ttk.Label(self.win, textvariable=self.status, wraplength=1050).pack(fill='x', padx=8)
        self.canvas = tk.Canvas(self.win, bg='#f5f8fc', highlightthickness=0); self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Button-1>', self.toggle); self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<ButtonPress-3>', self.pan_start); self.canvas.bind('<B3-Motion>', self.pan)
        self.canvas.bind('<MouseWheel>', self.wheel); self.canvas.bind('<Button-4>', lambda e: self.zoom(e.x,e.y,1.2)); self.canvas.bind('<Button-5>', lambda e: self.zoom(e.x,e.y,1/1.2))
        self.win.after(100, self.fit)

    def xy(self, node):
        return (float(node['x'])*self.scale+self.offset_x, -float(node['y'])*self.scale+self.offset_y)

    def fit(self):
        xs = [float(n['x']) for n in self.nodes.values()]; ys = [float(n['y']) for n in self.nodes.values()]
        w = max(self.canvas.winfo_width(), 200); h = max(self.canvas.winfo_height(), 200)
        dx = max(xs)-min(xs); dy = max(ys)-min(ys)
        self.scale = min((w-100)/max(dx, 1e-9), (h-100)/max(dy, 1e-9))
        if not math.isfinite(self.scale) or self.scale <= 0: self.scale = 1
        self.offset_x = w/2 - (min(xs)+max(xs))/2*self.scale
        self.offset_y = h/2 + (min(ys)+max(ys))/2*self.scale
        self.draw()

    def draw(self):
        c = self.canvas; c.delete('all')
        for b in self.model['branches']:
            a = self.xy(self.nodes[b['from_node']]); z = self.xy(self.nodes[b['to_node']]); selected = b['id'] in self.selected
            c.create_line(*a, *z, fill=self.colors[b['feeder']], width=5 if selected else 2)
            if b['existing_switch']:
                x, y = z; c.create_rectangle(x-5,y-5,x+5,y+5,fill='#545b64',outline='white')
            if selected:
                # Marker uses downstream endpoint chosen by the topology engine.
                p = next((p for p in (self.result or {}).get('proposals', []) if p['branch'] == b['id']), None)
                point = self.xy(self.nodes[p['to_node']]) if p else z
                x,y = point; c.create_oval(x-7,y-7,x+7,y+7,fill='#e53e3e',outline='white',width=2)
        for tie in self.model['ties']:
            a = self.xy(self.nodes[tie['node_a']]); b = self.xy(self.nodes[tie['node_b']])
            c.create_line(*a, *b, fill='#777', width=2, dash=(5,4))
            x=(a[0]+b[0])/2; y=(a[1]+b[1])/2
            c.create_text(x,y-8,text=str(tie['id']),fill='#555')
        for n in self.nodes.values():
            x,y = self.xy(n); c.create_oval(x-2,y-2,x+2,y+2,fill=self.colors[n['feeder']],outline='')
        text = ' | '.join(f"{name}: {color}" for name,color in self.colors.items())
        c.create_text(10,10,anchor='nw',text=f"CRS: {self.model['crs']}  |  {text}  |  قرمز: پیشنهادی  |  خاکستری: کلید موجود", fill='#22334a')

    def closest(self, x, y):
        best = None
        for b in self.model['branches']:
            if not b['candidate'] or b['existing_switch']: continue
            a=self.xy(self.nodes[b['from_node']]); z=self.xy(self.nodes[b['to_node']])
            dist=segment_distance(x,y,*a,*z)
            if dist <= 12 and (best is None or dist < best[0]): best = (dist,b)
        return best[1] if best else None

    def toggle(self, event):
        b = self.closest(event.x,event.y)
        if not b: return
        bid = b['id']; selected = set(self.selected)
        if bid in selected: selected.remove(bid)
        else: selected.add(bid)
        try: result = evaluate(self.model, sorted(selected))
        except Exception as exc: messagebox.showerror('خطا', str(exc), parent=self.win); return
        self.selected = selected; self.set_result(result)

    def hover(self, event):
        b = self.closest(event.x,event.y)
        if b: self.status.set(f"شاخه {b['id']}، فیدر {b['feeder']}، از {b['from_node']} تا {b['to_node']}؛ کلیک برای تغییر محل")

    def pan_start(self, event): self._last = (event.x,event.y)
    def pan(self, event):
        self.offset_x += event.x-self._last[0]; self.offset_y += event.y-self._last[1]
        self._last = (event.x,event.y); self.draw()
    def wheel(self, event): self.zoom(event.x,event.y, 1.2 if event.delta > 0 else 1/1.2)
    def zoom(self, x, y, factor):
        scale = max(1e-9, min(1e9, self.scale * factor))
        factor = scale / self.scale; self.scale = scale
        self.offset_x = x + factor*(self.offset_x-x); self.offset_y = y + factor*(self.offset_y-y); self.draw()

    def set_result(self, result):
        self.result = result; self.selected = set(result['selected']); self.draw()
        self.status.set(f"کلید جدید: {len(self.selected)} | ENS اکتشافی: {result['ens_kwh_per_year']:.2f} kWh/سال | قیود الکتریکی و مانور تأیید نشده‌اند")
        if self.on_result: self.on_result(result)

    def run_manual(self):
        try: self.set_result(evaluate(self.model, sorted(self.selected)))
        except Exception as exc: messagebox.showerror('خطا',str(exc),parent=self.win)

    def run_optimization(self):
        try:
            self.status.set('در حال محاسبه؛ لطفاً صبر کنید...'); self.win.update_idletasks()
            self.set_result(optimize(self.model, self.count, limit=1000))
            messagebox.showwarning('محدودیت', '\n'.join(self.result['warnings']), parent=self.win)
        except Exception as exc: messagebox.showerror('خطا',str(exc),parent=self.win)

    def save(self):
        if self.result is None: messagebox.showerror('خطا','ابتدا محاسبه را اجرا کنید',parent=self.win); return
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
        if not path: return
        try:
            if Path(path).resolve() in self.protected | {self.source_path}: raise ValueError('مسیر خروجی با فایل ورودی یا پروژه یکسان است')
            export_result(path,self.result,self.model['crs'])
        except Exception as exc: messagebox.showerror('خطا',str(exc),parent=self.win)
