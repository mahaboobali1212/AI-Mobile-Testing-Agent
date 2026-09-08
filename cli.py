"""
Command-line interface (CLI) for AI Mobile Testing Agent.
"""

import sys
import argparse
import subprocess
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import TESTS_GENERATED_DIR
from core.device_manager import DeviceManager
from core.script_generator import ScriptGenerator
from core.sandbox_runner import SandboxRunner
from core.result_analyzer import ResultAnalyzer


def cmd_devices(args):
    dm = DeviceManager()
    devices = dm.list_connected_devices()
    avds = dm.list_available_avds()

    print("\n📱 Connected ADB Devices / Emulators:")
    print("=" * 50)
    if not devices:
        print("  (No physical devices or active emulators found)")
    else:
        for d in devices:
            print(f"  • Serial: {d['serial']:<20} State: {d['state']:<10} Model: {d['model']}")

    print("\n📲 Available Android Virtual Devices (AVDs):")
    print("=" * 50)
    if not avds:
        print("  (No AVDs found)")
    else:
        for avd in avds:
            print(f"  • {avd}")
    print()


def cmd_generate(args):
    prompt = args.prompt
    name = args.name
    print(f"\n🤖 Generating test script for scenario:\n  \"{prompt}\"\n")
    
    generator = ScriptGenerator()
    script_path, code = generator.generate_script(prompt, test_name=name)
    print(f"✅ Test script successfully generated and saved to:")
    print(f"   📁 {script_path}\n")
    print("-" * 50)
    print(code)
    print("-" * 50)

    if args.execute:
        print("\n🚀 Executing generated script immediately in Sandbox...")
        runner = SandboxRunner()
        analyzer = ResultAnalyzer()
        summary = runner.run_script(script_path)
        report_path = analyzer.analyze_and_report(summary)
        print(f"\n🏁 Result: {summary['status']} (Duration: {summary['total_duration']}s)")
        print(f"📊 Report generated at: {report_path}\n")


def cmd_run(args):
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"❌ Error: Script not found at {script_path}")
        sys.exit(1)

    print(f"\n⚡ Running test script: {script_path.name} in Sandbox...")
    runner = SandboxRunner()
    analyzer = ResultAnalyzer()
    summary = runner.run_script(script_path)
    report_path = analyzer.analyze_and_report(summary)

    print(f"\n🏁 Result: {summary['status']} (Duration: {summary['total_duration']}s)")
    print(f"📄 Full HTML Report: {report_path}\n")


def cmd_list_tests(args):
    tests = list(TESTS_GENERATED_DIR.glob("test_*.py"))
    print("\n💾 Saved Reusable Test Scripts:")
    print("=" * 50)
    if not tests:
        print("  (No saved test scripts yet)")
    else:
        for t in tests:
            print(f"  • {t.name} ({t.stat().st_size} bytes)")
    print()


def cmd_web(args):
    print("\n🌐 Launching Streamlit Web Dashboard...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "web/app.py"])


def main():
    parser = argparse.ArgumentParser(description="AI Mobile Testing Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # devices
    subparsers.add_parser("devices", help="List connected ADB devices and available AVDs")

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate a Python test script from prompt")
    gen_p.add_argument("prompt", type=str, help="Natural language test scenario description")
    gen_p.add_argument("--name", type=str, default=None, help="Custom filename for test")
    gen_p.add_argument("--execute", action="store_true", help="Execute immediately after generation")

    # run
    run_p = subparsers.add_parser("run", help="Run an existing test script in the sandbox")
    run_p.add_argument("script", type=str, help="Path to Python test script")

    # list-tests
    subparsers.add_parser("list-tests", help="List all saved reusable test scripts")

    # web
    subparsers.add_parser("web", help="Launch Streamlit web dashboard")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "devices": cmd_devices,
        "generate": cmd_generate,
        "run": cmd_run,
        "list-tests": cmd_list_tests,
        "web": cmd_web,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
