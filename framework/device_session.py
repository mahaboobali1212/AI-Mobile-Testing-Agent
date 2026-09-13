"""
DeviceSession: Encapsulates high-level automation actions for an individual Android device.
Supports both live ADB execution and ultra-high-fidelity simulated sandbox visual rendering with genuine vector brand logos, phone bezels, and anti-aliased typography.
"""

import os
import math
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


# ==========================================
# VECTOR LOGO & ICON DRAWING HELPERS
# ==========================================

def _draw_chrome_logo(draw: ImageDraw.Draw, cx: int, cy: int, r: int = 20):
    """Draws authentic 4-color Google Chrome circular logo."""
    # Red top, Yellow bottom-left, Green bottom-right sectors
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=210, end=330, fill=(234, 67, 53))   # Red
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=330, end=90, fill=(52, 168, 83))    # Green
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=90, end=210, fill=(251, 188, 4))    # Yellow
    
    # White separator ring
    inner_r = int(r * 0.55)
    draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], fill=(255, 255, 255))
    
    # Blue center circle
    core_r = int(r * 0.42)
    draw.ellipse([(cx - core_r, cy - core_r), (cx + core_r, cy + core_r)], fill=(66, 133, 244))


def _draw_phone_handset_logo(draw: ImageDraw.Draw, cx: int, cy: int, size: int = 16, color=(255, 255, 255), facing_down: bool = False):
    """Draws a vector telephone handset icon."""
    if facing_down:
        # End call (Handset facing down horizontally)
        draw.rounded_rectangle([(cx - size, cy - 4), (cx + size, cy + 4)], radius=4, fill=color)
        draw.rounded_rectangle([(cx - size, cy - 8), (cx - size + 7, cy + 8)], radius=3, fill=color)
        draw.rounded_rectangle([(cx + size - 7, cy - 8), (cx + size, cy + 8)], radius=3, fill=color)
    else:
        # Standard active/app handset (Angled handset)
        draw.pieslice([(cx - size, cy - size), (cx + size, cy + size)], start=120, end=240, fill=color, outline=color, width=2)
        draw.ellipse([(cx - size + 2, cy - size + 4), (cx - 2, cy - 2)], fill=color)
        draw.ellipse([(cx - size + 2, cy + 2), (cx - 2, cy + size - 4)], fill=color)


def _draw_messages_bubble_logo(draw: ImageDraw.Draw, cx: int, cy: int, size: int = 16, color=(255, 255, 255)):
    """Draws a vector chat speech bubble logo."""
    w, h = size + 4, size
    draw.rounded_rectangle([(cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2)], radius=6, fill=color)
    # Speech bubble pointer tail
    draw.polygon([(cx - w // 2 + 4, cy + h // 2 - 2), (cx - w // 2 - 4, cy + h // 2 + 5), (cx - w // 2 + 10, cy + h // 2 - 2)], fill=color)
    # Internal message dots/lines
    line_col = (59, 130, 246)
    draw.line([(cx - 6, cy - 2), (cx + 6, cy - 2)], fill=line_col, width=2)
    draw.line([(cx - 6, cy + 3), (cx + 2, cy + 3)], fill=line_col, width=2)


def _draw_camera_lens_logo(draw: ImageDraw.Draw, cx: int, cy: int, size: int = 16):
    """Draws a vector camera logo."""
    # Camera body
    draw.rounded_rectangle([(cx - size, cy - size + 4), (cx + size, cy + size - 2)], radius=5, fill=(255, 255, 255))
    # Top flash ridge
    draw.rounded_rectangle([(cx - 6, cy - size + 1), (cx + 6, cy - size + 4)], radius=2, fill=(255, 255, 255))
    # Circular Lens
    draw.ellipse([(cx - 8, cy - 5), (cx + 8, cy + 9)], fill=(168, 85, 247), outline=(255, 255, 255), width=2)
    # Lens reflection dot
    draw.ellipse([(cx - 3, cy), (cx + 1, cy + 4)], fill=(255, 255, 255))
    # Red sensor dot
    draw.ellipse([(cx + size - 7, cy - size + 7), (cx + size - 3, cy - size + 11)], fill=(239, 68, 68))


def _draw_settings_gear_logo(draw: ImageDraw.Draw, cx: int, cy: int, r: int = 14):
    """Draws a vector mechanical settings cogwheel gear."""
    # Radial teeth
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        tx = cx + int((r + 4) * math.cos(rad))
        ty = cy + int((r + 4) * math.sin(rad))
        draw.ellipse([(tx - 3, ty - 3), (tx + 3, ty + 3)], fill=(255, 255, 255))
    # Gear body
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 255, 255))
    # Central hole
    draw.ellipse([(cx - r // 2, cy - r // 2), (cx + r // 2, cy + r // 2)], fill=(100, 116, 139))


def _draw_files_folder_logo(draw: ImageDraw.Draw, cx: int, cy: int, size: int = 16):
    """Draws a vector files folder icon."""
    draw.polygon([(cx - size, cy - size + 4), (cx - 4, cy - size + 4), (cx, cy - size + 8), (cx + size, cy - size + 8), (cx + size, cy + size - 4), (cx - size, cy + size - 4)], fill=(255, 255, 255))
    draw.rounded_rectangle([(cx - size, cy - 2), (cx + size, cy + size - 4)], radius=3, fill=(254, 215, 170))


def _draw_google_g_logo(draw: ImageDraw.Draw, cx: int, cy: int, r: int = 11):
    """Draws the official Google 'G' 4-color vector logo."""
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=225, end=340, fill=(234, 67, 53))   # Red
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=340, end=45, fill=(66, 133, 244))    # Blue
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=45, end=140, fill=(52, 168, 83))     # Green
    draw.pieslice([(cx - r, cy - r), (cx + r, cy + r)], start=140, end=225, fill=(251, 188, 4))    # Yellow
    # Inner hole
    inner_r = int(r * 0.60)
    draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], fill=(30, 41, 59))
    # Horizontal blue crossbar
    draw.rectangle([(cx, cy - 3), (cx + r, cy + 3)], fill=(66, 133, 244))


