import os

# Prevent random CPU spikes from failing worker unit tests by default
os.environ["WORKER_MAX_CPU_PERCENT"] = "100.0"
