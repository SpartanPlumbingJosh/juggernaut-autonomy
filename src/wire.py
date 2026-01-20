import json
import logging
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_LOOP_SLEEP_SECONDS: float = 1.0
DEFAULT_HEALTH_SNAPSHOT_INTERVAL_SECONDS: float = 60.0
DEFAULT_SNAPSHOT_FILE_NAME: str = "health_snapshots.jsonl"


@dataclass
class HealthSnapshot:
    """Represents a single health snapshot of the worker.

    Attributes:
        worker_id: Identifier for the worker instance.
        timestamp: Epoch timestamp when the snapshot was taken.
        loop_iteration: The current loop iteration count.
        uptime_seconds: Time in seconds since the worker started.
        process_id: Operating system process identifier.
        thread_count: Number of active threads in the process.
        load_average_1m: 1-minute system load average if available, otherwise None.
    """

    worker_id: str
    timestamp: float
    loop_iteration: int
    uptime_seconds: float
    process_id: int
    thread_count: int
    load_average_1m: Optional[float]


def _get_load_average_1m() -> Optional[float]:
    """Safely retrieve the 1-minute system load average.

    Returns:
        The 1-minute load average if supported by the OS, otherwise None.
    """
    try:
        load1, _load5, _load15 = os.getloadavg()
    except (OSError, AttributeError):
        return None
    return float(load1)


def track_metrics(worker_id: str, loop_iteration: int) -> None:
    """Track lightweight metrics on each worker loop iteration.

    This function is intended to be called on every iteration of the main worker
    loop. It should remain fast and avoid heavy I/O so as not to interfere with
    normal worker performance.

    Args:
        worker_id: Identifier of the worker instance.
        loop_iteration: The current loop iteration count.

    Returns:
        None
    """
    # Example metrics: here we log; this could be extended to push to a metrics backend.
    LOGGER.debug(
        "Tracking metrics for worker_id=%s iteration=%d",
        worker_id,
        loop_iteration,
    )