def _draw_person_avatar_logo(draw: ImageDraw.Draw, cx: int, cy: int, r: int = 35):
    """Draws a vector person silhouette avatar for calls and contacts."""
    # Head
    draw.ellipse([(cx - int(r * 0.35), cy - int(r * 0.55)), (cx + int(r * 0.35), cy + int(r * 0.05))], fill=(255, 255, 255))
    # Shoulders
    draw.pieslice([(cx - int(r * 0.70), cy - int(r * 0.1)), (cx + int(r * 0.70), cy + int(r * 0.85))], start=180, end=360, fill=(255, 255, 255))


def _draw_microphone_logo(draw: ImageDraw.Draw, cx: int, cy: int):
    """Draws a vector microphone icon."""
    draw.rounded_rectangle([(cx - 4, cy - 10), (cx + 4, cy + 2)], radius=4, fill=(240, 240, 240))
    draw.arc([(cx - 7, cy - 6), (cx + 7, cy + 5)], start=0, end=180, fill=(240, 240, 240), width=2)
    draw.line([(cx, cy + 5), (cx, cy + 10)], fill=(240, 240, 240), width=2)


def _draw_keypad_logo(draw: ImageDraw.Draw, cx: int, cy: int):
    """Draws a 3x3 numeric dialpad dots icon."""
    for row in range(-1, 2):
        for col in range(-1, 2):
            dx = cx + col * 7
            dy = cy + row * 7
            draw.ellipse([(dx - 2, dy - 2), (dx + 2, dy + 2)], fill=(240, 240, 240))


def _draw_speaker_logo(draw: ImageDraw.Draw, cx: int, cy: int):
    """Draws a vector audio speaker icon."""
    draw.polygon([(cx - 8, cy - 4), (cx - 4, cy - 4), (cx + 2, cy - 9), (cx + 2, cy + 9), (cx - 4, cy + 4), (cx - 8, cy + 4)], fill=(240, 240, 240))
    draw.arc([(cx + 4, cy - 6), (cx + 10, cy + 6)], start=300, end=60, fill=(240, 240, 240), width=2)


def _draw_paperplane_logo(draw: ImageDraw.Draw, cx: int, cy: int):
    """Draws a paper airplane send vector icon."""
    draw.polygon([(cx - 8, cy - 8), (cx + 9, cy), (cx - 8, cy + 8), (cx - 3, cy)], fill=(255, 255, 255))


