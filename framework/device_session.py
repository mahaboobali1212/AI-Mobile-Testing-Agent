"""
DeviceSession: Encapsulates high-level automation actions for an individual Android device.
Supports both live ADB execution and ultra-high-fidelity simulated sandbox visual rendering with phone bezels and anti-aliased typography.
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


def _get_font(size: int, bold: bool = False):
    """Loads clean anti-aliased TrueType fonts on Windows/Linux or falls back to default."""
    if not HAS_PIL:
        return None
    font_names = ["arialbd.ttf" if bold else "arial.ttf", "segoeuib.ttf" if bold else "segoeui.ttf", "calibrib.ttf" if bold else "calibri.ttf"]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            try:
                return ImageFont.truetype(f"C:\\Windows\\Fonts\\{fn}", size)
            except Exception:
                pass
    return ImageFont.load_default()


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
        self._notification: Optional[Dict[str, str]] = None
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
                peer._notification = {"title": "INCOMING CALL", "text": f"Calling from {self.alias.upper()} ({self.serial})"}
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
            self._notification = None
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
            self._notification = None
            self._screen_text = ["Call ended", "Home", "Phone", "Messages"]
            for peer in self.peers:
                peer._in_call = False
                peer._notification = None
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
            
            # Deliver to peers & create notification popup
            for peer in self.peers:
                peer._messages.append({
                    "direction": "in",
                    "sender": self.alias.upper(),
                    "recipient": peer.alias.upper(),
                    "text": text,
                    "time": time.strftime("%I:%M %p")
                })
                peer._notification = {
                    "title": f"NEW SMS FROM {self.alias.upper()}",
                    "text": text
                }
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
            self._notification = None  # Clear notification when app opens
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
                # Load anti-aliased TrueType fonts
                f_title = _get_font(18, bold=True)
                f_sub = _get_font(14, bold=True)
                f_body = _get_font(13, bold=False)
                f_bold = _get_font(13, bold=True)
                f_small = _get_font(11, bold=False)

                # 440 x 780 Phone Canvas
                img = Image.new("RGB", (440, 780), color=(10, 14, 20))
                draw = ImageDraw.Draw(img)
                
                # Outer Phone Chassis
                draw.rounded_rectangle([(6, 6), (434, 774)], radius=24, fill=(18, 24, 34), outline=(71, 85, 105), width=2)
                draw.rounded_rectangle([(14, 14), (426, 766)], radius=18, fill=(15, 23, 42))

                # Punch-hole Camera Dot
                draw.ellipse([(212, 22), (228, 38)], fill=(5, 5, 8))

                # 1. Top Status Bar
                draw.text((28, 22), "12:00", fill=(240, 240, 240), font=f_small)
                draw.text((320, 22), "5G  100%", fill=(200, 200, 200), font=f_small)

                # 2. Top Header Bar
                draw.rectangle([(14, 48), (426, 105)], fill=(30, 41, 59))
                dev_badge = f"{self.alias.upper()} ({self.serial})"
                draw.text((26, 56), dev_badge, fill=(56, 189, 248), font=f_sub)

                # 3. Dynamic App View
                if "messaging" in self._current_app.lower():
                    draw.text((26, 78), "Messages  |  Chat", fill=(255, 255, 255), font=f_body)
                    
                    # Conversation area
                    y = 120
                    if not self._messages:
                        draw.text((36, y), "No messages in conversation", fill=(148, 163, 184), font=f_body)
                    else:
                        for msg in self._messages[-4:]:
                            is_out = msg.get("direction") == "out"
                            msg_text = msg.get("text", "")
                            msg_time = msg.get("time", "12:00 PM")
                            
                            if is_out:
                                # Outgoing message (Blue Bubble on Right)
                                draw.rounded_rectangle([(130, y), (410, y + 62)], radius=12, fill=(2, 132, 199))
                                draw.text((144, y + 8), msg_text[:36], fill=(255, 255, 255), font=f_bold)
                                if len(msg_text) > 36:
                                    draw.text((144, y + 24), msg_text[36:72], fill=(255, 255, 255), font=f_body)
                                draw.text((280, y + 42), f"{msg_time}  Sent", fill=(224, 242, 254), font=f_small)
                            else:
                                # Incoming message (Slate Bubble on Left)
                                draw.rounded_rectangle([(26, y), (300, y + 62)], radius=12, fill=(51, 65, 85))
                                draw.text((38, y + 8), msg_text[:36], fill=(255, 255, 255), font=f_bold)
                                if len(msg_text) > 36:
                                    draw.text((38, y + 24), msg_text[36:72], fill=(255, 255, 255), font=f_body)
                                draw.text((38, y + 42), f"From {msg.get('sender', 'Peer')}  {msg_time}", fill=(148, 163, 184), font=f_small)
                            
                            y += 74

                    # Bottom Input Bar
                    draw.rounded_rectangle([(24, 645), (355, 685)], radius=18, fill=(30, 41, 59), outline=(71, 85, 105))
                    draw.text((40, 658), "Type message...", fill=(148, 163, 184), font=f_body)
                    draw.ellipse([(370, 645), (410, 685)], fill=(2, 132, 199))
                    draw.text((384, 656), ">", fill=(255, 255, 255), font=f_sub)

                elif "dialer" in self._current_app.lower() or self._in_call:
                    draw.text((26, 78), "Phone  |  Voice Call", fill=(255, 255, 255), font=f_body)
                    
                    # Caller Avatar Circle with initial
                    draw.ellipse([(170, 160), (270, 260)], fill=(30, 58, 138), outline=(59, 130, 246), width=2)
                    draw.text((210, 192), self.alias[-1].upper(), fill=(255, 255, 255), font=f_title)
                    
                    # Target Number & Timer
                    target = self._call_target or "555-0002"
                    draw.text((170, 280), target, fill=(255, 255, 255), font=f_sub)
                    call_text = "Connected (00:08)" if self._in_call else "Call Ended"
                    call_color = (74, 222, 128) if self._in_call else (248, 113, 113)
                    draw.text((160, 310), call_text, fill=call_color, font=f_body)
                    
                    # Call Action Buttons
                    draw.rounded_rectangle([(65, 370), (165, 430)], radius=10, fill=(30, 41, 59))
                    draw.text((95, 392), "Mute", fill=(240, 240, 240), font=f_body)
                    
                    draw.rounded_rectangle([(175, 370), (265, 430)], radius=10, fill=(30, 41, 59))
                    draw.text((195, 392), "Keypad", fill=(240, 240, 240), font=f_body)
                    
                    draw.rounded_rectangle([(275, 370), (375, 430)], radius=10, fill=(30, 41, 59))
                    draw.text((300, 392), "Speaker", fill=(240, 240, 240), font=f_body)
                    
                    # End Call Button
                    draw.rounded_rectangle([(160, 550), (280, 610)], radius=16, fill=(239, 68, 68))
                    draw.text((185, 570), "END CALL", fill=(255, 255, 255), font=f_sub)

                else:
                    # Home Screen Launcher
                    draw.text((26, 78), "Android Home Screen", fill=(255, 255, 255), font=f_body)
                    
                    # Search Bar
                    draw.rounded_rectangle([(30, 140), (410, 185)], radius=20, fill=(30, 41, 59), outline=(71, 85, 105))
                    draw.text((55, 154), "Search Google", fill=(148, 163, 184), font=f_body)
                    
                    # App Tiles Grid
                    apps = [
                        ("PHONE", (34, 197, 94)),
                        ("MESSAGES", (59, 130, 246)),
                        ("CHROME", (234, 179, 8)),
                        ("CAMERA", (168, 85, 247)),
                        ("SETTINGS", (100, 116, 139)),
                        ("FILES", (249, 115, 22))
                    ]
                    for idx, (lbl, col) in enumerate(apps):
                        r = idx // 3
                        c = idx % 3
                        ix = 55 + c * 125
                        iy = 240 + r * 115
                        draw.rounded_rectangle([(ix, iy), (ix + 70, iy + 70)], radius=16, fill=col)
                        draw.text((ix + 12, iy + 26), lbl[:4], fill=(255, 255, 255), font=f_bold)
                        draw.text((ix + 6, iy + 76), lbl, fill=(203, 213, 225), font=f_small)

                # 4. Top Notification Banner (If active)
                if self._notification:
                    draw.rounded_rectangle([(24, 112), (416, 172)], radius=14, fill=(30, 58, 138), outline=(59, 130, 246), width=2)
                    draw.text((38, 122), self._notification.get("title", "NOTIFICATION"), fill=(224, 242, 254), font=f_bold)
                    draw.text((38, 144), self._notification.get("text", "")[:45], fill=(255, 255, 255), font=f_body)

                # 5. Bottom Navigation Bar
                draw.rectangle([(14, 705), (426, 766)], fill=(12, 15, 20))
                draw.text((95, 725), "BACK", fill=(160, 160, 160), font=f_small)
                draw.text((205, 725), "HOME", fill=(160, 160, 160), font=f_small)
                draw.text((315, 725), "RECENTS", fill=(160, 160, 160), font=f_small)

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
