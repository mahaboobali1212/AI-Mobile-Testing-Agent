"""
DeviceManager: Discovers, configures, and allocates Android devices and emulators over ADB.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import ADB_PATH
from framework.device_session import DeviceSession


class DeviceManager:
    def __init__(self, adb_path: str = ADB_PATH):
        self.adb_path = adb_path

    def _exec_adb(self, args: List[str], timeout: int = 10) -> str:
        """Helper to run ADB commands safely."""
        try:
            res = subprocess.run(
                [self.adb_path] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            return res.stdout.strip()
        except Exception as e:
            return ""

    def list_connected_devices(self) -> List[Dict[str, Any]]:
        """Scans ADB for all currently attached devices and emulators."""
        output = self._exec_adb(["devices", "-l"])
        devices = []
        
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices") or line.startswith("*"):
                continue

            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                
                # Extract properties like model, product, device
                props = {}
                for part in parts[2:]:
                    if ":" in part:
                        k, v = part.split(":", 1)
                        props[k] = v

                devices.append({
                    "serial": serial,
                    "state": state,
                    "model": props.get("model", "Android Device"),
                    "device": props.get("device", "generic"),
                    "is_emulator": serial.startswith("emulator-"),
                    "is_simulated": False
                })
        
        return devices

    def list_available_avds(self) -> List[str]:
        """Lists installed Android Virtual Devices (AVDs)."""
        emulator_bin = shutil.which("emulator")
        if not emulator_bin:
            # Check standard Android SDK emulator path
            local_app_data = os.getenv("LOCALAPPDATA", "")
            if local_app_data:
                candidate = Path(local_app_data) / "Android" / "Sdk" / "emulator" / "emulator.exe"
                if candidate.exists():
                    emulator_bin = str(candidate)

        if not emulator_bin:
            return []

        try:
            res = subprocess.run(
                [emulator_bin, "-list-avds"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace"
            )
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    def allocate_devices(self, required_count: int = 2, allow_simulation: bool = True) -> Dict[str, DeviceSession]:
        """
        Allocates required number of device sessions (e.g. device_a, device_b).
        If physical/emulator devices are missing and allow_simulation is True, creates simulated devices.
        """
        connected = self.list_connected_devices()
        allocated: Dict[str, DeviceSession] = {}
        aliases = ["device_a", "device_b", "device_c", "device_d"]

        # 1. Map physical / live emulator devices
        for idx, dev_info in enumerate(connected[:required_count]):
            alias = aliases[idx] if idx < len(aliases) else f"device_{idx+1}"
            allocated[alias] = DeviceSession(
                serial=dev_info["serial"],
                alias=alias,
                is_simulated=False
            )

        # 2. Fill remaining required devices with simulated sessions if needed
        if len(allocated) < required_count:
            if allow_simulation:
                start_idx = len(allocated)
                for idx in range(start_idx, required_count):
                    alias = aliases[idx] if idx < len(aliases) else f"device_{idx+1}"
                    sim_serial = f"sim-emulator-{5554 + idx*2}"
                    allocated[alias] = DeviceSession(
                        serial=sim_serial,
                        alias=alias,
                        is_simulated=True
                    )
        # 3. Link all allocated devices as peers for state synchronization
        all_devs = list(allocated.values())
        for i in range(len(all_devs)):
            for j in range(i + 1, len(all_devs)):
                all_devs[i].link_peer(all_devs[j])

        return allocated
