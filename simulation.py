import random
import numpy as np
import matplotlib.pyplot as plt
import logging
from logging.handlers import RotatingFileHandler
# -------------------------------
# 1. Frame
# -------------------------------
class Frame:
    def __init__(self, fid, size_bytes, gen_time):
        self.fid = fid
        self.size_bytes = size_bytes
        self.generation_time = gen_time
        self.first_attempt_time = None
        self.received_time = None
        self.retries = 0


# -------------------------------
# 2. Stats
# -------------------------------
class Stats:
    def __init__(self):
        self.total_bytes_transmitted = 0
        self.total_bytes_received = 0
        self.frame_count_received = 0
        self.collision_events = 0
        self.latencies = []
        self.frames_dropped = 0
        self.total_retries = 0
        self.perfect_load_bytes = 0

    def set_perfect_load_bytes(self, perfect_load_bytes):
        self.perfect_load_bytes = perfect_load_bytes

    def record_received(self, frame):

        self.frame_count_received += 1
        self.total_bytes_received += frame.size_bytes

        self.latencies.append(frame.received_time - frame.first_attempt_time)



    def record_collision(self):
        self.collision_events += 1

    def record_retry(self):
        self.total_retries += 1

    def record_drop(self):
        self.frames_dropped += 1

    def summary(self, total_time_s):

        throughput_mbps = (self.total_bytes_received * 8) / (total_time_s * 1e6)
        
        avg_latency = np.mean(self.latencies) if self.latencies else 0
        avg_latancy_ms = avg_latency * 1000

        print(f"\n\nIlość odbranych ramek: {self.frame_count_received}")
        print(f"Ilość odbranych mega bajtów: {self.total_bytes_received/1e6} MB")
        print(f"Maksymalna ilosc odebranych mega bajtów {self.perfect_load_bytes/1e6}")

        return {
            "Czas przesyłu danych [s]:": round(total_time_s, 3),
            "Realna przepustowość [Mb/s]:": round(throughput_mbps, 3),
            "Procent przesłanych danych [%]:": str(round((self.total_bytes_received / self.perfect_load_bytes) * 100, 2)) + " %",
            "Liczba kolizji:": self.collision_events,
            "Liczba porzuconych ramek:": self.frames_dropped,
        }


# -------------------------------
# 3. Medium
# -------------------------------
class Medium:

    def __init__(self, bandwidth_mbps):
        self.bandwidth_bps = bandwidth_mbps * 1e6
        self.active_transmissions = []   # lista tuple (node, end_time)
        self.busy_until = 0.0

    def is_free(self, current_time):
        EPS = 1e-12
        return current_time > self.busy_until - EPS

    def start_transmission(self, current_time, frame_size_bytes, node=None):

        if not self.is_free(current_time):
            raise RuntimeError("Medium occupied – simultaneous transmission detected.")

        transmission_time = (frame_size_bytes * 8) / self.bandwidth_bps

        end_time = current_time + transmission_time
        # dodajemy aktywną transmisję i aktualizujemy busy_until na najdalszy koniec
        self.active_transmissions.append((node, end_time))
        self.busy_until = max(self.busy_until, end_time)

        return transmission_time

    
    def end_transmission(self, node, end_time):

        # usuń dopasowane wpisy (porównanie czasu z epsilonem)
        EPS = 1e-9
        self.active_transmissions = [
            (n, t) for (n, t) in self.active_transmissions
            if not (n is node and abs(t - end_time) < EPS)
        ]
        if self.active_transmissions:
            self.busy_until = max(t for (_, t) in self.active_transmissions)
        else:
            self.busy_until = 0.0



