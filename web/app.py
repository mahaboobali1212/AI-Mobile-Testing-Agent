"""
Streamlit Web Dashboard for AI-Powered Multi-Device Mobile Testing Agent.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
from config import ARTIFACTS_DIR, TESTS_GENERATED_DIR, ADB_PATH
from core.device_manager import DeviceManager
from core.script_generator import ScriptGenerator
from core.sandbox_runner import SandboxRunner
from core.result_analyzer import ResultAnalyzer

st.set_page_config(
    page_title="AI Mobile Testing Agent",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Dark Modern Dashboard
st.markdown("""
<style>
    .reportview-container { background-color: #0f172a; }
    .main-header { font-size: 28px; font-weight: 800; color: #38bdf8; margin-bottom: 4px; }
    .sub-header { color: #94a3b8; font-size: 14px; margin-bottom: 20px; }
    .card { background-color: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }
    .metric-value { font-size: 26px; font-weight: bold; color: #f8fafc; }
    .metric-label { font-size: 13px; color: #94a3b8; }
</style>
""", unsafe_allow_html=True)

# Initialize engines
dev_mgr = DeviceManager()
generator = ScriptGenerator()
runner = SandboxRunner(dev_mgr)
analyzer = ResultAnalyzer()

# Sidebar: Device Status & Info
with st.sidebar:
    st.markdown("### 📱 Device Pool Status")
    devices = dev_mgr.list_connected_devices()
    avds = dev_mgr.list_available_avds()

    if devices:
        st.success(f"🟢 {len(devices)} ADB Device(s) Online")
        for dev in devices:
            st.markdown(f"• **{dev['serial']}** ({dev['model']})")
    else:
        st.info("ℹ️ No physical devices connected. Simulation mode active.")

    if avds:
        st.markdown("**Installed AVDs:**")
        for avd in avds:
            st.markdown(f"- 📲 `{avd}`")

    st.divider()
    st.markdown(f"**ADB Path:** `{ADB_PATH}`")
    allow_sim = st.checkbox("Allow Virtual Simulation Fallback", value=True)

# Main Title
st.markdown('<div class="main-header">🤖 AI-Powered Multi-Device Mobile Testing Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Author multi-device mobile tests in plain English, execute in isolated sandbox, capture artifacts, and rerun saved test suites.</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["✨ Generate & Run New Test", "💾 Saved Test Catalog & Rerun", "📊 Test Reports & Artifacts"])

# TAB 1: GENERATE & RUN TEST
with tab1:
    col_input, col_code = st.columns([1, 1])

    with col_input:
        st.markdown("#### 1. Describe Test Scenario")
        sample_prompts = [
            "Device A dials Device B (555-0002), Device B answers the call, stay on line for 5s, then Device A hangs up.",
            "Device A sends an SMS 'Hello Device B' to Device B (555-0002), Device B verifies message received, then replies back.",
            "Launch Chrome browser on Device A and Device B, verify home screen is loaded, and return both to home."
        ]
        selected_sample = st.selectbox("Or choose a pre-built scenario template:", ["Custom"] + sample_prompts)
        
        default_val = selected_sample if selected_sample != "Custom" else "Device A calls Device B, Device B accepts the call, wait 5 seconds, then Device A ends the call."
        prompt_text = st.text_area("Test Scenario Prompt (Plain English):", value=default_val, height=130)
        
        custom_test_name = st.text_input("Custom Test Name (Optional):", placeholder="e.g. test_voice_call_flow")
        
        run_btn = st.button("🚀 Generate & Execute Test in Sandbox", type="primary", use_container_width=True)

    if run_btn and prompt_text:
        with st.spinner("🤖 Generating deterministic Python test script with AI..."):
            script_path, code = generator.generate_script(prompt_text, test_name=custom_test_name or None)
            st.success(f"✅ Generated & Saved to `{script_path.name}`")

        with col_code:
            st.markdown(f"#### 2. Generated Python Script (`{script_path.name}`)")
            st.code(code, language="python")

        st.markdown("---")
        st.markdown("#### 3. Sandbox Execution & Live Artifacts")
        progress_bar = st.progress(0, text="Executing in Sandbox...")

        with st.spinner("⚡ Running test script in sandbox..."):
            summary = runner.run_script(script_path, allow_simulation=allow_sim)
            report_path = analyzer.analyze_and_report(summary)
            progress_bar.progress(100, text="Execution Complete!")

        # Display Result Card
        is_pass = summary.get("status") == "PASSED"
        status_color = "#10b981" if is_pass else "#ef4444"
        
        st.markdown(f"""
        <div style="background-color: #1e293b; border-left: 6px solid {status_color}; padding: 16px; border-radius: 8px; margin-top: 10px;">
            <h3 style="margin: 0; color: {status_color};">Status: {summary.get('status')}</h3>
            <p style="margin: 4px 0 0 0; color: #94a3b8;">Total Duration: {summary.get('total_duration')}s | Steps: {len(summary.get('steps', []))}</p>
        </div>
        """, unsafe_allow_html=True)

        if not is_pass and summary.get("ai_diagnosis"):
            st.error(summary["ai_diagnosis"])

        # Display Step-by-Step Screenshots
        st.markdown("##### 📸 Execution Screenshots & Timeline")
        steps = summary.get("steps", [])
        for step in steps:
            with st.expander(f"Step {step['step_index']}: {step['name']} ({step['status']} - {step['duration']}s)", expanded=True):
                if step.get("screenshots"):
                    cols = st.columns(len(step["screenshots"]))
                    for idx, s_name in enumerate(step["screenshots"]):
                        img_path = Path(summary["run_dir"]) / "screenshots" / s_name
                        if img_path.exists():
                            with cols[idx]:
                                st.image(str(img_path), caption=s_name, use_container_width=True)

        st.info(f"📄 Full interactive HTML report generated at: `{report_path}`")

# TAB 2: SAVED TEST CATALOG & RERUN
with tab2:
    st.markdown("#### 💾 Saved Reusable Tests")
    st.caption("Re-run any previously generated test on-demand in the Sandbox without making any AI calls.")

    saved_tests = list(TESTS_GENERATED_DIR.glob("test_*.py"))
    if not saved_tests:
        st.info("No saved test scripts found yet. Generate one in Tab 1!")
    else:
        selected_script = st.selectbox("Select Saved Test Script:", saved_tests, format_func=lambda p: p.name)
        
        col_view, col_action = st.columns([2, 1])
        with col_view:
            with open(selected_script, "r", encoding="utf-8") as f:
                content = f.read()
            st.code(content, language="python")

        with col_action:
            st.markdown("##### Actions")
            if st.button("▶️ Rerun Test in Sandbox", type="primary", use_container_width=True):
                with st.spinner(f"Running `{selected_script.name}` in sandbox..."):
                    summary = runner.run_script(selected_script, allow_simulation=allow_sim)
                    report_path = analyzer.analyze_and_report(summary)
                    
                st.success(f"Execution {summary.get('status')} in {summary.get('total_duration')}s!")
                st.info(f"Report: `{report_path.name}`")

# TAB 3: TEST REPORTS & ARTIFACTS
with tab3:
    st.markdown("#### 📊 Historical Test Runs & Reports")
    runs = sorted(list(ARTIFACTS_DIR.glob("run_*")), reverse=True)
    if not runs:
        st.info("No test runs recorded yet.")
    else:
        for run in runs[:10]:
            sum_file = run / "summary.json"
            rep_file = run / "report.html"
            if sum_file.exists():
                import json
                with open(sum_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                
                status = s_data.get("status", "UNKNOWN")
                icon = "🟢" if status == "PASSED" else "🔴"
                
                with st.expander(f"{icon} {run.name} ({status} - {s_data.get('total_duration', 0)}s)"):
                    st.write(f"**Start Time:** {s_data.get('start_time')}")
                    st.write(f"**Steps Count:** {len(s_data.get('steps', []))}")
                    if s_data.get("error_message"):
                        st.error(f"Error: {s_data.get('error_message')}")
                    
                    if rep_file.exists():
                        with open(rep_file, "r", encoding="utf-8") as rf:
                            html_text = rf.read()
                        st.download_button(
                            label="⬇️ Download HTML Report",
                            data=html_text,
                            file_name=f"{run.name}_report.html",
                            mime="text/html"
                        )
