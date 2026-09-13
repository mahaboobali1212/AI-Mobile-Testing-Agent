"""
Streamlit Web Dashboard for AI-Powered Multi-Device Mobile Testing Agent.
"""

import os
import sys
import json
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

# Custom CSS for Premium Modern QA Dashboard
st.markdown("""
<style>
    .main-header { font-size: 30px; font-weight: 800; color: #38bdf8; margin-bottom: 2px; }
    .sub-header { color: #94a3b8; font-size: 15px; margin-bottom: 22px; }
    .metric-card { background-color: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; text-align: center; }
    .metric-value { font-size: 26px; font-weight: bold; color: #f8fafc; }
    .metric-label { font-size: 13px; color: #94a3b8; margin-top: 4px; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .prompt-box { background: #1e293b; border-left: 4px solid #38bdf8; padding: 12px; border-radius: 6px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# Curated Comprehensive Prompt Library
PROMPT_LIBRARY = {
    "📞 Telecom & Voice Calling": [
        ("Standard Two-Way Voice Call", "Device A dials Device B (555-0002), Device B answers the incoming call, stay on line for 4 seconds, then Device A terminates the call."),
        ("Call Decline / Rejection Flow", "Device A dials Device B (555-0002), Device B immediately rejects and declines the call, verify that both devices return to idle state with no active call."),
        ("Rapid Redial Flow", "Device A dials Device B (555-0002), hangs up after 2s, immediately redials Device B, and Device B accepts the call."),
        ("Conference Dialing Simulation", "Device A dials Device B (555-0002), Device B answers, verify connected call state for 5s, then both devices end the call.")
    ],
    "💬 SMS & Real-Time Messaging": [
        ("Two-Way Chat & Reply", "Device A sends SMS 'Project presentation at 3 PM' to Device B (555-0002), Device B verifies receipt and replies 'Got it, see you there!' to Device A."),
        ("One-Time Password (OTP) Verification", "Device A sends SMS 'Your verification code is 849201' to Device B (555-0002), Device B opens Messages app, reads OTP code, and returns home."),
        ("Notification Banner Alert", "Device A sends SMS 'Urgent: Server is back online' to Device B (555-0002), Device B verifies incoming push notification banner appears on screen."),
        ("Multi-Message Sequential Conversation", "Device A sends SMS 'Hello' to Device B, Device B replies 'Hi there', Device A sends 'Can we talk?', Device B verifies receipt.")
    ],
    "💳 Fintech & P2P Transactions": [
        ("P2P Money Transfer Alert", "Device A sends SMS 'Transaction Alert: $150.00 sent to Device B' to Device B (555-0002), Device B verifies notification text and navigates home."),
        ("Payment Request Notification", "Device A sends SMS 'Payment Request: Please pay $45 for dinner' to Device B (555-0002), Device B verifies request received."),
        ("Wallet Balance Update Alert", "Device A sends SMS 'Wallet top-up successful: New balance $500' to Device B (555-0002), Device B opens Messages app to verify.")
    ],
    "🌐 Multi-App & Navigation": [
        ("Dual Chrome Browser Launch", "Launch Chrome browser on Device A and Device B simultaneously, verify browser is opened on both devices, and then press Home button on both devices."),
        ("App Switching & Multitasking", "Device A opens Messages, sends SMS to Device B, Device A opens Chrome browser, and returns to Home screen."),
        ("Desktop State Clean Reset", "Press Home button on Device A and Device B, launch Camera on Device A and Chrome on Device B, then return both to Home.")
    ]
}

# Initialize engines
dev_mgr = DeviceManager()
generator = ScriptGenerator()
runner = SandboxRunner(dev_mgr)
analyzer = ResultAnalyzer()

# Sidebar: Device Pool Status & Config
with st.sidebar:
    st.markdown("### 📱 Device Pool Status")
    devices = dev_mgr.list_connected_devices()
    avds = dev_mgr.list_available_avds()

    if devices:
        st.success(f"🟢 {len(devices)} ADB Device(s) Online")
        for dev in devices:
            st.markdown(f"• **{dev['serial']}** ({dev['model']})")
    else:
        st.info("ℹ️ Virtual Device Sandbox active.")

    if avds:
        st.markdown("**Installed AVDs:**")
        for avd in avds:
            st.markdown(f"- 📲 `{avd}`")

    st.divider()
    st.markdown(f"**ADB Binary:** `{ADB_PATH}`")
    allow_sim = st.checkbox("Allow Virtual Simulation Fallback", value=True)
    
    st.divider()
    st.markdown("### ⚡ Quick Presets")
    presets = {
        "📞 Voice Call & Hangup": "Device A dials Device B (555-0002), Device B answers the call, stay on line for 4s, then Device A terminates the call.",
        "💬 Two-Way SMS Chat": "Device A sends SMS 'Project presentation at 3 PM' to Device B (555-0002), Device B verifies receipt and replies 'Got it, see you there!' to Device A.",
        "🌐 Dual Chrome Launch": "Launch Chrome browser on Device A and Device B simultaneously, verify browser is loaded, and return both to home screen.",
        "🚫 Call Decline Flow": "Device A dials Device B (555-0002), Device B immediately declines the call, verify both devices return to idle state.",
        "💳 Payment Alert": "Device A sends SMS 'Transaction Alert: $50 received' to Device B (555-0002), Device B verifies notification text and navigates home."
    }
    
    for label, text in presets.items():
        if st.button(label, use_container_width=True):
            st.session_state["selected_prompt"] = text

# Main Title
st.markdown('<div class="main-header">🤖 AI-Powered Multi-Device Mobile Testing Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous test authoring from natural language, isolated sandbox execution, real-time artifact collection, and 1-click test reruns.</div>', unsafe_allow_html=True)

tab1, tab_lib, tab2, tab3 = st.tabs([
    "✨ Generate & Run Test", 
    "📚 Scenario Prompt Library", 
    "💾 Saved Test Catalog & Rerun", 
    "📊 Test Reports & History"
])

# TAB 1: GENERATE & RUN TEST
with tab1:
    col_input, col_code = st.columns([1.1, 0.9])

    with col_input:
        st.markdown("#### 1. Describe Multi-Device Test Scenario")
        
        # Category Quick Selector
        cat_choice = st.selectbox("🎯 Or pick from category templates:", ["Custom / Manual Input"] + list(PROMPT_LIBRARY.keys()))
        if cat_choice != "Custom / Manual Input":
            template_options = [title for title, _ in PROMPT_LIBRARY[cat_choice]]
            sub_choice = st.selectbox("Select Scenario:", template_options)
            for title, prompt_val in PROMPT_LIBRARY[cat_choice]:
                if title == sub_choice:
                    st.session_state["selected_prompt"] = prompt_val
                    break

        default_prompt = st.session_state.get(
            "selected_prompt", 
            "Device A sends SMS 'Hello from Device A!' to Device B (555-0002), Device B verifies receipt and replies 'Message received loud and clear' to Device A."
        )
        prompt_text = st.text_area("Test Scenario Prompt (Plain English):", value=default_prompt, height=120)
        
        col_name, col_btn = st.columns([1, 1])
        with col_name:
            custom_test_name = st.text_input("Custom Test Name (Optional):", placeholder="e.g. test_sms_flow")
        with col_btn:
            st.write("")
            st.write("")
            run_btn = st.button("🚀 Generate & Run Test in Sandbox", type="primary", use_container_width=True)

    if run_btn and prompt_text:
        with st.spinner("🤖 Generating deterministic Python test script with AI..."):
            script_path, code = generator.generate_script(prompt_text, test_name=custom_test_name or None)
            st.success(f"✅ Generated & Saved to `{script_path.name}`")

        with col_code:
            st.markdown(f"#### 2. Generated Python Script (`{script_path.name}`)")
            st.code(code, language="python")

        st.markdown("---")
        st.markdown("#### 3. Sandbox Execution & Dual-Device Live Timeline")
        progress_bar = st.progress(0, text="Executing in Sandbox...")

        with st.spinner("⚡ Running test script in sandbox..."):
            summary = runner.run_script(script_path, allow_simulation=allow_sim)
            report_path = analyzer.analyze_and_report(summary)
            progress_bar.progress(100, text="Execution Complete!")

        # Display Metrics Cards
        is_pass = summary.get("status") == "PASSED"
        status_color = "#10b981" if is_pass else "#ef4444"
        
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: {status_color};">{summary.get("status")}</div><div class="metric-label">Test Outcome</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{summary.get("total_duration")}s</div><div class="metric-label">Total Duration</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{len(summary.get("steps", []))}</div><div class="metric-label">Steps Executed</div></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{len(summary.get("devices", {}))}</div><div class="metric-label">Devices Tested</div></div>', unsafe_allow_html=True)

        if not is_pass and summary.get("ai_diagnosis"):
            st.error(summary["ai_diagnosis"])

        st.markdown("##### 📸 Step-by-Step Device Screen Comparison")
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

        # Download Report button
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as rf:
                report_html = rf.read()
            st.download_button(
                label="⬇️ Download Standalone Self-Contained HTML Report",
                data=report_html,
                file_name=f"{summary.get('run_name', 'test')}_report.html",
                mime="text/html",
                type="secondary"
            )

# TAB: SCENARIO PROMPT LIBRARY
with tab_lib:
    st.markdown("### 📚 Comprehensive Scenario Prompt Library")
    st.markdown("Browse and load ready-to-test multi-device mobile scenarios across multiple domains.")
    
    for category, prompt_list in PROMPT_LIBRARY.items():
        with st.expander(f"📂 {category} ({len(prompt_list)} Scenarios)", expanded=True):
            for title, prompt_str in prompt_list:
                c_desc, c_btn = st.columns([3.5, 1])
                with c_desc:
                    st.markdown(f"**{title}**")
                    st.caption(prompt_str)
                with c_btn:
                    st.write("")
                    if st.button(f"Load Scenario", key=f"btn_{title}"):
                        st.session_state["selected_prompt"] = prompt_str
                        st.success(f"Loaded '{title}' into Tab 1!")

# TAB 2: SAVED TEST CATALOG & RERUN
with tab2:
    st.markdown("#### 💾 Saved Reusable Test Catalog")
    st.caption("Re-run any previously generated test on-demand in the Sandbox without making any AI calls.")

    saved_tests = sorted(list(TESTS_GENERATED_DIR.glob("test_*.py")), reverse=True)
    if not saved_tests:
        st.info("No saved test scripts found yet. Generate one in Tab 1!")
    else:
        selected_script = st.selectbox("Select Saved Test Script to Inspect & Run:", saved_tests, format_func=lambda p: p.name)
        
        col_view, col_action = st.columns([1.2, 0.8])
        with col_view:
            with open(selected_script, "r", encoding="utf-8") as f:
                content = f.read()
            st.code(content, language="python")

        with col_action:
            st.markdown("##### Execute Test")
            st.markdown(f"**Script:** `{selected_script.name}`")
            st.markdown(f"**Size:** {selected_script.stat().st_size} bytes")
            if st.button("▶️ Rerun Test in Sandbox", type="primary", use_container_width=True):
                with st.spinner(f"Running `{selected_script.name}` in sandbox..."):
                    summary = runner.run_script(selected_script, allow_simulation=allow_sim)
                    report_path = analyzer.analyze_and_report(summary)
                    
                st.success(f"Execution {summary.get('status')} in {summary.get('total_duration')}s!")
                if report_path.exists():
                    with open(report_path, "r", encoding="utf-8") as rf:
                        report_html = rf.read()
                    st.download_button(
                        label="⬇️ Download Run Report",
                        data=report_html,
                        file_name=f"{selected_script.stem}_report.html",
                        mime="text/html"
                    )

# TAB 3: TEST REPORTS & HISTORY
with tab3:
    st.markdown("#### 📊 Historical Test Runs & Reports")
    runs = sorted(list(ARTIFACTS_DIR.glob("run_*")), reverse=True)
    if not runs:
        st.info("No test runs recorded yet.")
    else:
        for run in runs[:15]:
            sum_file = run / "summary.json"
            rep_file = run / "report.html"
            if sum_file.exists():
                with open(sum_file, "r", encoding="utf-8") as rf:
                    s_data = json.load(rf)
                
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
                            label="⬇️ Download Self-Contained HTML Report",
                            data=html_text,
                            file_name=f"{run.name}_report.html",
                            mime="text/html",
                            key=f"dl_{run.name}"
                        )
