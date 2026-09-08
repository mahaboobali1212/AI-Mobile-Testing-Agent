"""
Synchronization utilities for coordinating actions across multiple Android devices.
"""

import time
import threading
from typing import Callable, Optional


class SyncBarrier:
    """Thread-safe synchronization barrier for multi-device test steps."""
    def __init__(self, parties: int = 2, timeout: float = 30.0):
        self.parties = parties
        self.timeout = timeout
        self.barrier = threading.Barrier(parties)

    def wait(self):
        """Waits until all participating devices reach this point."""
        try:
            self.barrier.wait(timeout=self.timeout)
        except threading.BrokenBarrierError:
            raise TimeoutError(f"SyncBarrier timed out waiting for {self.parties} devices.")


def wait_until(condition: Callable[[], bool], timeout: float = 15.0, poll_interval: float = 0.5, error_msg: Optional[str] = None) -> bool:
    """Polls a condition function until it returns True or timeout is reached."""
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        time.sleep(poll_interval)
    if error_msg:
        raise AssertionError(f"Condition not met within {timeout}s: {error_msg}")
    return False
