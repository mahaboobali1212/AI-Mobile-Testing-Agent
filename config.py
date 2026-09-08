"""
Configuration module for AI-Powered Mobile Testing Agent.
Handles environment variables, ADB path resolution, API keys, and artifact storage.
"""

import os
import shutil
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    if k and k not in os.environ:
                        os.environ[k] = v

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
TESTS_GENERATED_DIR = BASE_DIR / "tests" / "generated"

# Ensure essential directories exist
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
TESTS_GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# Gemini API Key (Can be set via GEMINI_API_KEY environment variable or .env)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Default Timeouts
DEFAULT_COMMAND_TIMEOUT = int(os.getenv("DEFAULT_COMMAND_TIMEOUT", "60"))
DEFAULT_STEP_TIMEOUT = int(os.getenv("DEFAULT_STEP_TIMEOUT", "15"))

# Auto-locate ADB executable
def find_adb_path() -> str:
    # 1. Check if adb is on system PATH
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        return adb_in_path

    # 2. Check standard Android SDK locations on Windows
    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        standard_win_adb = Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
        if standard_win_adb.exists():
            return str(standard_win_adb)

    # 3. Check ANDROID_HOME / ANDROID_SDK_ROOT
    android_home = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
    if android_home:
        candidate = Path(android_home) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if candidate.exists():
            return str(candidate)

    # Fallback to plain 'adb'
    return "adb"

ADB_PATH = find_adb_path()
