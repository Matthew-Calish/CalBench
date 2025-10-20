import classes as cl

print("\nRozpoczynam Symulacje:")
sim = cl.Simulator(num_nodes=100, bandwidth_mbps=2, total_data_bytes=1e5)

results = sim.run()
print("\nEthernet Simulation Results (100 Mb/s, 1 GB total):")
for k, v in results.items():
    print(f"{k}: {v}")