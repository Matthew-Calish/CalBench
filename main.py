import classes as cl


import threading
import queue
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import classes as cl

def run_sim_in_thread(params, out_q):
    try:
        sim = cl.Simulator(params['num_nodes'], params['bandwidth_mbps'], params['total_data_bytes'])
        results = sim.run()
        out_q.put(('done', results))
    except Exception as e:
        out_q.put(('error', str(e)))

def start_sim(button, entries, out_q):
    try:
        num_nodes = int(entries['num_nodes'].get())
        bandwidth_mbps = float(entries['bandwidth_mbps'].get())
        total_data_bytes = float(entries['total_data_bytes'].get())
    except ValueError:

        return

    params = {
        'num_nodes': num_nodes,
        'bandwidth_mbps': bandwidth_mbps,
        'total_data_bytes': total_data_bytes
    }
    button.config(state=DISABLED)

    t = threading.Thread(target=run_sim_in_thread, args=(params, out_q), daemon=True)
    t.start()

def poll_queue(root, out_q, button, results_frame):
    try:
        while True:
            msg = out_q.get_nowait()
            typ, payload = msg
            if typ == 'done':
                button.config(state=NORMAL)

                # wyświetl wyniki
                for widget in results_frame.winfo_children():
                    widget.destroy()
                row = 0
                for k, v in payload.items():
                    ttkb.Label(results_frame, text=f"{k}:", bootstyle="inverse-dark").grid(row=row, column=0, sticky='w', padx=6, pady=2)
                    ttkb.Label(results_frame, text=str(v), bootstyle="secondary").grid(row=row, column=1, sticky='w', padx=6, pady=2)
                    row += 1
            elif typ == 'error':
                button.config(state=NORMAL)

    except queue.Empty:
        pass
    root.after(200, poll_queue, root, out_q, button, results_frame)

def main():
    root = ttkb.Window(themename= "vapor")  # ciemny motyw
    root.title("CalBench")
    root.geometry("400x300")
    root.minsize(500, 300)
    root.iconbitmap(None)

    # tło ciemno-fioletowe
    dark_purple = "#F9F5FD"
    root.configure(bg=dark_purple)

    frm = ttkb.Frame(root, padding=12)
    frm.pack(fill=BOTH, expand=YES)

    left = ttkb.Frame(frm)
    left.pack(side=LEFT, fill=Y, padx=8, pady=8)

    entries = {}
    ttkb.Label(left, text="Ilość wę", bootstyle="inverse-dark").pack(anchor='w')
    entries['num_nodes'] = ttkb.Entry(left)
    entries['num_nodes'].pack(fill=X, pady=4)
    entries['num_nodes'].insert(0, "50")

    ttkb.Label(left, text="bandwidth_mbps", bootstyle="inverse-dark").pack(anchor='w')
    entries['bandwidth_mbps'] = ttkb.Entry(left)
    entries['bandwidth_mbps'].pack(fill=X, pady=4)
    entries['bandwidth_mbps'].insert(0, "50")

    ttkb.Label(left, text="total_data_bytes (per node)", bootstyle="inverse-dark").pack(anchor='w')
    entries['total_data_bytes'] = ttkb.Entry(left)
    entries['total_data_bytes'].pack(fill=X, pady=4)
    entries['total_data_bytes'].insert(0, "100000.0")

    out_q = queue.Queue()
    results_frame = ttkb.Frame(frm)
    results_frame.pack(side=TOP, fill=X, padx=8, pady=8)

    start_btn = ttkb.Button(left, text="Start", command=lambda: start_sim(start_btn, entries, out_q), bootstyle="success")
    start_btn.pack(fill=X, pady=(8,2))

    # poll queue
    root.after(200, poll_queue, root, out_q, start_btn, results_frame)

    root.mainloop()

if __name__ == "__main__":
    main()


