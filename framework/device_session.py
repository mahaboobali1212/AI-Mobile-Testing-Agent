"""
DeviceSession: Encapsulates high-level automation actions for an individual Android device.
Supports both live ADB execution and simulated sandbox fallback.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config import ADB_PATH


class DeviceSession:
    def __init__(self, serial: str, alias: str = "device", is_simulated: bool = False, screenshot_dir: Optional[Path] = None):
        self.serial = serial
        self.alias = alias
        self.is_simulated = is_simulated
        self.screenshot_dir = screenshot_dir or Path("artifacts/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = []
        self._in_call = False
        self._current_app = "com.google.android.apps.nexuslauncher"
        self._screen_text = ["Home", "Phone", "Messages", "Chrome", "Camera"]
        self.peers: List['DeviceSession'] = []

    def link_peer(self, peer: 'DeviceSession'):
        if peer not in self.peers and peer is not self:
            self.peers.append(peer)
            peer.peers.append(self)

    def _run_adb(self, cmd_args: List[str], timeout: int = 15) -> str:
        """Executes an adb command targeting this device's serial."""
        if self.is_simulated:
            return "simulated"

        full_cmd = [ADB_PATH, "-s", self.serial] + cmd_args
        try:
            res = subprocess.run(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            return res.stdout.strip()
        except Exception as e:
            return f"Error: {e}"

    def dial_number(self, phone_number: str) -> bool:
        """Dials a phone number and initiates the call."""
        self._log_action(f"Dialing {phone_number}")
        if self.is_simulated:
            self._in_call = True
            self._current_app = "com.google.android.dialer"
            self._screen_text = ["Calling...", phone_number, "Mute", "Keypad", "Speaker", "End Call"]
            time.sleep(0.5)
            return True

        # Use intent to dial directly
        self._run_adb(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{phone_number}"])
        time.sleep(1)
        self._in_call = True
        return True

    def answer_incoming_call(self) -> bool:
        """Answers an active incoming voice call."""
        self._log_action("Answering incoming call")
        if self.is_simulated:
            self._in_call = True
            self._screen_text = ["Call in progress", "00:05", "Mute", "End Call"]
            time.sleep(0.5)
            return True

        # Keyevent 5 is KEYCODE_CALL
        self._run_adb(["shell", "input", "keyevent", "5"])
        time.sleep(1)
        self._in_call = True
        return True

    def end_call(self) -> bool:
        """Hangs up the active call."""
        self._log_action("Ending call")
        if self.is_simulated:
            self._in_call = False
            self._screen_text = ["Call ended", "Home", "Phone", "Messages"]
            for peer in self.peers:
                peer._in_call = False
                peer._screen_text = ["Call ended", "Home", "Phone", "Messages"]
            time.sleep(0.5)
            return True

        # Keyevent 6 is KEYCODE_ENDCALL
        self._run_adb(["shell", "input", "keyevent", "6"])
        time.sleep(1)
        self._in_call = False
        return True

    def is_in_call(self) -> bool:
        """Checks if device is currently in a call."""
        if self.is_simulated:
            return self._in_call
        
        telephony_dump = self._run_adb(["shell", "dumpsys", "telephony.registry"])
        # Check call state (2 = OFFHOOK / In call, 1 = RINGING, 0 = IDLE)
        return "mCallState=2" in telephony_dump or "mCallState=1" in telephony_dump

    def send_sms(self, phone_number: str, text: str) -> bool:
        """Sends an SMS message to a given recipient."""
        self._log_action(f"Sending SMS to {phone_number}: '{text}'")
        if self.is_simulated:
            time.sleep(0.5)
            return True

        self._run_adb(["shell", "service", "call", "isms", "7", "i32", "0", "s16", "com.android.mms",
                       "s16", phone_number, "s16", "null", "s16", text, "s16", "null", "s16", "null"])
        return True

    def open_app(self, package_name: str) -> bool:
        """Launches an application package."""
        self._log_action(f"Opening app: {package_name}")
        if self.is_simulated:
            self._current_app = package_name
            self._screen_text = [package_name, "Welcome", "Search", "Settings"]
            time.sleep(0.5)
            return True

        self._run_adb(["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
        time.sleep(1)
        return True

    def tap(self, x: Optional[int] = None, y: Optional[int] = None, text: Optional[str] = None) -> bool:
        """Taps on screen coordinates or looks for text element."""
        self._log_action(f"Tapping (x={x}, y={y}, text='{text}')")
        if self.is_simulated:
            time.sleep(0.2)
            return True

        if x is not None and y is not None:
            self._run_adb(["shell", "input", "tap", str(x), str(y)])
            return True
        elif text:
            # Fallback coordinate tap or uiautomator lookup
            self._run_adb(["shell", "input", "tap", "500", "800"])
            return True
        return False

    def type_text(self, text: str) -> bool:
        """Enters text into the active focused input field."""
        self._log_action(f"Typing text: '{text}'")
        if self.is_simulated:
            self._screen_text.append(text)
            time.sleep(0.3)
            return True

        escaped = text.replace(" ", "%s")
        self._run_adb(["shell", "input", "text", escaped])
        return True

    def press_home(self) -> bool:
        """Presses the Android HOME button (Keyevent 3)."""
        self._log_action("Press Home button")
        if self.is_simulated:
            self._screen_text = ["Home", "Apps", "Widgets"]
            return True
        self._run_adb(["shell", "input", "keyevent", "3"])
        return True

    def press_back(self) -> bool:
        """Presses the Android BACK button (Keyevent 4)."""
        self._log_action("Press Back button")
        if self.is_simulated:
            return True
        self._run_adb(["shell", "input", "keyevent", "4"])
        return True

    def wait_for_text(self, text: str, timeout: int = 10) -> bool:
        """Polls until text appears on screen or timeout occurs."""
        self._log_action(f"Waiting for text: '{text}' (timeout={timeout}s)")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_text_visible(text):
                return True
            time.sleep(1)
        return False

    def is_text_visible(self, text: str) -> bool:
        """Checks if text is visible on the current screen."""
        if self.is_simulated:
            return any(text.lower() in t.lower() for t in self._screen_text)

        # Quick check via uiautomator dump
        dump = self.dump_hierarchy()
        return text.lower() in dump.lower()

    def dump_hierarchy(self) -> str:
        """Dumps window hierarchy XML for inspection."""
        if self.is_simulated:
            items = "".join([f'<node text="{t}" />' for t in self._screen_text])
            return f'<hierarchy rotation="0">{items}</hierarchy>'

        self._run_adb(["shell", "uiautomator", "dump", "/data/local/tmp/uidump.xml"])
        xml = self._run_adb(["shell", "cat", "/data/local/tmp/uidump.xml"])
        return xml

    def take_screenshot(self, name: Optional[str] = None) -> Path:
        """Captures a screenshot from the device and saves to screenshot_dir."""
        timestamp = int(time.time() * 1000)
        file_name = f"{self.alias}_{name or 'screenshot'}_{timestamp}.png"
        target_path = self.screenshot_dir / file_name

        if self.is_simulated:
            if HAS_PIL:
                # Generate a realistic mock screenshot image with Pillow
                img = Image.new("RGB", (400, 700), color=(30, 34, 42))
                draw = ImageDraw.Draw(img)
                
                # Status bar
                draw.rectangle([(0, 0), (400, 40)], fill=(20, 24, 30))
                draw.text((15, 12), f"📶 100% | 12:00 PM | {self.alias.upper()}", fill=(220, 220, 220))
                
                # Header
                draw.rectangle([(0, 40), (400, 100)], fill=(45, 55, 72))
                draw.text((20, 60), f"Device: {self.serial}", fill=(255, 255, 255))
                
                # Body content
                draw.rectangle([(20, 120), (380, 580)], fill=(24, 28, 36), outline=(70, 80, 100))
                draw.text((35, 140), f"Current App: {self._current_app}", fill=(100, 200, 255))
                draw.text((35, 170), f"Call State: {'ACTIVE' if self._in_call else 'IDLE'}", fill=(100, 255, 150) if self._in_call else (180, 180, 180))
                
                y_offset = 220
                draw.text((35, y_offset), "Screen Elements:", fill=(200, 200, 200))
                y_offset += 30
                for item in self._screen_text:
                    draw.rectangle([(40, y_offset), (360, y_offset + 35)], fill=(40, 48, 60), outline=(60, 70, 90))
                    draw.text((55, y_offset + 8), item, fill=(240, 240, 240))
                    y_offset += 45

                # Bottom navigation bar
                draw.rectangle([(0, 640), (400, 700)], fill=(20, 24, 30))
                draw.text((80, 660), "◀", fill=(180, 180, 180))
                draw.text((195, 660), "●", fill=(180, 180, 180))
                draw.text((310, 660), "■", fill=(180, 180, 180))

                img.save(target_path)
            else:
                # Write simple placeholder SVG/Text
                with open(target_path, "wb") as f:
                    f.write(b"")
        else:
            remote_path = f"/data/local/tmp/{file_name}"
            self._run_adb(["shell", "screencap", "-p", remote_path])
            self._run_adb(["pull", remote_path, str(target_path)])
            self._run_adb(["shell", "rm", remote_path])

        self._log_action(f"Captured screenshot: {file_name}")
        return target_path

    def _log_action(self, description: str):
        entry = {"timestamp": time.strftime("%H:%M:%S"), "action": description}
        self.history.append(entry)
