"""
ResultAnalyzer: Evaluates test run results, generates AI root-cause diagnostics, and produces interactive HTML reports.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from config import GEMINI_API_KEY, GEMINI_MODEL


class ResultAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model_name: str = GEMINI_MODEL):
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None

    def analyze_and_report(self, run_summary: Dict[str, Any]) -> Path:
        """
        Performs AI diagnosis on failed runs and generates a complete, standalone report.html.
        """
        run_dir = Path(run_summary["run_dir"])
        ai_diagnosis = ""

        # Perform AI analysis if test failed
        if run_summary.get("status") == "FAILED":
            ai_diagnosis = self._diagnose_failure(run_summary)
            run_summary["ai_diagnosis"] = ai_diagnosis

        # Generate HTML report
        report_path = self._generate_html_report(run_summary, run_dir)
        return report_path

    def _diagnose_failure(self, summary: Dict[str, Any]) -> str:
        """Uses Gemini to explain why the test failed and suggest fixes."""
        error_msg = summary.get("error_message", "Unknown error")
        stack_trace = summary.get("stack_trace", "")
        steps = summary.get("steps", [])

        if self._client:
            try:
                prompt = f"""You are an expert Mobile QA Diagnostics Agent. Analyze this failed Android multi-device test run and provide:
1. Root Cause Summary (1-2 sentences)
2. Likely Reason for Failure
3. Recommended Fix

Error Message: {error_msg}
Stack Trace:
{stack_trace}

Executed Steps:
{json.dumps(steps, indent=2)}
"""
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                pass

        # Smart fallback diagnosis
        return f"**Automated Diagnostic**: Test failed at step due to `{error_msg}`. Ensure devices have network connectivity and UI elements are accessible without unexpected system dialogs."

    def _generate_html_report(self, summary: Dict[str, Any], run_dir: Path) -> Path:
        """Renders an interactive, standalone HTML test report with embedded styling."""
        status = summary.get("status", "UNKNOWN")
        is_pass = status == "PASSED"
        status_color = "#10b981" if is_pass else "#ef4444"
        badge_text = "PASSED" if is_pass else "FAILED"
        duration = summary.get("total_duration", 0)
        run_name = summary.get("run_name", "Test Run")
        devices = summary.get("devices", {})
        steps = summary.get("steps", [])
        ai_diag = summary.get("ai_diagnosis", "")

        # Build device list HTML
        devices_html = ""
        for alias, info in devices.items():
            sim_tag = '<span class="badge-sim">SIMULATED</span>' if info.get("simulated") else '<span class="badge-real">PHYSICAL/AVD</span>'
            devices_html += f'<div class="device-card"><strong>{alias.upper()}</strong> ({info.get("serial")}) {sim_tag}</div>'

        # Build steps HTML
        steps_html = ""
        for step in steps:
            s_name = step.get("name", "Step")
            s_status = step.get("status", "PASSED")
            s_dur = step.get("duration", 0)
            s_err = step.get("error")
            s_screens = step.get("screenshots", [])
            
            s_color = "#10b981" if s_status == "PASSED" else "#ef4444"
            
            # Images gallery for step
            imgs_html = ""
            for img_name in s_screens:
                img_rel = f"screenshots/{img_name}"
                imgs_html += f'<div class="screenshot-box"><img src="{img_rel}" alt="{img_name}" /><div class="ss-caption">{img_name}</div></div>'

            err_block = f'<div class="error-msg">⚠️ {s_err}</div>' if s_err else ''

            steps_html += f"""
            <div class="step-card">
                <div class="step-header">
                    <span class="step-title">{s_name}</span>
                    <span class="step-meta" style="color: {s_color}; font-weight: bold;">{s_status} ({s_dur}s)</span>
                </div>
                {err_block}
                <div class="screenshot-grid">
                    {imgs_html}
                </div>
            </div>
            """

        ai_diag_html = ""
        if ai_diag:
            ai_diag_html = f"""
            <div class="ai-diagnosis-card">
                <h3>🤖 AI Failure Root-Cause Analysis</h3>
                <div class="ai-content">{ai_diag}</div>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {run_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        .header-card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 8px solid {status_color};
        }}
        .title {{
            font-size: 24px;
            font-weight: 700;
            margin: 0 0 8px 0;
        }}
        .subtitle {{
            color: #94a3b8;
            font-size: 14px;
        }}
        .status-badge {{
            background: {status_color};
            color: #ffffff;
            font-size: 18px;
            font-weight: 800;
            padding: 8px 20px;
            border-radius: 8px;
            text-transform: uppercase;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .metric-card {{
            background: #1e293b;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-val {{
            font-size: 24px;
            font-weight: 700;
            color: #38bdf8;
        }}
        .metric-label {{
            color: #94a3b8;
            font-size: 13px;
            margin-top: 4px;
        }}
        .devices-section {{
            margin-bottom: 24px;
        }}
        .device-card {{
            background: #1e293b;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 8px;
            display: inline-block;
            margin-right: 12px;
        }}
        .badge-sim {{
            background: #64748b;
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 8px;
        }}
        .badge-real {{
            background: #0284c7;
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin-left: 8px;
        }}
        .step-card {{
            background: #1e293b;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .step-title {{
            font-size: 16px;
            font-weight: 600;
        }}
        .error-msg {{
            background: #7f1d1d;
            color: #fecaca;
            padding: 10px 14px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-family: monospace;
        }}
        .screenshot-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 12px;
        }}
        .screenshot-box {{
            background: #0f172a;
            border-radius: 6px;
            padding: 8px;
            text-align: center;
            border: 1px solid #334155;
        }}
        .screenshot-box img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        .ss-caption {{
            color: #94a3b8;
            font-size: 11px;
            margin-top: 6px;
            word-break: break-all;
        }}
        .ai-diagnosis-card {{
            background: #2e1065;
            border: 1px solid #a855f7;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .ai-diagnosis-card h3 {{
            margin-top: 0;
            color: #d8b4fe;
        }}
        .ai-content {{
            white-space: pre-line;
            color: #f3e8ff;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-card">
            <div>
                <h1 class="title">Mobile Automation Test Report</h1>
                <div class="subtitle">{run_name} | {summary.get("start_time")}</div>
            </div>
            <div class="status-badge">{badge_text}</div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-val">{duration}s</div>
                <div class="metric-label">Total Duration</div>
            </div>
            <div class="metric-card">
                <div class="metric-val">{len(steps)}</div>
                <div class="metric-label">Steps Executed</div>
            </div>
            <div class="metric-card">
                <div class="metric-val">{len(devices)}</div>
                <div class="metric-label">Devices Involved</div>
            </div>
        </div>

        {ai_diag_html}

        <div class="devices-section">
            <h3 style="color: #94a3b8;">Allocated Devices</h3>
            {devices_html}
        </div>

        <div class="steps-section">
            <h3 style="color: #94a3b8;">Execution Timeline</h3>
            {steps_html}
        </div>
    </div>
</body>
</html>
"""
        report_path = run_dir / "report.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return report_path
