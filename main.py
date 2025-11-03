import threading
import queue
import time
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import simulation as simul
import tkinter.font as tkfont
import logging
from logging.handlers import RotatingFileHandler
import sys

logger = logging.getLogger("calbench")
logger.setLevel(logging.DEBUG)

# plik logów z rotacją (max 5 MB, 3 pliki)
fh = RotatingFileHandler("calbench.log", maxBytes=32*1024*1024, backupCount=3, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s   %(message)s"))

logger.addHandler(fh)

def run_sim_in_thread(params, out_q):
    try:
        sim = simul.Simulator(params['max_sim_time'], params['num_nodes'], params['bandwidth_mbps'], params['total_load_per_sec_Mb'], logger)
        stop_flag = threading.Event()

        def progress_poller():
            try:
                while not stop_flag.is_set():
                    out_q.put(('progress', None, sim.stats.total_bytes_received / 1e6))
                    time.sleep(0.5)
            except Exception:
                pass

        p = threading.Thread(target=progress_poller, daemon=True)
        p.start()

        results = sim.run()

        # wysyłamy finalny update, zatrzymujemy poller i zwracamy wynik
        out_q.put(('progress', None, sim.stats.total_bytes_received / 1e6))
        stop_flag.set()
        out_q.put(('done', results, sim.stats.total_bytes_received / 1e6))
        
    except Exception as e:
        out_q.put(('error', str(e), str(e)))



def start_sim(button, entries, out_q, meter):
    try:
        max_sim_time = int(entries['max_sim_time'].get())
        num_nodes = int(entries['num_nodes'].get())
        bandwidth_mbps = float(entries['bandwidth_mbps'].get())
        total_load_per_sec_Mb = float(entries['total_load_per_sec_Mb'].get())
        perfect_load_MB = total_load_per_sec_Mb * max_sim_time / 8.0
    except ValueError:
        return

    params = {
        'max_sim_time': max_sim_time,
        'num_nodes': num_nodes,
        'bandwidth_mbps': bandwidth_mbps,
        'total_load_per_sec_Mb': total_load_per_sec_Mb
    }

    meter.configure(amounttotal=perfect_load_MB, amountused=0, stepsize=total_load_per_sec_Mb * 0.1)
    button.config(state=DISABLED)

    t = threading.Thread(target=run_sim_in_thread, args=(params, out_q), daemon=True)
    t.start()



def poll_queue(root, out_q, button, results_frame, meter):
    try:
        while True:
            msg = out_q.get_nowait()
            typ, payload, total_mega_bytes = msg
            if typ == 'done':
                button.config(state=NORMAL)
                for widget in results_frame.winfo_children():
                    widget.destroy()
                row = 0
                for k, v in payload.items():
                    ttkb.Label(results_frame, text=f"{k}").grid(row=row, column=0, sticky='w', padx=6, pady=2)
                    ttkb.Label(results_frame, text=str(v), bootstyle="secondary").grid(row=row, column=1, sticky='w', padx=6, pady=2)
                    row += 1



            elif typ == 'error':
                button.config(state=NORMAL)
            elif typ == 'progress':
                try:

                    meter.configure(amountused=round(total_mega_bytes, 3))

                except Exception:
                    pass

    except queue.Empty:
        pass
    root.after(100, poll_queue, root, out_q, button, results_frame, meter)




def main():
    root = ttkb.Window(themename="vapor")
    root.title("CalBench")

    
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = int(sw * 0.22)
    h = int(sh * 0.3)
    #w = max(800, min(w, sw))   # minimalna szerokość 800px
    #h = max(600, min(h, sh))   # minimalna wysokość 600px
    root.geometry(f"{w}x{h}")
    root.resizable(False, False)


    try:
        dpi = root.winfo_fpixels('1i')    # px per inch
        scaling = dpi / 76.0
        root.tk.call('tk', 'scaling', scaling)
    except Exception:
        pass

    # użyj grid jako layoutu głównego aby elementy mogły skalować się proporcjonalnie
    frm = ttkb.Frame(root, padding=12)
    frm.grid(sticky='nsew')
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # lewy panel (kontrolki) i prawy panel (wyniki + meter)
    left = ttkb.Frame(frm)
    left.grid(row=0, column=0, sticky='nsw', padx=8, pady=8)

    right = ttkb.Frame(frm)
    right.grid(row=0, column=1, sticky='nsew', padx=8, pady=8)

    frm.columnconfigure(1, weight=1)   # prawy panel rośnie wraz z oknem
    frm.rowconfigure(0, weight=1)

    entries = {}

    ttkb.Label(left, text="Czas przesyłu danych [s]").pack(anchor='w', pady=(4,0))
    entries['max_sim_time'] = ttkb.Entry(left)
    entries['max_sim_time'].pack(fill=X, pady=4)
    entries['max_sim_time'].insert(0, "60")

    ttkb.Label(left, text="Ilość węzłów").pack(anchor='w', pady=(4,0))
    entries['num_nodes'] = ttkb.Entry(left)
    entries['num_nodes'].pack(fill=X, pady=4)
    entries['num_nodes'].insert(0, "10")

    ttkb.Label(left, text="Przepustowość sieci [Mb/s]").pack(anchor='w', pady=(4,0))
    entries['bandwidth_mbps'] = ttkb.Entry(left)
    entries['bandwidth_mbps'].pack(fill=X, pady=4)
    entries['bandwidth_mbps'].insert(0, "100")

    ttkb.Label(left, text="Obciążenie sieci [Mb/s]").pack(anchor='w', pady=(4,0))
    entries['total_load_per_sec_Mb'] = ttkb.Entry(left)
    entries['total_load_per_sec_Mb'].pack(fill=X, pady=4)
    entries['total_load_per_sec_Mb'].insert(0, "30")

    out_q = queue.Queue()
    # ramka wyników umieszczona w prawym panelu — zawsze widoczna i rozciąga się
    results_frame = ttkb.Frame(right)
    results_frame.pack(side=TOP, fill=BOTH, expand=YES, padx=18, pady=8)

    # tytuł/placeholder wyników (zostanie nadpisany po zakończeniu symulacji)
    ttkb.Label(results_frame, text="Czas przesyłu danych [s]:").grid(row=0, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=0, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Przepustowość [Mb/s]:").grid(row=1, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=1, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Średnie opuźnienia [ms]:").grid(row=2, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=2, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Kolizje:").grid(row=3, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=3, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Porzucone ramki:").grid(row=4, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=4, column=1, sticky='w', padx=6, pady=2)


    meter = ttkb.Meter(
        right, 
        metersize=150,
        textfont=tkfont.Font(size=14, weight="bold"),
        subtextfont=tkfont.Font(size=8), 
        amountused=0, 
        amounttotal=1,
        stepsize=0.001,
        metertype='full', 
        subtext='Wysłane dane [MB]', 
        bootstyle='light')
    
    meter.pack(side=TOP, padx=(0,20), pady=(0,6))


    start_btn = ttkb.Button(left, text="Start", command=lambda: start_sim(start_btn, entries, out_q, meter), bootstyle="secondary")
    start_btn.pack(fill= X, pady=12)

    root.after(100, poll_queue, root, out_q, start_btn, results_frame, meter)
    root.mainloop()

if __name__ == "__main__":
    main()