# -------------------------------
# 4. Node
# -------------------------------
class Node:

    def __init__(self, node_id, simulator):

        self.id = node_id
        self.sim = simulator
        self.state = "idle"
        self.retries = 0
        self.wasDrop = False 
        self.backOff = 0
        self.queue = []
        self.frame_length = 1500

    def generate_frame_now(self, current_time):

        fid = len(self.sim.generated_frames) + 1
        frame = Frame(fid, self.frame_length, current_time)

        self.queue.append(frame)
        self.sim.generated_frames.append(frame)
        self.sim.active_frames.append(frame)

    def handle_retry(self):

        self.retries += 1

        if self.retries > 15:

            self.sim.active_frames.remove(self.queue[0])
            self.queue.remove(self.queue[0])
            self.retries = 0
            self.sim.stats.record_drop()
            self.wasDrop = True

            return



    def handle_collision(self):
        if self.retries > 15:
            self.sim.active_frames.remove(self.queue[0])
            self.queue.remove(self.queue[0])
            self.retries = 0
            self.backOff = 0
            self.sim.stats.record_drop()
            self.wasDrop = True

            return

        self.retries += 1
        k = min(self.retries, 10)

        self.sim.stats.record_retry()

        raw = random.randint(0, 2**k - 1)
        delay_slots = raw if raw > 0 else 1
        self.backOff = self.sim.time + delay_slots * self.sim.slot_time

# -------------------------------
# 5. Event
# -------------------------------
class Event:
    def __init__(self, time, type, node):

        self.time = time
        self.type = type
        self.node = node
        self.frame = None