def store_health_snapshot(
    worker_id: str,
    loop_iteration: int,
    started_at_monotonic: float,
    output_path: Path,
) -> HealthSnapshot:
    """Create and persist a health snapshot for the worker.

    The snapshot is appended as a JSON line to the provided output path, which
    is created if it does not exist.

    Args:
        worker_id: Identifier for the worker instance.
        loop_iteration: The current loop iteration count.
        started_at_monotonic: Monotonic timestamp when the worker started.
        output_path: File path where snapshots are stored as JSON Lines.

    Returns:
        The created HealthSnapshot instance.

    Raises:
        OSError: If writing to the snapshot file fails.
        ValueError: If loop_iteration is not positive.
    """
    if loop_iteration <= 0:
        raise ValueError("loop_iteration must be a positive integer")

    now_real: float = time.time()
    uptime_seconds: float = time.monotonic() - started_at_monotonic

    snapshot = HealthSnapshot(
        worker_id=worker_id,
        timestamp=now_real,
        loop_iteration=loop_iteration,
        uptime_seconds=uptime_seconds,
        process_id=os.getpid(),
        thread_count=threading.active_count(),
        load_average_1m=_get_load_average_1m(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    line: str = json.dumps(asdict(snapshot), separators=(",", ":"))
    try:
        with output_path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError as exc:
        LOGGER.error("Failed to write health snapshot to %s", output_path)
        raise exc

    LOGGER.info(
        "Stored health snapshot for worker_id=%s iteration=%d at %s",
        worker_id,
        loop_iteration,
        output_path,
    )
    return snapshot


class Worker:
    """Represents a long-running worker with integrated health monitoring.

    The worker executes a main loop where it performs work, tracks metrics on
    each iteration, and periodically stores health snapshots.

    Attributes:
        worker_id: Identifier for this worker instance.
        loop_sleep_seconds: Time to sleep between loop iterations.
        health_snapshot_interval_seconds: Interval between health snapshots.
        snapshot_output_path: File path where health snapshots are stored.
    """

    def __init__(
        self,
        worker_id: str,
        loop_sleep_seconds: float = DEFAULT_LOOP_SLEEP_SECONDS,
        health_snapshot_interval_seconds: float = DEFAULT_HEALTH_SNAPSHOT_INTERVAL_SECONDS,
        snapshot_output_path: Optional[Path] = None,
    ) -> None:
        """Initialize the worker.

        Args:
            worker_id: Identifier for this worker instance.
            loop_sleep_seconds: Time in seconds to sleep between loop iterations.
            health_snapshot_interval_seconds: Minimum interval between stored health snapshots.
            snapshot_output_path: Optional custom path for snapshot file. If None,
                a default file name is used in the current working directory.

        Raises:
            ValueError: If any of the time-based parameters are not positive.
        """
        if loop_sleep_seconds <= 0:
            raise ValueError("loop_sleep_seconds must be positive")
        if health_snapshot_interval_seconds <= 0:
            raise ValueError("health_snapshot_interval_seconds must be positive")

        self.worker_id: str = worker_id
        self.loop_sleep_seconds: float = loop_sleep_seconds
        self.health_snapshot_interval_seconds: float = health_snapshot_interval_seconds
        self.snapshot_output_path: Path = snapshot_output_path or Path.cwd() / DEFAULT_SNAPSHOT_FILE_NAME

        self._stop_event: threading.Event = threading.Event()
        self._started_at_monotonic: Optional[float] = None

    def stop(self) -> None:
        """Signal the worker loop to stop gracefully.

        Returns:
            None
        """
        self._stop_event.set()
        LOGGER.info("Stop signal set for worker_id=%s", self.worker_id)

    def _do_work_iteration(self, loop_iteration: int) -> None:
        """Perform a single unit of work for the worker.

        This method is a placeholder for real work. It can be overridden in a
        subclass or modified to perform actual business logic.

        Args:
            loop_iteration: The current loop iteration count.

        Returns:
            None
        """
        LOGGER.debug(
            "Worker %s performing work on iteration %d",
            self.worker_id,
            loop_iteration,
        )
        # Insert real work logic here.

    def run(self, max_iterations: Optional[int] = None) -> None:
        """Run the main worker loop.

        Each iteration of the loop calls `track_metrics()` for lightweight
        health tracking and, at configured intervals, `store_health_snapshot()`
        to persist a snapshot of worker health.

        Args:
            max_iterations: Optional maximum number of iterations to run. If None,
                the worker runs until `stop()` is called.

        Returns:
            None
        """
        self._started_at_monotonic = time.monotonic()
        last_snapshot_monotonic: float = self._started_at_monotonic
        loop_iteration: int = 0

        LOGGER.info(
            "Starting worker loop for worker_id=%s (max_iterations=%s)",
            self.worker_id,
            str(max_iterations) if max_iterations is not None else "unbounded",
        )

        try:
            while not self._stop_event.is_set():
                loop_iteration += 1

                track_metrics(self.worker_id, loop_iteration)

                now_monotonic: float = time.monotonic()
                if now_monotonic - last_snapshot_monotonic >= self.health_snapshot_interval_seconds:
                    try:
                        store_health_snapshot(
                            worker_id=self.worker_id,
                            loop_iteration=loop_iteration,
                            started_at_monotonic=self._started_at_monotonic,
                            output_path=self.snapshot_output_path,
                        )
                    except OSError:
                        LOGGER.exception(
                            "Error while storing health snapshot for worker_id=%s",
                            self.worker_id,
                        )
                    last_snapshot_monotonic = now_monotonic

                self._do_work_iteration(loop_iteration)

                if max_iterations is not None and loop_iteration >= max_iterations:
                    LOGGER.info(
                        "Reached max_iterations=%d for worker_id=%s, stopping loop",
                        max_iterations,
                        self.worker_id,
                    )
                    break

                time.sleep(self.loop_sleep_seconds)
        finally:
            LOGGER.info("Worker loop stopped for worker_id=%s", self.worker_id)


def _configure_logging() -> None:
    """Configure basic logging for standalone execution.

    Returns:
        None
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


if __name__ == "__main__":
    _configure_logging()
    worker = Worker(worker_id="demo-worker")
    try:
        # Run a finite number of iterations in demo mode.
        worker.run(max_iterations=10)
    except KeyboardInterrupt:
        LOGGER.info("KeyboardInterrupt received, requesting worker stop")
        worker.stop()