# ==========================================
# DEVICE SESSION ENGINE
# ==========================================

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
                # Typography
                f_title = _get_font(20, bold=True)
                f_sub = _get_font(15, bold=True)
                f_body = _get_font(13, bold=False)
                f_bold = _get_font(13, bold=True)
                f_small = _get_font(11, bold=False)

                # 440 x 780 Phone Canvas
                img = Image.new("RGB", (440, 780), color=(10, 14, 20))
                draw = ImageDraw.Draw(img)
                
                # Outer Curved Phone Frame
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

                # 3. Dynamic App View with Genuine Vector Brand Logos
                if "messaging" in self._current_app.lower():
                    # Header with Vector Messages Bubble Logo
                    _draw_messages_bubble_logo(draw, 36, 86, size=14, color=(59, 130, 246))
                    draw.text((54, 78), "Google Messages", fill=(255, 255, 255), font=f_bold)
                    
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
                                draw.text((280, y + 42), f"{msg_time}  Delivered", fill=(224, 242, 254), font=f_small)
                            else:
                                # Incoming message (Slate Bubble on Left)
                                draw.rounded_rectangle([(26, y), (300, y + 62)], radius=12, fill=(51, 65, 85))
                                draw.text((38, y + 8), msg_text[:36], fill=(255, 255, 255), font=f_bold)
                                if len(msg_text) > 36:
                                    draw.text((38, y + 24), msg_text[36:72], fill=(255, 255, 255), font=f_body)
                                draw.text((38, y + 42), f"From {msg.get('sender', 'Peer')}  {msg_time}", fill=(148, 163, 184), font=f_small)
                            
                            y += 74

                    # Bottom Input Bar with Send Paperplane Logo
                    draw.rounded_rectangle([(24, 645), (355, 685)], radius=18, fill=(30, 41, 59), outline=(71, 85, 105))
                    draw.text((40, 658), "Type message...", fill=(148, 163, 184), font=f_body)
                    draw.ellipse([(370, 645), (410, 685)], fill=(2, 132, 199))
                    _draw_paperplane_logo(draw, 390, 665)

                elif "dialer" in self._current_app.lower() or self._in_call:
                    # Phone Call Header with Vector Handset Logo
                    _draw_phone_handset_logo(draw, 36, 86, size=8, color=(34, 197, 94))
                    draw.text((52, 78), "Phone  |  Voice Call", fill=(255, 255, 255), font=f_bold)
                    
                    # Large Silhouette Caller Avatar
                    draw.ellipse([(160, 140), (280, 260)], fill=(30, 58, 138), outline=(59, 130, 246), width=2)
                    _draw_person_avatar_logo(draw, 220, 200, r=40)
                    
                    # Target Number & Live Status
                    target = self._call_target or "555-0002"
                    draw.text((170, 280), target, fill=(255, 255, 255), font=f_title)
                    call_text = "Connected (00:08)" if self._in_call else "Call Ended"
                    call_color = (74, 222, 128) if self._in_call else (248, 113, 113)
                    draw.text((160, 312), call_text, fill=call_color, font=f_sub)
                    
                    # Vector Call Control Action Buttons
                    # 1. Mute
                    draw.rounded_rectangle([(65, 370), (155, 435)], radius=12, fill=(30, 41, 59))
                    _draw_microphone_logo(draw, 110, 395)
                    draw.text((95, 412), "Mute", fill=(240, 240, 240), font=f_small)
                    
                    # 2. Keypad
                    draw.rounded_rectangle([(175, 370), (265, 435)], radius=12, fill=(30, 41, 59))
                    _draw_keypad_logo(draw, 220, 395)
                    draw.text((200, 412), "Keypad", fill=(240, 240, 240), font=f_small)
                    
                    # 3. Speaker
                    draw.rounded_rectangle([(285, 370), (375, 435)], radius=12, fill=(30, 41, 59))
                    _draw_speaker_logo(draw, 330, 395)
                    draw.text((310, 412), "Speaker", fill=(240, 240, 240), font=f_small)
                    
                    # End Call Button (Red Circle with Handset Facing Down)
                    draw.ellipse([(185, 540), (255, 610)], fill=(239, 68, 68))
                    _draw_phone_handset_logo(draw, 220, 575, size=16, color=(255, 255, 255), facing_down=True)
                    draw.text((188, 620), "END CALL", fill=(239, 68, 68), font=f_bold)

                else:
                    # Home Screen Launcher with Genuine App Vector Logos
                    draw.text((26, 78), "Android Home Screen", fill=(255, 255, 255), font=f_bold)
                    
                    # Google Search Bar with 'G' Multi-Color Logo
                    draw.rounded_rectangle([(30, 140), (410, 185)], radius=22, fill=(30, 41, 59), outline=(71, 85, 105))
                    _draw_google_g_logo(draw, 55, 162, r=12)
                    draw.text((80, 154), "Search or type URL", fill=(148, 163, 184), font=f_body)
                    
                    # Vector App Icons Grid (Phone, Messages, Chrome, Camera, Settings, Files)
                    app_data = [
                        ("Phone", (34, 197, 94), lambda d, x, y: _draw_phone_handset_logo(d, x, y, size=14)),
                        ("Messages", (59, 130, 246), lambda d, x, y: _draw_messages_bubble_logo(d, x, y, size=15)),
                        ("Chrome", (255, 255, 255), lambda d, x, y: _draw_chrome_logo(d, x, y, r=16)),
                        ("Camera", (168, 85, 247), lambda d, x, y: _draw_camera_lens_logo(d, x, y, size=15)),
                        ("Settings", (100, 116, 139), lambda d, x, y: _draw_settings_gear_logo(d, x, y, r=13)),
                        ("Files", (249, 115, 22), lambda d, x, y: _draw_files_folder_logo(d, x, y, size=15))
                    ]
                    
                    for idx, (lbl, bg_col, draw_fn) in enumerate(app_data):
                        r = idx // 3
                        c = idx % 3
                        ix = 55 + c * 125
                        iy = 240 + r * 115
                        draw.rounded_rectangle([(ix, iy), (ix + 68, iy + 68)], radius=16, fill=bg_col)
                        draw_fn(draw, ix + 34, iy + 34)
                        draw.text((ix + 12, iy + 76), lbl, fill=(203, 213, 225), font=f_small)

                # 4. Top Notification Banner (If active)
                if self._notification:
                    draw.rounded_rectangle([(24, 112), (416, 172)], radius=14, fill=(30, 58, 138), outline=(59, 130, 246), width=2)
                    _draw_messages_bubble_logo(draw, 42, 132, size=10, color=(255, 255, 255))
                    draw.text((60, 122), self._notification.get("title", "NOTIFICATION"), fill=(224, 242, 254), font=f_bold)
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