# -------------------------------
# 5. Simulator
# -------------------------------
class Simulator:

    def __init__(self, max_sim_time, num_nodes, bandwidth_mbps, total_load_per_sec, logger):

        print(f"Initializing simulator with {num_nodes} nodes, {bandwidth_mbps} Mb/s bandwidth, "
              f"{total_load_per_sec} Mb/s total load, max sim time {max_sim_time} s.")

        self.max_sim_time = max_sim_time
        self.time = 0
        self.slot_time = 512 / (bandwidth_mbps * 1e6)
        self.inter_frame_gap = 96 / (bandwidth_mbps * 1e6)

        self.num_nodes = num_nodes
        self.nodes = [Node(i, self) for i in range(num_nodes)]
        self.medium = Medium(bandwidth_mbps)
        self.stats = Stats()

        self.generated_frames = []
        self.active_frames = []
        self.frame_size_bytes = 1500

        self.total_load_bps = total_load_per_sec * 1e6
        self.perfect_total_bytes = int((self.total_load_bps * self.max_sim_time) / 8)
        self.stats.set_perfect_load_bytes(self.perfect_total_bytes)

        self.frames_per_sec_total = self.total_load_bps / (self.frame_size_bytes * 8)
        self.frames_per_sec_per_node = self.frames_per_sec_total / self.num_nodes
        self.interarrival_det = 1.0 / self.frames_per_sec_per_node if self.frames_per_sec_per_node > 0 else float('inf')

        self.events = []  

        self.debug_help = 0
        self.debug_set = set()

        self.logger = logger


    def handle_event_2(self, events):
        gen_events = [e for e in events if e.type == "generate_frame"]
        end_events = [e for e in events if e.type == "end_transmission"]
        try_events = [e for e in events if e.type == "try_transmission"]
        start_events = [e for e in events if e.type == "start_transmission"]

        # -------------------------------
        # 1. Zakończ transmisje
        # -------------------------------
        for ev in end_events:

            self.logger.debug(f"Węzeł {ev.node.id} kończy nadawać o czasie {ev.time}")

            node = ev.node
            pkt = getattr(ev, "frame", None)
            if pkt and pkt in node.queue:
                pkt.received_time = self.time
                self.stats.record_received(pkt)
                node.queue.remove(pkt)
            node.retries = 0
            self.medium.end_transmission(node, ev.time)
            if node.queue:
                self.events.append(Event(self.time + self.inter_frame_gap, "try_transmission", node))





        # -------------------------------
        # 2. Generuj nowe ramki
        # -------------------------------
        for ev in gen_events:

            self.logger.debug(f"Węzeł {ev.node.id} generuje ramkę o czasie {ev.time}")

            node = ev.node
            if ev.time <= self.max_sim_time:

                node.generate_frame_now(ev.time)

                if len(node.queue) == 1:

                    self.events.append(Event(self.time, "try_transmission", node))
                    
                if self.frames_per_sec_per_node > 0:
                    interarrival_time = random.expovariate(self.frames_per_sec_per_node)
                    next_time = ev.time + interarrival_time
                    self.events.append(Event(next_time, "generate_frame", node))






        # -------------------------------
        # 3. Obsłuż próby transmisji
        # -------------------------------
        active_nodes = [e.node for e in try_events + start_events if e.node.queue]

        if not active_nodes:
            return  

        # Jeśli więcej niż jeden węzeł próbuje naraz -> kolizja
        if len(active_nodes) > 1 and self.medium.is_free(self.time):
            self.stats.record_collision()

            self.logger.debug(f"Kolizja! O czasie {self.time} między węzłami {[node.id for node in active_nodes]}")

            for node in active_nodes:
                if node.queue[0].first_attempt_time is None:
                    node.queue[0].first_attempt_time = self.time
                node.handle_collision()
                if node.queue:
                    self.events.append(Event(node.backOff, "try_transmission", node))
            return

        # pojedynczy węzeł
        if len(active_nodes) == 1:
            n = active_nodes[0]
            f = n.queue[0]
            if f.first_attempt_time is None:
                f.first_attempt_time = self.time
            if self.medium.is_free(self.time):
                # start
                duration = self.medium.start_transmission(self.time, f.size_bytes, n)
                end_ev = Event(self.time + duration, "end_transmission", n)
                end_ev.frame = f
                self.events.append(end_ev)
            else:
                # kanał zajęty – NIE backoff jak przy kolizji; 1‑persistent: czekaj aż wolny + IFG
                sense_t = max(self.medium.busy_until, self.time + self.slot_time) + self.inter_frame_gap
                n.handle_retry()

                if(n.wasDrop == False):

                    self.events.append(Event(sense_t, "try_transmission", n))
                    self.logger.debug(f"Węzeł {n.id} kanał zajęty o {self.time}, planuje ponowne czucie o {sense_t}")
                else:

                    n.wasDrop = False

        # start_events (jeśli zostały z wcześniejszego stylu) – przekieruj w tę samą logikę
        for ev in start_events:
            # Konwersja do try jeśli medium wolne
            if ev.node.queue and self.medium.is_free(self.time):
                n = ev.node
                f = n.queue[0]
                if f.first_attempt_time is None:
                    f.first_attempt_time = self.time
                duration = self.medium.start_transmission(self.time, f.size_bytes, n)
                end_ev = Event(self.time + duration, "end_transmission", n)
                end_ev.frame = f
                self.events.append(end_ev)

    def run(self):

        print("\nRozpoczynanie symulacji...\n")
        self.logger.debug("Rozpoczynanie symulacji.")

        for n in self.nodes:
            if self.frames_per_sec_per_node > 0:
                offset = random.expovariate(self.frames_per_sec_per_node)
            else:
                offset = 0.0
            self.events.append(Event(offset, "generate_frame", n))

        while self.events and self.time <= self.max_sim_time:
            self.events.sort(key=lambda e: e.time)
            current_t = self.events[0].time
            if current_t > self.max_sim_time:
                break
            self.time = current_t
            epsilon = 1e-9
            batch = [e for e in self.events if abs(e.time - self.time) < epsilon]
            self.events = [e for e in self.events if e not in batch]
            self.handle_event_2(batch)

        self.logger.debug("Symulacja zakończona.")

        return self.stats.summary(self.time)
    

# logger = logging.getLogger("calbench")
# logger.setLevel(logging.DEBUG)

# fh = RotatingFileHandler("calbench.log", maxBytes=32*1024*1024, backupCount=3, encoding="utf-8")
# fh.setLevel(logging.DEBUG)
# fh.setFormatter(logging.Formatter("%(asctime)s   %(message)s"))

# logger.addHandler(fh)

# cos = Simulator(60, 30, 100, 90, logger)
# cos.run()