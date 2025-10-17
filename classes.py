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
        if packet.received_time and packet.generation_time:
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
            "Avg latency [ms]": round(avg_latency, 3),
            "Collisions": self.collision_events,
            "Retries avg": round(avg_retries, 2),
            "Dropped": self.packets_dropped,
        }


# -------------------------------
# 3. Medium
# -------------------------------
class Medium:

    def __init__(self, bandwidth_mbps):
        self.bandwidth_bps = bandwidth_mbps * 1e6
        self.busy_until = 0.0
        self.current_node = None 

    def is_free(self, current_time):
        return current_time >= self.busy_until

    def start_transmission(self, current_time, packet_size_bytes, node=None):
        transmission_time = (packet_size_bytes * 8) / self.bandwidth_bps
        self.busy_until = current_time + transmission_time
        self.current_node = node
        return transmission_time
    
    def end_transmission(self):
        self.current_node = None
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
        self.backOff = 0
        self.queue = []

    def generate_packet(self, size_bytes=1500):

        pid = len(self.sim.generated_packets) + 1
        packet = Packet(pid, self.id, "Server", size_bytes, self.sim.time)
        self.queue.append(packet)
        self.sim.generated_packets.append(packet)
        self.sim.active_packets.append(packet) 

    def attempt_send(self):

        if not self.queue:
            return
        

        packet = self.queue[0]
        ##self.sim.active_packets.remove(packet)

        ##self.retries = 0
        ##self.queue.pop(0)

        #success = self.sim.medium.start_transmission(self)
        packet.sent_time = self.sim.time

        #self.sim.stats.record_sent(packet)
        return packet


    def handle_collision(self):

        if self.retries > 16:
            # pakiet uznany za utracony
            self.sim.active_packets.remove(self.queue[0])
            self.queue.pop(0)
            
            self.backOff = 0
            self.sim.stats.record_drop()
            return

        self.retries += 1
        self.sim.stats.record_retry()

        delay_slots = random.randint(0, 2**self.retries - 1)
        self.backOff = self.sim.time + delay_slots * self.sim.slot_time


    def finish_send(self, packet):
        self.sim.medium.end_transmission(self)
        self.sim.stats.record_received(packet)
        self.queue.pop(0)
        self.retries = 0
        self.state = "idle"


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
        self.events = []  # [(time, func, args)]

    def run(self):

        for n in self.nodes:

            # każdy węzeł ma tę samą ilość danych do przesłania
            packets_per_node = int(self.total_data_bytes / 1500)
            n.backOff = random.randint(0, 10) * self.slot_time

            for _ in range(packets_per_node):
                n.generate_packet()

        while self.active_packets:  
            
            print(len(self.active_packets))

            ready_nodes = [n for n in self.nodes if n.backOff <= self.time and n.queue]

            if len(ready_nodes) > 1:
            # kolizja

                for n in ready_nodes:
                    n.handle_collision()

                self.medium.busy_until = self.time
                self.stats.record_collision()
                self.time += self.slot_time
                
                continue

            if len(ready_nodes) == 1:

                node = ready_nodes[0]

                if self.medium.is_free(self.time):

                    packet = node.attempt_send()
                    if packet is None:
                        # nic do wysłania
                        self.time += self.slot_time
                        continue

                    tx_time = self.medium.start_transmission(self.time, 1500, node=node)
                    
                    self.time += tx_time

                    packet.received_time = self.time
                    self.stats.record_sent(packet)
                    self.stats.record_received(packet)

                    # usuń pakiet z queue i active_packets
                    node.queue.pop(0)
                    try:
                        self.active_packets.remove(packet)
                    except ValueError:
                        pass

                    # zakończ transmisję medium (ustaw wolne)
                    self.medium.end_transmission()

                    continue  

            self.time += self.slot_time

        return self.stats.summary(self.time / 1000.0)


