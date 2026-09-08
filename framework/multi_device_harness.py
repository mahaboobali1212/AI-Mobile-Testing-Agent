"""
MultiDeviceHarness: Test runtime harness managing multi-device lifecycle, step recording, and artifact collection.
"""

import os
import json
import time
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

from .device_session import DeviceSession


class StepRecorder:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.steps: List[Dict[str, Any]] = []
        self.screenshots: List[str] = []

    def record_step(self, name: str, status: str, duration: float, error: Optional[str] = None, screenshots: Optional[List[str]] = None):
        self.steps.append({
            "step_index": len(self.steps) + 1,
            "name": name,
            "status": status,
            "duration": round(duration, 3),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": error,
            "screenshots": screenshots or []
        })


class MultiDeviceHarness:
    """The central fixture / harness initialized during test execution."""
    def __init__(self, devices_map: Dict[str, DeviceSession], run_dir: Path):
        self.devices = devices_map
        self.run_dir = run_dir
        self.screenshots_dir = run_dir / "screenshots"
        self.logs_dir = run_dir / "logs"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Point each device's screenshot directory to this run's folder
        for dev in self.devices.values():
            dev.screenshot_dir = self.screenshots_dir

        self.recorder = StepRecorder(run_dir)
        self.current_step_name = "Initialization"
        self.start_time = time.time()
        self.status = "RUNNING"
        self.error_message: Optional[str] = None
        self.stack_trace: Optional[str] = None

    def get_device(self, alias: str) -> DeviceSession:
        if alias not in self.devices:
            raise KeyError(f"Device alias '{alias}' not found. Available devices: {list(self.devices.keys())}")
        return self.devices[alias]

    @property
    def device_a(self) -> DeviceSession:
        return self.get_device("device_a")

    @property
    def device_b(self) -> DeviceSession:
        return self.get_device("device_b")

    @contextmanager
    def step(self, description: str):
        """Context manager to record an individual test step with before/after screenshots."""
        self.current_step_name = description
        step_start = time.time()
        step_screenshots = []
        
        # Capture before screenshot for all active devices
        for dev in self.devices.values():
            try:
                ss = dev.take_screenshot(f"before_{len(self.recorder.steps)+1}")
                step_screenshots.append(str(ss.name))
            except Exception:
                pass

        step_error = None
        try:
            yield
            step_status = "PASSED"
        except Exception as e:
            step_status = "FAILED"
            step_error = f"{type(e).__name__}: {str(e)}"
            raise e
        finally:
            # Capture after screenshot
            for dev in self.devices.values():
                try:
                    ss = dev.take_screenshot(f"after_{len(self.recorder.steps)+1}")
                    step_screenshots.append(str(ss.name))
                except Exception:
                    pass

            duration = time.time() - step_start
            self.recorder.record_step(description, step_status, duration, step_error, step_screenshots)

    def finalize(self, success: bool, error: Optional[Exception] = None):
        """Finalizes test run and saves metadata summary to JSON."""
        self.status = "PASSED" if success else "FAILED"
        if error:
            self.error_message = f"{type(error).__name__}: {str(error)}"
            self.stack_trace = traceback.format_exc()

        summary = {
            "status": self.status,
            "total_duration": round(time.time() - self.start_time, 2),
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time)),
            "end_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "devices": {alias: {"serial": dev.serial, "simulated": dev.is_simulated} for alias, dev in self.devices.items()},
            "steps": self.recorder.steps,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace
        }

        with open(self.run_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


# Global helper context manager for direct test script usage
_CURRENT_HARNESS: Optional[MultiDeviceHarness] = None

def set_active_harness(harness: MultiDeviceHarness):
    global _CURRENT_HARNESS
    _CURRENT_HARNESS = harness

def get_active_harness() -> Optional[MultiDeviceHarness]:
    return _CURRENT_HARNESS

@contextmanager
def step(description: str):
    if _CURRENT_HARNESS:
        with _CURRENT_HARNESS.step(description):
            yield
    else:
        # Fallback if run without harness
        yield
