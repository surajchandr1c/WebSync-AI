import argparse
import asyncio
import logging
import sys
from agent.config import settings
from agent.metrics import get_static_capabilities, sample_system_metrics

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [agent]: %(message)s",
)
logger = logging.getLogger("websync-worker")


def inspect_system():
    """Print the node's genuine hardware specifications and current metrics."""
    caps = get_static_capabilities()
    metrics = sample_system_metrics()
    
    print("\n=== WebSync AI Worker Agent — Node Telemetry ===")
    print(f"Worker ID:        {settings.WORKER_ID}")
    print(f"Platform:         {caps['platform']} {caps['platform_version']} ({caps['architecture']})")
    print(f"Hostname:         {caps['hostname']}")
    print(f"CPU Cores:        {caps['cpu_count_physical']} physical / {caps['cpu_count_logical']} logical")
    print(f"Total RAM:        {caps['total_memory_bytes'] / (1024**3):.2f} GB")
    print(f"Current CPU:      {metrics['cpu_percent']}%")
    print(f"RAM Used:         {metrics['memory_used_bytes'] / (1024**3):.2f} GB ({metrics['memory_percent']}%)")
    print(f"Disk Free:        {metrics['disk_free_bytes'] / (1024**3):.2f} GB")
    print("================================================\n")


async def run_agent():
    """Foundation agent loop (Phase 1 initialization)."""
    logger.info("Initializing WebSync AI Worker Agent (ID: %s)", settings.WORKER_ID)
    logger.info("Target Coordinator URL: %s", settings.WORKER_COORDINATOR_URL)
    
    caps = get_static_capabilities()
    logger.info(
        "Host detected: %s on %s (%d CPU cores, %.1f GB RAM)",
        caps["hostname"],
        caps["platform"],
        caps["cpu_count_logical"],
        caps["total_memory_bytes"] / (1024**3),
    )
    logger.info("Phase 1 initialization complete. Agent execution engine ready for Phase 2 registration.")


def main():
    parser = argparse.ArgumentParser(description="WebSync AI Distributed Compute Worker Agent")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect and print genuine host hardware telemetry and exit.",
    )
    args = parser.parse_args()

    if args.inspect:
        inspect_system()
        sys.exit(0)

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logger.info("Agent process interrupted by user. Exiting.")


if __name__ == "__main__":
    main()
