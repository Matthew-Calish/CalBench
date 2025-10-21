import classes as cl

num_nodes = 700
bandwidth_mbps = 2
total_data_bytes = 1e5

print("\nRozpoczynam Symulacje:")
sim = cl.Simulator(num_nodes, bandwidth_mbps, total_data_bytes)

results = sim.run()
print(f"\nEthernet Simulation Results ({num_nodes} nodes, {bandwidth_mbps} Mbps, {total_data_bytes} bytes per node):")
for k, v in results.items():
    print(f"{k}: {v}")