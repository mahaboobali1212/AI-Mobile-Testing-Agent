"""
DeviceSession: Encapsulates high-level automation actions for an individual Android device.
Supports both live ADB execution and high-fidelity simulated sandbox visual rendering.
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
        self._call_target = ""
        self._current_app = "com.google.android.apps.nexuslauncher"
        self._screen_text = ["Home", "Phone", "Messages", "Chrome", "Camera"]
        self._messages: List[Dict[str, str]] = []
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
            self._call_target = phone_number
            self._current_app = "com.google.android.dialer"
            self._screen_text = ["Calling...", phone_number, "Mute", "Keypad", "Speaker", "End Call"]
            for peer in self.peers:
                peer._in_call = True
                peer._call_target = self.serial
                peer._current_app = "com.google.android.dialer"
                peer._screen_text = ["Incoming Call...", f"From: {self.serial}", "Answer", "Decline"]
            time.sleep(0.5)
            return True

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

        self._run_adb(["shell", "input", "keyevent", "6"])
        time.sleep(1)
        self._in_call = False
        return True

    def is_in_call(self) -> bool:
        """Checks if device is currently in a call."""
        if self.is_simulated:
            return self._in_call
        
        telephony_dump = self._run_adb(["shell", "dumpsys", "telephony.registry"])
        return "mCallState=2" in telephony_dump or "mCallState=1" in telephony_dump

    def send_sms(self, phone_number: str, text: str) -> bool:
        """Sends an SMS message to a given recipient."""
        self._log_action(f"Sending SMS to {phone_number}: '{text}'")
        if self.is_simulated:
            self._current_app = "com.google.android.apps.messaging"
            self._messages.append({
                "direction": "out",
                "sender": self.alias.upper(),
                "recipient": phone_number,
                "text": text,
                "time": time.strftime("%I:%M %p")
            })
            self._screen_text = ["Messages", f"To: {phone_number}", text, "Sent • Delivered"]
            
            # Send into peers' inbox
            for peer in self.peers:
                peer._messages.append({
                    "direction": "in",
                    "sender": self.alias.upper(),
                    "recipient": peer.alias.upper(),
                    "text": text,
                    "time": time.strftime("%I:%M %p")
                })
                peer._screen_text.append(text)
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
            if "messaging" in package_name:
                self._screen_text = ["Messages", "Conversations", "Start chat"] + [m["text"] for m in self._messages]
            elif "chrome" in package_name:
                self._screen_text = ["Chrome", "Search or type URL", "Google", "Bookmarks"]
            else:
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
            self._current_app = "com.google.android.apps.nexuslauncher"
            self._screen_text = ["Home", "Apps", "Widgets", "Phone", "Messages", "Chrome"]
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
                # Generate a high-fidelity visual mock screenshot image with Pillow
                img = Image.new("RGB", (420, 750), color=(18, 22, 28))
                draw = ImageDraw.Draw(img)
                
                # 1. Status Bar (Top)
                draw.rectangle([(0, 0), (420, 36)], fill=(12, 15, 20))
                draw.text((16, 10), "12:00", fill=(240, 240, 240))
                draw.text((310, 10), "📶 5G  🔋 98%", fill=(200, 200, 200))

                # 2. App Header
                draw.rectangle([(0, 36), (420, 95)], fill=(30, 41, 59))
                dev_badge = f"[{self.alias.upper()}] {self.serial}"
                draw.text((16, 46), dev_badge, fill=(56, 189, 248))

                # 3. Dynamic Screen Rendering according to active app
                if "messaging" in self._current_app.lower() or len(self._messages) > 0:
                    # Header for Messages
                    draw.text((16, 68), "💬 Google Messages", fill=(255, 255, 255))
                    
                    # Chat background
                    draw.rectangle([(10, 105), (410, 675)], fill=(15, 23, 42), outline=(51, 65, 85))
                    
                    # Render Chat Bubbles
                    y = 125
                    if not self._messages:
                        draw.text((30, y), "No recent messages in conversation", fill=(148, 163, 184))
                    else:
                        for msg in self._messages[-4:]:
                            is_out = msg.get("direction") == "out"
                            msg_text = msg.get("text", "")
                            msg_time = msg.get("time", "12:00 PM")
                            
                            if is_out:
                                # Outgoing Message (Right-aligned, Blue Bubble)
                                draw.rounded_rectangle([(140, y), (395, y + 60)], radius=12, fill=(2, 132, 199))
                                draw.text((155, y + 10), msg_text[:32], fill=(255, 255, 255))
                                if len(msg_text) > 32:
                                    draw.text((155, y + 26), msg_text[32:64], fill=(255, 255, 255))
                                draw.text((280, y + 42), f"{msg_time} • Sent ✓✓", fill=(224, 242, 254))
                            else:
                                # Incoming Message (Left-aligned, Slate Gray Bubble)
                                draw.rounded_rectangle([(25, y), (280, y + 60)], radius=12, fill=(51, 65, 85))
                                draw.text((40, y + 10), msg_text[:32], fill=(255, 255, 255))
                                if len(msg_text) > 32:
                                    draw.text((40, y + 26), msg_text[32:64], fill=(255, 255, 255))
                                draw.text((40, y + 42), f"From {msg.get('sender', 'Peer')} • {msg_time}", fill=(148, 163, 184))
                            
                            y += 75

                    # Bottom Chat Input Bar
                    draw.rectangle([(20, 625), (340, 665)], fill=(30, 41, 59), outline=(71, 85, 105))
                    draw.text((35, 638), "Type SMS message...", fill=(148, 163, 184))
                    draw.ellipse([(355, 625), (395, 665)], fill=(2, 132, 199))
                    draw.text((370, 637), "➤", fill=(255, 255, 255))

                elif "dialer" in self._current_app.lower() or self._in_call:
                    # Phone Call UI
                    draw.text((16, 68), "📞 Phone • Ongoing Call", fill=(255, 255, 255))
                    draw.rectangle([(10, 105), (410, 675)], fill=(15, 23, 42), outline=(51, 65, 85))
                    
                    # Caller Avatar
                    draw.ellipse([(160, 150), (260, 250)], fill=(30, 58, 138), outline=(59, 130, 246))
                    draw.text((195, 185), "👤", fill=(255, 255, 255))
                    
                    # Call Info
                    target = self._call_target or "555-0002"
                    draw.text((150, 275), target, fill=(255, 255, 255))
                    call_state_text = "Call in progress (00:07)" if self._in_call else "Call Ended"
                    call_state_color = (74, 222, 128) if self._in_call else (248, 113, 113)
                    draw.text((135, 305), call_state_text, fill=call_state_color)
                    
                    # Action Buttons Grid
                    draw.rounded_rectangle([(60, 360), (160, 420)], radius=8, fill=(30, 41, 59))
                    draw.text((95, 382), "🎤 Mute", fill=(240, 240, 240))
                    
                    draw.rounded_rectangle([(180, 360), (280, 420)], radius=8, fill=(30, 41, 59))
                    draw.text((205, 382), "🔢 Keypad", fill=(240, 240, 240))
                    
                    draw.rounded_rectangle([(300, 360), (380, 420)], radius=8, fill=(30, 41, 59))
                    draw.text((315, 382), "🔊 Speaker", fill=(240, 240, 240))
                    
                    # End Call Button
                    draw.ellipse([(175, 540), (245, 610)], fill=(239, 68, 68))
                    draw.text((200, 565), "☎", fill=(255, 255, 255))

                else:
                    # Home Screen UI
                    draw.text((16, 68), "📱 Android Home Launcher", fill=(255, 255, 255))
                    draw.rectangle([(10, 105), (410, 675)], fill=(15, 23, 42), outline=(51, 65, 85))
                    
                    # Google Search Bar Widget
                    draw.rounded_rectangle([(30, 140), (390, 185)], radius=20, fill=(30, 41, 59), outline=(71, 85, 105))
                    draw.text((50, 153), "🔍 Google Search", fill=(148, 163, 184))
                    
                    # App Icons Grid
                    icons = [
                        ("📞", "Phone", (34, 197, 94)),
                        ("💬", "Messages", (59, 130, 246)),
                        ("🌐", "Chrome", (234, 179, 8)),
                        ("📷", "Camera", (168, 85, 247)),
                        ("⚙️", "Settings", (100, 116, 139)),
                        ("📁", "Files", (249, 115, 22))
                    ]
                    
                    for idx, (icon_sym, app_lbl, color) in enumerate(icons):
                        row = idx // 3
                        col = idx % 3
                        ix = 50 + col * 120
                        iy = 240 + row * 110
                        draw.rounded_rectangle([(ix, iy), (ix + 65, iy + 65)], radius=14, fill=color)
                        draw.text((ix + 20, iy + 18), icon_sym, fill=(255, 255, 255))
                        draw.text((ix + 5, iy + 72), app_lbl, fill=(203, 213, 225))

                # 4. Bottom Android Navigation Bar (Back, Home, Recents)
                draw.rectangle([(0, 690), (420, 750)], fill=(12, 15, 20))
                draw.text((90, 712), "◀", fill=(160, 160, 160))
                draw.text((205, 712), "●", fill=(160, 160, 160))
                draw.text((320, 712), "■", fill=(160, 160, 160))

                img.save(target_path)
            else:
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
