import random
import numpy as np
import matplotlib.pyplot as plt

# -------------------------------
# 1. Packet
# -------------------------------
class Packet:
    def __init__(self, pid, src, dst, size_bytes, gen_time):
        self.pid = pid
        self.src = src
        self.dst = dst
        self.size_bytes = size_bytes
        self.generation_time = gen_time
        self.sent_time = None
        self.received_time = None
        self.retries = 0


# -------------------------------
# 2. Stats
# -------------------------------
class Stats:
    def __init__(self):
        self.total_bytes_transmitted = 0
        self.total_bytes_received = 0
        self.packet_count_sent = 0
        self.packet_count_received = 0
        self.collision_events = 0
        self.latencies = []
        self.packets_dropped = 0
        self.total_retries = 0

    def record_sent(self, packet):
        self.packet_count_sent += 1
        self.total_bytes_transmitted += packet.size_bytes

    def record_received(self, packet):

        self.packet_count_received += 1
        self.total_bytes_received += packet.size_bytes

        self.latencies.append(packet.received_time - packet.generation_time)


    def record_collision(self):
        self.collision_events += 1

    def record_retry(self):
        self.total_retries += 1

    def record_drop(self):
        self.packets_dropped += 1

    def summary(self, total_time_s):

        throughput_mbps = (self.total_bytes_received * 8) / (total_time_s * 1e6)
        avg_latency = np.mean(self.latencies) if self.latencies else 0

        avg_retries = self.total_retries / self.packet_count_sent if self.packet_count_sent else 0

        return {
            "Simulation Time": total_time_s,
            "Throughput [Mb/s]": round(throughput_mbps, 3),
            "Avg latency [s]": round(avg_latency, 3),
            "Collisions": self.collision_events,
            "Dropped": self.packets_dropped,
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

    def start_transmission(self, current_time, packet_size_bytes, node=None):

        transmission_time = (packet_size_bytes * 8) / self.bandwidth_bps

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
        self.packet_length = 1500

    def generate_packet(self):

        pid = len(self.sim.generated_packets) + 1
        packet = Packet(pid, self.id, "Server", self.packet_length, self.sim.time)

        self.queue.append(packet)
        self.sim.generated_packets.append(packet)
        self.sim.active_packets.append(packet) 

    def attempt_send(self):

        if not self.queue:
            return
        
        packet = self.queue[0]
        packet.sent_time = self.sim.time

        return packet


    def handle_collision(self):

        if self.retries > 15:

            #print(f"\nNode {self.id}: Packet {self.queue[0].pid} dropped after 16 retries.\n")

            # pakiet uznany za utracony
            self.sim.active_packets.remove(self.queue[0])
            self.queue.pop(0)
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



# -------------------------------
# 5. Simulator
# -------------------------------
class Simulator:

    def __init__(self, num_nodes=5, bandwidth_mbps=100, total_data_bytes=1e6):

        self.time = 0
        self.slot_time = 512 / (bandwidth_mbps * 1e6)

        self.nodes = [Node(i, self) for i in range(num_nodes)]
        self.medium = Medium(bandwidth_mbps)
        self.stats = Stats()

        self.generated_packets = []
        self.active_packets = []

        self.total_data_bytes = total_data_bytes
        self.events = []  

    def handle_event(self, events):

        try_events = [e for e in events if e.type == "try_transmission"]

        if len(try_events) > 1:


            # -------------------------------
            # Więcej niż jeden węzeł próbuje nadać w tym samym czasie
            # -------------------------------


            if self.medium.is_free(self.time): 

                #print(f"Kolizja o czasie {self.time} między węzłami {[event.node.id for event in events]}")

                # kolizja
                
                for event in try_events:

                    self.stats.record_collision()
                    event.node.handle_collision()

                    if event.node.wasDrop:

                        #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")

                        new_event = Event(time= self.time + self.slot_time, type="try_transmission", node=event.node)
                        self.events.append(new_event)

                        event.node.wasDrop = False
                    
                    else:

                        #print(f"Dodano węzeł {event.node.id} do ponownej próby o czasie {event.node.backOff}")

                        new_event = Event(time= event.node.backOff, type="try_transmission", node=event.node)
                        self.events.append(new_event)

            else:

                #medium zajęte, ponów próbę po czasie slot_time
                #print(f"Medium zajęte o czasie {self.time}, ponawianie prób węzłów {[event.node.id for event in try_events]}")
                for event in try_events:

                    new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=event.node)

                    self.events.append(new_event)
                    self.events.sort(key=lambda e: e.time)

            self.events.sort(key=lambda e: e.time)

        else:

            event = events[0]

            if event.type == "try_transmission":

                # -------------------------------
                # Jeden węzeł próbuje nadawać
                # -------------------------------

                #print(f"Node {event.node.id} próbuje nadać o czasie {self.time}")
                
                if self.medium.is_free(self.time):

                    print(f"Node {event.node.id} medium wolne o czasie {self.time}, rozpoczyna nadawanie.")
                    new_event = Event(time=self.time, type="start_transmission", node=event.node)
                    
                    self.events.append(new_event)
                    self.events.sort(key=lambda e: e.time)

                else:
                    #print(f"Node {event.node.id} medium zajęte o czasie {self.time}, ponawia próbę.")
                    # medium zajęte, ponów próbę po czasie slot_time
                    new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=event.node)

                    self.events.append(new_event)
                    self.events.sort(key=lambda e: e.time)


            elif event.type == "start_transmission":

                # -------------------------------
                # Jeden węzeł zaczyna nadawać
                # -------------------------------

                

                if not self.medium.is_free(self.time):

                    self.stats.record_collision()
                    event.node.handle_collision()
                    new_event = Event(time= event.node.backOff, type="try_transmission", node=event.node)
                    self.events.append(new_event)
                    

                else:
                    
                    print(f"\nNode {event.node.id} zaczyna nadawać o czasie {self.time}")

                    duration = self.medium.start_transmission(self.time, 1500, node=event.node)

                    new_event = Event(time=self.time + duration, type="end_transmission", node=event.node)
                    self.events.append(new_event)

                self.events.sort(key=lambda e: e.time)


            elif event.type == "end_transmission":

                # -------------------------------
                # Jeden węzeł kończy nadawać
                # -------------------------------

                print(f"Node {event.node.id} kończy nadawać o czasie {self.time}")

                self.nodes[event.node.id].queue[0].received_time = self.time
                self.stats.record_received(self.nodes[event.node.id].queue[0])

                self.nodes[event.node.id].retries = 0
                self.nodes[event.node.id].queue.pop(0)

                self.medium.end_transmission(event.node, self.time)

                if event.node.queue:

                    new_event = Event(time=self.time + self.slot_time, type="try_transmission", node=event.node)
                    self.events.append(new_event)
                    self.events.sort(key=lambda e: e.time)




    def run(self):

        for n in self.nodes:
            
            # każdy węzeł ma tę samą ilość danych do przesłania
            packets_per_node = int(self.total_data_bytes / 1500)
            n.backOff = random.randint(0, 10) * self.slot_time

            for _ in range(packets_per_node):
                n.generate_packet()

            print(f"Węzeł {n.id} wygenerował {len(n.queue)} pakietów.")

            new_event = Event(time=n.backOff, type="try_transmission", node=n)
            self.events.append(new_event)
            

        self.events.sort(key=lambda e: e.time)

        while self.events:  

            self.time = self.events[0].time

            # grupowanie wydarzeń z tolerancją float
            epsilon = max(1e-9, self.slot_time * 1e-6)
            events = [event for event in self.events if abs(event.time - self.time) < epsilon]

            #print(f"\nCzas symulacji: {self.time}, Obsługiwane id węzłów: {[event.node.id for event in events]}")

            for event in events:
                self.events.remove(event)

            self.handle_event(events) 


        return self.stats.summary(self.time)