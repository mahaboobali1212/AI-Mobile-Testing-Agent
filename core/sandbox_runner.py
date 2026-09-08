"""
SandboxRunner: Executes generated mobile test scripts in an isolated runtime environment with artifact collection.
"""

import sys
import time
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional

from config import ARTIFACTS_DIR, DEFAULT_COMMAND_TIMEOUT
from core.device_manager import DeviceManager
from framework.multi_device_harness import MultiDeviceHarness, set_active_harness


class SandboxRunner:
    def __init__(self, device_manager: Optional[DeviceManager] = None):
        self.device_manager = device_manager or DeviceManager()

    def run_script(self, script_path: Path, timeout: int = DEFAULT_COMMAND_TIMEOUT, allow_simulation: bool = True) -> Dict[str, Any]:
        """
        Executes the Python test script in a controlled sandbox harness.
        Captures all execution steps, screenshots, logs, and produces summary.json.
        """
        script_path = Path(script_path)
        if not script_path.exists():
            raise FileNotFoundError(f"Test script not found at {script_path}")

        # 1. Create timestamped run folder
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        run_name = f"run_{script_path.stem}_{timestamp}"
        run_dir = ARTIFACTS_DIR / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # 2. Allocate devices
        devices_map = self.device_manager.allocate_devices(
            required_count=2,
            allow_simulation=allow_simulation
        )

        # 3. Create Harness
        harness = MultiDeviceHarness(devices_map=devices_map, run_dir=run_dir)
        set_active_harness(harness)

        # 4. Load & Execute the script module
        success = False
        execution_error = None
        
        try:
            spec = importlib.util.spec_from_file_location("dynamic_test_module", script_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load module specification for {script_path}")

            test_module = importlib.util.module_from_spec(spec)
            sys.modules["dynamic_test_module"] = test_module
            spec.loader.exec_module(test_module)

            # Look for standard entry point: run_test(harness) or test_*(...)
            if hasattr(test_module, "run_test"):
                test_module.run_test(harness)
                success = True
            elif hasattr(test_module, "test_scenario"):
                test_module.test_scenario(harness.device_a, harness.device_b)
                success = True
            else:
                # Find any callable test_* function
                test_fns = [getattr(test_module, f) for f in dir(test_module) if f.startswith("test_") and callable(getattr(test_module, f))]
                if test_fns:
                    test_fns[0](harness)
                    success = True
                else:
                    raise AttributeError("Script does not contain a recognizable 'run_test(harness)' entry point.")

        except Exception as e:
            execution_error = e
            success = False

        # 5. Finalize harness & record summary
        summary = harness.finalize(success=success, error=execution_error)
        summary["run_dir"] = str(run_dir)
        summary["script_path"] = str(script_path)
        summary["run_name"] = run_name

        return summary
