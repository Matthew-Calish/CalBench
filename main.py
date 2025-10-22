import threading
import queue
import time
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import simulation as simul
import tkinter.font as tkfont

def run_sim_in_thread(params, out_q):
    try:
        sim = simul.Simulator(params['num_nodes'], params['bandwidth_mbps'], params['total_data_mega_bytes'])
        stop_flag = threading.Event()

        def progress_poller():
            try:
                while not stop_flag.is_set():
                    out_q.put(('progress', sim.stats.total_bytes_received / 1e6))
                    time.sleep(0.1)
            except Exception:
                pass

        p = threading.Thread(target=progress_poller, daemon=True)
        p.start()

        results = sim.run()
        # wysyłamy finalny update, zatrzymujemy poller i zwracamy wynik
        out_q.put(('progress', sim.stats.total_bytes_received / 1e6))
        stop_flag.set()
        out_q.put(('done', results))
    except Exception as e:
        out_q.put(('error', str(e)))



def start_sim(button, entries, out_q, meter):
    try:
        num_nodes = int(entries['num_nodes'].get())
        bandwidth_mbps = float(entries['bandwidth_mbps'].get())
        total_data_mega_bytes = float(entries['total_data_mega_bytes'].get())
    except ValueError:
        return

    params = {
        'num_nodes': num_nodes,
        'bandwidth_mbps': bandwidth_mbps,
        'total_data_mega_bytes': total_data_mega_bytes
    }

    meter.configure(amounttotal=total_data_mega_bytes, amountused=0)
    button.config(state=DISABLED)

    t = threading.Thread(target=run_sim_in_thread, args=(params, out_q), daemon=True)
    t.start()



def poll_queue(root, out_q, button, results_frame, meter):
    try:
        while True:
            msg = out_q.get_nowait()
            typ, payload = msg
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
                    # payload = total_bytes_received
                    meter.configure(amountused=payload)
                except Exception:
                    pass

    except queue.Empty:
        pass
    root.after(100, poll_queue, root, out_q, button, results_frame, meter)




def main():
    root = ttkb.Window(themename="vapor")
    root.title("CalBench")
    root.geometry("500x350")
    root.resizable(False, False)

    frm = ttkb.Frame(root, padding=12)
    frm.pack(fill=BOTH, expand=YES)

    left = ttkb.Frame(frm)
    left.pack(side=LEFT, fill=Y, padx=8, pady=8)

    # prawy panel na meter i wyniki — rozciąga się, by wyniki były zawsze widoczne
    right = ttkb.Frame(frm)
    right.pack(side=RIGHT, fill=BOTH, expand=YES, padx=8, pady=8)

    entries = {}
    ttkb.Label(left, text="Ilość węzłów").pack(anchor='w', pady=(4,0))
    entries['num_nodes'] = ttkb.Entry(left)
    entries['num_nodes'].pack(fill=X, pady=4)
    entries['num_nodes'].insert(0, "5")

    ttkb.Label(left, text="Przepustowość [mbps]").pack(anchor='w', pady=(4,0))
    entries['bandwidth_mbps'] = ttkb.Entry(left)
    entries['bandwidth_mbps'].pack(fill=X, pady=4)
    entries['bandwidth_mbps'].insert(0, "50")

    ttkb.Label(left, text="Ilość wysłanych danych [MB]").pack(anchor='w', pady=(4,0))
    entries['total_data_mega_bytes'] = ttkb.Entry(left)
    entries['total_data_mega_bytes'].pack(fill=X, pady=4)
    entries['total_data_mega_bytes'].insert(0, "15")

    out_q = queue.Queue()
    # ramka wyników umieszczona w prawym panelu — zawsze widoczna i rozciąga się
    results_frame = ttkb.Frame(right)
    results_frame.pack(side=TOP, fill=BOTH, expand=YES, padx=18, pady=8)

    # tytuł/placeholder wyników (zostanie nadpisany po zakończeniu symulacji)
    ttkb.Label(results_frame, text="Czas przesyłu danych [s]:").grid(row=0, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=0, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Przepustowość [Mb/s]:").grid(row=1, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=1, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Średnie opuźnienia [s]:").grid(row=2, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=2, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Kolizje:").grid(row=3, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=3, column=1, sticky='w', padx=6, pady=2)

    ttkb.Label(results_frame, text="Porzucone pakiety:").grid(row=4, column=0, sticky='w', padx=6, pady=2)
    ttkb.Label(results_frame, text="Brak", bootstyle="secondary").grid(row=4, column=1, sticky='w', padx=6, pady=2)


    meter = ttkb.Meter(
        right, 
        metersize=150,
        textfont=tkfont.Font(size=14, weight="bold"),
        subtextfont=tkfont.Font(size=8), 
        amountused=0, 
        amounttotal=1, 
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


