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
            "Przepustowość [Mb/s]:": round(throughput_mbps, 3),
            "Średnie opuźnienia [ms]:": round(avg_latancy_ms, 3),
            "Kolizje:": self.collision_events,
            "Porzucone ramki:": self.frames_dropped,
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
        return current_time >= self.busy_until

    def start_transmission(self, current_time, frame_size_bytes, node=None):

        transmission_time = (frame_size_bytes * 8) / self.bandwidth_bps

        end_time = current_time + transmission_time
        # dodajemy aktywną transmisję i aktualizujemy busy_until na najdalszy koniec
        self.active_transmissions.append((node, end_time))
        self.busy_until = max(self.busy_until, end_time)

        return transmission_time

    
    def end_transmission(self, node, end_time):
        """
        Usuń konkretną transmisję node o oczekiwanym end_time.
        Jeśli po usunięciu nie ma aktywnych transmisji -> busy_until = 0,
        w przeciwnym razie busy_until = max(pozostałe end_time).
        """
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


    def handle_collision(self):

        if self.retries > 15:

            #print(f"\nNode {self.id}: frame {self.queue[0].fid} dropped after 16 retries.\n")

            # ramka uznany za utracony
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
        #idk czy randint od 0 do 2^k -1 czy od 1 do 2^k -1
        delay_slots = random.randint(0, 2**k - 1)
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

    def handle_event(self, events):

        try_events = [e for e in events if e.type == "try_transmission"]
        start_event = [e for e in events if e.type == "start_transmission"]
        end_event = [e for e in events if e.type == "end_transmission"]
        generate_events = [e for e in events if e.type == "generate_frame"]
        transmission_events = try_events + start_event + end_event

        # obsłuż generacje ramek (może być wiele równocześnie)
        for ge in generate_events:
            node = ge.node
            
            self.logger.debug(f"Węzeł {node.id} generuje ramkę o czasie {ge.time}")
            #self.logger.debug(f"Rozmiar eventów w kolejce dla noda {node.id} przed generacją: {len(ge.node.queue)}")
            # generuj ramkę tylko jeśli nie przekroczyliśmy max_sim_time
            if ge.time <= self.max_sim_time:
                node.generate_frame_now(ge.time)  # użyj ge.time zamiast self.time

                #if not any(e for e in self.events if e.node == node and e.type == "try_transmission"):
                    #new_ev = Event(time=ge.time, type="try_transmission", node=node)
                    #self.events.append(new_ev)

                if len(node.queue) == 1:
                    new_ev = Event(time=ge.time, type="try_transmission", node=node)
                    self.events.append(new_ev)

                initial_offset = random.random() * self.interarrival_det if self.interarrival_det != float('inf') else 0.0
                next_time = ge.time + initial_offset
                
                self.logger.debug(f"Następna generacja ramki dla węzła {node.id} będzie o czasie {next_time}")
                self.events.append(Event(time=next_time, type="generate_frame", node=node))

        

        if len(try_events) > 1 and not start_event and not end_event:


            # -------------------------------
            # Więcej niż jeden węzeł próbuje nadać w tym samym czasie
            # -------------------------------
            
            #print(f"Wiele węzłów próbuje nadać o czasie (kolizja) {self.time}: {[event.node.id for event in try_events]}")

            if self.medium.is_free(self.time): 

                self.logger.debug(f"Kolizja! O czasie {self.time} między węzłami {[event.node.id for event in try_events]}")

                # kolizja
                self.stats.record_collision()
                for event in try_events:

                    if event.node.queue and event.node.queue[0].first_attempt_time is None:
                        event.node.queue[0].first_attempt_time = self.time
                    
                    event.node.handle_collision()

                    if event.node.wasDrop:

                        #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")

                        
                        if event.node.queue:

                            self.debug_set.add(event.node.queue[0].fid)
                            new_event = Event(time= self.time + self.slot_time, type="try_transmission", node=event.node)
                            self.events.append(new_event)

                            event.node.wasDrop = False
                    
                    else:

                        #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")
                        #self.debug_set.add(event.node.queue[0].fid)
                        if event.node.queue:

                            new_event = Event(time= event.node.backOff, type="try_transmission", node=event.node)
                            self.events.append(new_event)

            else:

                #medium zajęte, ponów próbę po czasie slot_time
                #print(f"Medium zajęte o czasie {self.time}, ponawianie prób węzłów {[event.node.id for event in try_events]}")
                #self.logger.debug(f"Medium zajęte o czasie {self.time}, ponawianie prób węzłów {[event.node.id for event in try_events]}")
                ##self.logger.debug(f"Rozmiar eventów w kolejce: {len(self.events)}")


                for event in try_events:

                    if event.node.queue:

                        if event.node.queue[0].first_attempt_time is None:
                            event.node.queue[0].first_attempt_time = self.time

                        self.debug_set.add(event.node.queue[0].fid)
                        new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=event.node)

                        self.events.append(new_event)



        elif len(transmission_events) == 1:

            
            ##self.logger.debug(f"Jeden event o czasie {self.time} dla węzła {events[0].node.id}, pozostało ramek do wysłania: {len(events[0].node.queue)}")
            ##self.logger.debug(f"Rozmiar eventów w kolejce na początku: {len(self.events)}")
            event = transmission_events[0]

            if event.type == "try_transmission":


                # -------------------------------
                # Jeden węzeł próbuje nadawać
                # -------------------------------

                #print(f"Node {event.node.id} próbuje nadać o czasie {self.time}")

                #self.logger.debug(f"Węzeł {event.node.id} próbuje nadawać o czasie {self.time}")

                if event.node.queue and event.node.queue[0].first_attempt_time is None:
                    event.node.queue[0].first_attempt_time = self.time
                
                if self.medium.is_free(self.time):

                    self.debug_help += 1

                    #print(f"Ilość eventów start transmisison: {self.debug_help} / {len(self.generated_frames)}", end='\r')

                    #print(f"Node {event.node.id} medium wolne o czasie {self.time}, rozpoczyna nadawanie.")
                    if event.node.queue:

                        #new_event = Event(time=self.time, type="start_transmission", node=event.node)
                        new_event = Event(time=self.time, type="start_transmission", node=event.node)
                        new_event.frame = event.node.queue[0]
                        
                        self.events.append(new_event)
                        self.events.sort(key=lambda e: e.time)

                else:


                    #print(f"Node {event.node.id} medium zajęte o czasie {self.time}, ponawia próbę.")
                    #self.logger.debug(f"Węzeł {event.node.id} medium zajęte o czasie {self.time}, ponawia próbę.")
                    # medium zajęte, ponów próbę po czasie slot_time
                    if event.node.queue:
                        self.debug_set.add(event.node.queue[0].fid)
                        new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=event.node)

                        self.events.append(new_event)



            elif event.type == "start_transmission":

                # -------------------------------
                # Jeden węzeł zaczyna nadawać
                # -------------------------------

                #print(f"Node {event.node.id} zaczyna nadawać o czasie {self.time}")

                if not self.medium.is_free(self.time):

                    self.logger.debug(f"Kolizja! Węzeł {event.node.id} napotkał kolizję przy starcie nadawania o czasie {self.time}")

                    self.stats.record_collision()
                    event.node.handle_collision()

                    if event.node.wasDrop:

                        #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")

                        
                        if event.node.queue:

                            self.debug_set.add(event.node.queue[0].fid)
                            new_event = Event(time= self.time + self.slot_time, type="try_transmission", node=event.node)
                            self.events.append(new_event)

                            event.node.wasDrop = False
                    
                    else:

                        #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")
                        self.debug_set.add(event.node.queue[0].fid)
                        if event.node.queue:

                            new_event = Event(time= event.node.backOff, type="try_transmission", node=event.node)
                            self.events.append(new_event)
                    

                else:
                    
                    #print(f"\nNode {event.node.id} zaczyna nadawać o czasie {self.time}")
                    
                    duration = self.medium.start_transmission(self.time, 1500, node=event.node)

                    # end event powinien odnosić się do tego samego ramkau co start
                    pkt = event.frame if getattr(event, "frame", None) is not None else (event.node.queue[0] if event.node.queue else None)
                    new_event = Event(time=self.time + duration, type="end_transmission", node=event.node)
                    new_event.frame = pkt

                    self.logger.debug(f"Węzeł {event.node.id} rozpoczął transmisję o czasie {self.time} bez kolizji. Czas konca: {self.time + duration} ")
                    ##self.logger.debug(f"Rozmiar eventów w kolejce: {len(self.events)}")
                    self.events.append(new_event)
                    ##self.logger.debug(f"Rozmiar eventów w kolejce: {len(self.events)}")



            elif event.type == "end_transmission":
                # -------------------------------
                # Jeden węzeł kończy nadawać
                # -------------------------------

                self.logger.debug(f"Węzeł {event.node.id} kończy nadawać o czasie {self.time}")

                #print(f"Node {event.node.id} kończy nadawać o czasie {self.time}")

                # defensywnie: pracujemy na konkretnym pakiecie powiązanym z eventem
                pkt = getattr(event, "frame", None)
                if pkt is not None and pkt in event.node.queue:
                    pkt.received_time = self.time
                    self.stats.record_received(pkt)
                    # usuń konkretny ramka z kolejki
                    event.node.queue.remove(pkt)
                else:
                    ##self.logger.debug(f"Jakis else")
                    # jeśli ramka z jakiegoś powodu nie istnieje w queue, log minimalnie i kontynuuj
                    # (ważne: i tak musimy zakończyć transmisję w medium)
                    pass

                # zresetuj retry counter jeśli istniał (nie szkodzi jeśli ramka był już usunięty)
                event.node.retries = 0

                # zakończ transmisję w medium (użyj dokładnego time z event)
                self.medium.end_transmission(event.node, event.time)

                # jeśli pozostały ramki w kolejce, zaplanuj następną próbę
                if event.node.queue:

                    ##self.logger.debug(f"Węzeł {event.node.id} ma więcej ramek, planuje następną próbę.")

                    self.debug_set.add(event.node.queue[0].fid)
                    new_event = Event(time=self.time + self.inter_frame_gap, type="try_transmission", node=event.node)
                    self.events.append(new_event)
                    self.events.sort(key=lambda e: e.time)
                else:
                    self.logger.debug(f"Węzeł {event.node.id} nie ma więcej ramek do wysłania o czasie {self.time}.")
                    pass
                    
                

            


        elif len(try_events) > 0 and len(end_event) == 1:

            self.logger.debug(f"Jeden węzeł {end_event[0].node.id} kończy nadawać o czasie {self.time} wezly co chca nadawac: {[w.node.id for w in try_events]}")

            event = end_event[0]

            self.nodes[event.node.id].queue[0].received_time = self.time
            self.stats.record_received(self.nodes[event.node.id].queue[0])
            #print(f"Ilość odebranych ramek: {self.stats.frame_count_received} / {len(self.generated_frames)}", end='\r')
            #print(f"Ilosc odebranych mega bajtów: {self.stats.total_bytes_received/1e6} MB", end='\r')

            self.nodes[event.node.id].retries = 0
            self.nodes[event.node.id].queue.remove(event.node.queue[0])

            self.medium.end_transmission(event.node, self.time)

            if event.node.queue:

                self.debug_set.add(event.node.queue[0].fid)

                new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=event.node)
                self.events.append(new_event)

            for ev in try_events:

                if ev.node.queue:

                    if ev.node.queue[0].first_attempt_time is None:
                        ev.node.queue[0].first_attempt_time = self.time

                    self.debug_set.add(ev.node.queue[0].fid)
                    new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=ev.node)
                    self.events.append(new_event)






        elif len(try_events) > 0 and len(start_event) == 1:

            self.logger.debug(f"Jeden węzeł {start_event[0].node.id} zaczyna nadawać o czasie {self.time} i probuje nadawac {[w.node.id for w in try_events]} węzłów")

            event = start_event[0]

            if not self.medium.is_free(self.time):

                self.stats.record_collision()
                event.node.handle_collision()

                if event.node.wasDrop:

                    #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")

                    
                    if event.node.queue:

                        self.debug_set.add(event.node.queue[0].fid)
                        new_event = Event(time= self.time + self.slot_time, type="try_transmission", node=event.node)
                        self.events.append(new_event)

                        event.node.wasDrop = False
                
                else:

                    #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")
                    self.debug_set.add(event.node.queue[0].fid)
                    if event.node.queue:

                        new_event = Event(time= event.node.backOff, type="try_transmission", node=event.node)
                        self.events.append(new_event)
                

            else:
                
                #print(f"\nNode {event.node.id} zaczyna nadawać o czasie {self.time}")

                duration = self.medium.start_transmission(self.time, 1500, node=event.node)
                if event.node.queue:
                    new_event = Event(time=self.time + duration, type="end_transmission", node=event.node)
                    self.events.append(new_event)

            for ev in try_events:

                if ev.node.queue:

                    if ev.node.queue[0].first_attempt_time is None:
                        ev.node.queue[0].first_attempt_time = self.time

                    self.debug_set.add(ev.node.queue[0].fid)
                    new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=ev.node)
                    self.events.append(new_event)

        else:
            if transmission_events:
                self.logger.debug(f"Nieobsługiwany przypadek eventów o czasie {self.time}: {[e.type for e in transmission_events]}")
            pass

    def handle_event_2(self, events):
        """Uproszczona obsługa eventów w jednej chwili czasu."""

        # Grupowanie typów eventów
        gen_events = [e for e in events if e.type == "generate_frame"]
        end_events = [e for e in events if e.type == "end_transmission"]
        try_events = [e for e in events if e.type == "try_transmission"]
        start_events = [e for e in events if e.type == "start_transmission"]

        # -------------------------------
        # 1. Zakończ transmisje
        # -------------------------------
        for ev in end_events:
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
            node = ev.node
            if ev.time <= self.max_sim_time:
                node.generate_frame_now(ev.time)
                if len(node.queue) == 1:
                    self.events.append(Event(self.time, "try_transmission", node))
                next_time = ev.time + random.random() * self.interarrival_det
                self.events.append(Event(next_time, "generate_frame", node))

        # -------------------------------
        # 3. Obsłuż próby transmisji
        # -------------------------------
        active_nodes = [e.node for e in try_events + start_events if e.node.queue]

        if not active_nodes:
            return  # nic się nie dzieje, spokój

        # Jeśli więcej niż jeden węzeł próbuje naraz -> kolizja
        if len(active_nodes) > 1 and self.medium.is_free(self.time):
            self.stats.record_collision()
            for node in active_nodes:
                if node.queue[0].first_attempt_time is None:
                    node.queue[0].first_attempt_time = self.time
                node.handle_collision()
                if node.queue:
                    self.events.append(Event(node.backOff, "try_transmission", node))
            return

        # Jeśli tylko jeden node próbuje
        node = active_nodes[0]
        frame = node.queue[0]

        if frame.first_attempt_time is None:
            frame.first_attempt_time = self.time

        if self.medium.is_free(self.time):
            duration = self.medium.start_transmission(self.time, frame.size_bytes, node)
            end_ev = Event(self.time + duration, "end_transmission", node)
            end_ev.frame = frame
            self.events.append(end_ev)
        else:
            # medium zajęte, spróbuj ponownie po czasie slotu
            self.events.append(Event(self.time + self.slot_time, "try_transmission", node))


    def run(self):

        print("\nRozpoczynanie symulacji...\n")
        self.logger.debug("Rozpoczynanie symulacji.")

        for n in self.nodes:
            # losowy offset, żeby nie synchronizować wszystkiego
            initial_offset = random.random() * self.interarrival_det if self.interarrival_det != float('inf') else 0.0
            new_event = Event(time=initial_offset, type="generate_frame", node=n)
            self.events.append(new_event)


        while self.time < self.max_sim_time and self.events:
            #print(f"Czas symulacji: {self.time:.6f} s, Pozostało eventów: {len(self.events)}", end='\r')

            ##self.logger.debug(f"Rozmiar eventów w kolejce w while: {len(self.events)}")

            self.events.sort(key=lambda e: e.time)

            self.time = self.events[0].time

            #print(f"Ilość ramkaow retry: {len(self.debug_set)} / {len(self.generated_frames)}", end='\r')

            # grupowanie wydarzeń z tolerancją float
            epsilon  = 1e-6
            events = [event for event in self.events if abs(event.time - self.time) < epsilon]

            #print(f"\nCzas symulacji: {self.time}, Obsługiwane id węzłów: {[event.node.id for event in events]}")

            self.events = [e for e in self.events if e not in events]

            self.handle_event(events)

        print("\nSymulacja zakończona.\n")
        self.logger.debug("Symulacja zakończona.")

        return self.stats.summary(self.time)
    
logger = logging.getLogger("calbench")
logger.setLevel(logging.DEBUG)

fh = RotatingFileHandler("calbench.log", maxBytes=32*1024*1024, backupCount=3, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s   %(message)s"))

logger.addHandler(fh)

cos = Simulator(3,30,100,30, logger)
cos.run()