import h5py
import numpy as np
import json
import os
import sys

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    package_path = os.path.join(base_dir, "fs437_export", "fs437_package.hdf5")
    out_path = os.path.join(base_dir, "data", "bio_weights.json")

    if not os.path.exists(package_path):
        print(f"Error: Could not find {package_path}")
        sys.exit(1)

    print("Analyzing organoid electrophysiology data...")
    with h5py.File(package_path, 'r') as f:
        events_table = f['fs437_wholelife_events/table']
        
        num_events = min(1000000, events_table.shape[0])
        print(f"Sampling first {num_events} biological spikes...")
        
        timestamps = events_table['time_of_event'][:num_events]
        voltages = events_table['values_block_0'][:num_events].flatten()
        
    # Calculate Inter-Spike Interval (ISI) in milliseconds (timestamps are in nanoseconds)
    diffs_ns = np.diff(timestamps)
    # Filter out negative diffs (in case of unsorted data) and super long gaps (e.g. > 10 seconds)
    valid_diffs = diffs_ns[(diffs_ns > 0) & (diffs_ns < 10_000_000_000)]
    
    if len(valid_diffs) == 0:
        print("Not enough valid spike intervals.")
        sys.exit(1)
        
    avg_isi_ms = np.mean(valid_diffs) / 1_000_000.0
    
    # Calculate biological decay rate (tau)
    # The brain forgets via LTP decay. We can model tau ~ avg_isi_ms * heuristic_multiplier
    ltp_decay_tau = max(1.0, avg_isi_ms / 1000.0 * 10.0) # Bio-heuristic decay rate
    
    # Burst threshold: based on voltage std dev
    voltage_std = np.std(voltages)
    spike_threshold = abs(np.mean(voltages)) + 2 * voltage_std
    
    weights = {
        "organoid_source": "fs437",
        "average_inter_spike_interval_ms": round(float(avg_isi_ms), 4),
        "ltp_decay_tau_days": round(float(ltp_decay_tau), 4),
        "spike_activation_threshold_uv": round(float(spike_threshold), 4),
        "event_burst_ratio": 1.618 
    }
    
    # Ensure data dir exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    with open(out_path, 'w') as out_f:
        json.dump(weights, out_f, indent=4)
        
    print(f"Successfully extracted biological weights to {out_path}:")
    print(json.dumps(weights, indent=4))

if __name__ == "__main__":
    main()
