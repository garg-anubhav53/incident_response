import os
import json
import csv
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from anthropic import Anthropic

OUTPUT_DIR = Path("output")

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an incident analysis engine for a SaaS security platform. You receive raw technical data from multiple sources about a production incident. Extract a structured, accurate analysis.

CRITICAL RULES:
1. NEVER state a fact without source support. If you cannot determine something, say so in data_gaps.
2. Distinguish CONFIRMED root cause (engineers said "found it", "confirmed", "that's it") from HYPOTHESIS ("I think", "maybe", "could be"). Set root_cause.status accordingly.
3. Cross-reference timestamps across ALL sources. Flag inconsistencies.
4. A deployment is root cause ONLY IF: deployed to SAME failing service AND timing correlates AND engineers confirmed OR rollback fixed it. Unrelated deploys: note but do not attribute causation.
5. For metrics: baseline = pre-incident normal. Anomaly = >2x or <0.5x baseline. Note if recovery is gradual or sudden.
6. For scope: only state what data proves. If data mentions only one region/service, flag others as unconfirmed — do NOT assume unaffected.
7. EXCLUDE from customer comms: engineer emails, internal hostnames, cluster names, PR numbers, commit SHAs, internal Slack channels. List all found.
8. Map technical symptoms to customer experience: connection pool exhaustion → "API performance degradation"; 500 errors → "intermittent errors" (partial) or "service unavailable" (total); auth failures → "login issues"; detection pipeline errors → "delayed threat detection" (URGENT — security product).
9. Severity: degraded_performance = works but slow, most requests succeed; partial_outage = significant error rate but partially functional; full_outage = nearly all requests failing.
10. Timeline: use EARLIEST corroborating signal for onset (often metrics, before the alert). Use LATEST confirmation for resolution (post-monitoring). Alert time = detection, not onset.

INCIDENT TYPES (use as reasoning guides, not labels to force-assign):
- Deployment-induced: recent deploy correlates with onset, rollback resolves
- Infrastructure cascade: multiple services degrade, no deploy trigger, external provider mentioned
- Regional failure: errors scoped to specific region labels
- Portal/auth-only: UI/login errors but core processing unaffected
- Third-party dependency: errors reference external APIs (Microsoft Graph, etc.)
- Integration/API failure: outbound webhooks/SIEM/SOAR failing, core product unaffected
- Silent degradation: no hard errors but quality metrics drift

Return ONLY valid JSON, no markdown fencing:

{
  "incident_summary": "One sentence: what happened, to what service(s), for approximately how long, at what severity",
  "affected_service": "Primary service from alert data",
  "affected_products": ["Customer-facing product names if determinable, otherwise state unknown"],
  "severity": "From PagerDuty if available",
  "timeline": {
    "cause_time_utc": "When the triggering event occurred (deployment time) — null if no causal event identified",
    "onset_time_utc": "When degradation first appeared in metrics/logs — may precede the alert",
    "detection_time_utc": "When alert fired or engineers noticed",
    "acknowledged_time_utc": "When engineer responded",
    "mitigation_time_utc": "When fix/rollback was deployed",
    "recovery_time_utc": "When metrics returned to baseline",
    "resolved_time_utc": "When incident formally closed"
  },
  "root_cause": {
    "summary": "One sentence confirmed root cause — or 'Root cause not confirmed in available data'",
    "status": "confirmed | hypothesized | unknown",
    "trigger": "Specific change/event, or null",
    "mechanism": "How trigger caused impact, or null"
  },
  "customer_impact": {
    "description": "What customers experienced in plain non-technical language",
    "severity_assessment": "degraded_performance | partial_outage | full_outage",
    "affected_functionality": ["affected capabilities"],
    "unaffected_functionality": ["what continued working normally, ONLY if data confirms — do not guess"]
  },
  "resolution": {
    "action_taken": "What fixed it",
    "confirmed_by": "Evidence of recovery (metric values, log messages)"
  },
  "confidence_scores": {
    "root_cause": "high | medium | low",
    "scope": "high | medium | low",
    "timeline": "high | medium | low",
    "customer_impact": "high | medium | low"
  },
  "source_attribution": {
    "root_cause": ["sources supporting this conclusion"],
    "timeline": ["sources for each timestamp"],
    "customer_impact": ["sources supporting impact assessment"]
  },
  "data_gaps": ["Anything you cannot determine — be specific about what's missing and why it matters"],
  "internal_details_to_exclude": ["All internal names, infra details, emails, PRs, commit SHAs found"]
}"""


def detect_file_type(file_path: Path, content: str) -> str:
    filename = file_path.name.lower()

    # Filename hints first (unambiguous)
    if filename.startswith("pagerduty"):
        return "pagerduty_incident"
    if filename.startswith("cloudwatch") or filename.startswith("app_logs"):
        return "cloudwatch_logs"
    if filename.startswith("prometheus") or filename.startswith("metrics"):
        return "prometheus_metrics"
    if filename.startswith("github") or filename.startswith("deploy"):
        return "github_deployments"
    if file_path.suffix == ".txt" or filename.startswith("slack"):
        return "incident_context"

    # Content-based fallback (most specific patterns first)
    if "logGroup" in content or "logStream" in content:
        return "cloudwatch_logs"
    if "metric_name" in content or ("\"result\"" in content and "\"values\"" in content):
        return "prometheus_metrics"
    if "\"ref\"" in content and "\"commit\"" in content:
        return "github_deployments"
    if "\"incident\"" in content and "\"severity\"" in content:
        return "pagerduty_incident"
    if filename.startswith("incident") or file_path.suffix == ".txt":
        return "incident_context"

    return "unknown"


def load_incident_files(data_dir: Path) -> dict:
    files_by_type = {}
    for file_path in sorted(data_dir.glob("*")):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        file_type = detect_file_type(file_path, content)
        if file_type != "unknown":
            files_by_type[file_type] = file_path
        else:
            print(f"Warning: could not categorize {file_path.name}")
    return files_by_type


def _parse_prometheus(prometheus_data):
    """Parse Prometheus JSON into (name, labels, [(timestamp, value)]) tuples."""
    result = []
    if prometheus_data and "data" in prometheus_data:
        for r in prometheus_data["data"].get("result", []):
            name = r["metric"].get("__name__", "metric")
            labels = ",".join(f"{k}={v}" for k, v in r["metric"].items() if k != "__name__")
            values = []
            for ts, val in r["values"]:
                # Handle both Unix timestamps and ISO format timestamps
                try:
                    # Try Unix timestamp first
                    timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    # If that fails, try parsing as ISO format
                    timestamp = ts  # Already in ISO format
                values.append((timestamp, float(val)))
            result.append((name, labels, values))
    return result


def _is_anomalous(val: float, baseline: float) -> bool:
    if baseline == 0:
        return val > 0
    return val > 2 * baseline or val < 0.5 * baseline


def _duration_str(start_ts: str, end_ts: str) -> str:
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        s = datetime.strptime(start_ts, fmt)
        e = datetime.strptime(end_ts, fmt)
        mins = int((e - s).total_seconds() / 60)
        return f"{mins}min"
    except Exception:
        return ""


def summarize_metrics(prometheus_data: dict) -> str:
    lines = []
    for name, labels, values in _parse_prometheus(prometheus_data):
        label_str = f"{{{labels}}}" if labels else ""
        if len(values) < 2:
            lines.append(f"{name}{label_str}: insufficient data")
            continue

        baseline = (values[0][1] + values[1][1]) / 2

        anomaly_start_ts = anomaly_start_val = None
        for ts, val in values[2:]:
            if _is_anomalous(val, baseline):
                anomaly_start_ts, anomaly_start_val = ts, val
                break

        if anomaly_start_ts is None:
            lines.append(f"{name}{label_str}: stable, baseline={baseline:.3g}")
            continue

        peak_val = max(v for _, v in values)
        peak_ts = next(ts for ts, v in values if v == peak_val)

        # Recovery: first value within 1.5x baseline after peak
        past_peak, anomaly_end_ts = False, None
        for ts, val in values:
            if ts == peak_ts:
                past_peak = True
                continue
            if past_peak:
                if baseline == 0 and val == 0:
                    anomaly_end_ts = ts
                    break
                elif baseline > 0 and val <= 1.5 * baseline:
                    anomaly_end_ts = ts
                    break

        dur = _duration_str(anomaly_start_ts, anomaly_end_ts) if anomaly_end_ts else ""
        lines.append(
            f"{name}{label_str}: baseline={baseline:.3g} | "
            f"anomaly_start={anomaly_start_ts}(val={anomaly_start_val:.3g}) | "
            f"peak={peak_val:.3g} at {peak_ts} | "
            f"recovery={anomaly_end_ts or 'not_observed'}"
            + (f" | duration={dur}" if dur else "")
        )

    # Compact raw appendix (timestamps + values only, no labels repeated)
    lines.append("\nRAW VALUES (compact):")
    for name, labels, values in _parse_prometheus(prometheus_data):
        compact = " ".join(f"{ts[11:16]}={v:.3g}" for ts, v in values)
        lines.append(f"  {name}: {compact}")

    return "\n".join(lines)


def build_user_message(files_by_type: dict) -> str:
    sections = []
    order = [
        ("pagerduty_incident", "PAGERDUTY INCIDENT"),
        ("cloudwatch_logs", "CLOUDWATCH LOGS"),
        ("prometheus_metrics", "PROMETHEUS METRICS (pre-processed)"),
        ("github_deployments", "GITHUB DEPLOYMENTS"),
        ("incident_context", "INCIDENT CONTEXT (SLACK THREAD)"),
    ]
    for file_type, label in order:
        if file_type not in files_by_type:
            continue
        path = files_by_type[file_type]
        if file_type == "prometheus_metrics":
            data = json.loads(path.read_text())
            content = summarize_metrics(data)
        else:
            content = path.read_text()
        sections.append(f"=== {label} ===\n{content}")
    return "\n\n".join(sections)


def call_api(user_message: str) -> dict:
    for attempt in range(2):
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1600,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            if attempt == 0:
                user_message += "\n\nCRITICAL: Respond with ONLY a JSON object. No markdown fences. No explanation."
                continue
            raise ValueError("Claude returned invalid JSON after 2 attempts")


# ── Validation helpers ─────────────────────────────────────────────────────────

def _run_checks(checks: list, label: str) -> tuple:
    print(f"\n── {label} ──")
    passed = 0
    for desc, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
        passed += ok
    print(f"{passed}/{len(checks)} checks passed")
    return passed, len(checks)


def validate_original(result: dict) -> tuple:
    timeline = result.get("timeline", {})
    root = result.get("root_cause", {})
    return _run_checks([
        ("affected_service == api-gateway",
         result.get("affected_service", "").lower() == "api-gateway"),
        ("severity == SEV-2",
         result.get("severity", "").upper() == "SEV-2"),
        ("root_cause mentions timeout or PR #12345",
         any(kw in json.dumps(root).lower() for kw in ["timeout", "pr #12345", "pr#12345", "http client"])),
        ("cause/onset time ~14:15-14:20 UTC",
         any(ts in json.dumps(timeline) for ts in ["14:15", "14:20", "T14:15", "T14:20"])),
        ("resolution mentions rollback",
         any(kw in json.dumps(result.get("resolution", {})).lower() for kw in ["rollback", "rolled back"])),
        ("customer_impact == degraded_performance",
         result.get("customer_impact", {}).get("severity_assessment") == "degraded_performance"),
        ("data_gaps mentions scope or regional",
         any(kw in " ".join(result.get("data_gaps", [])).lower()
             for kw in ["regional", "customer", "region", "scope", "which product"])),
        ("internal_details includes rds-prod-main",
         any("rds-prod-main" in d for d in result.get("internal_details_to_exclude", []))),
        ("internal_details includes engineer names",
         any(n in " ".join(result.get("internal_details_to_exclude", [])).lower()
             for n in ["alice", "bob", "john"])),
        ("confidence_scores present", "confidence_scores" in result),
        ("source_attribution present", "source_attribution" in result),
    ], "Original Incident (v1 data + v2 schema)")


def validate_portal(result: dict) -> tuple:
    impact = result.get("customer_impact", {})
    gaps = " ".join(result.get("data_gaps", []))
    unaffected = " ".join(impact.get("unaffected_functionality", []))
    internals = " ".join(result.get("internal_details_to_exclude", []))
    return _run_checks([
        ("affected_service is portal-auth-service",
         "portal" in result.get("affected_service", "").lower()),
        ("severity == SEV-3",
         result.get("severity", "").upper() == "SEV-3"),
        ("customer_impact describes portal/login",
         any(kw in impact.get("description", "").lower()
             for kw in ["portal", "login", "access", "sign in", "log in"])),
        ("severity_assessment == partial_outage",
         impact.get("severity_assessment") == "partial_outage"),
        ("detection noted as unaffected",
         any(kw in (unaffected + " " + gaps).lower()
             for kw in ["detection", "ies", "email processing", "emails processed", "email security"])),
        ("internal session service name excluded",
         "session" in internals.lower()),
        ("confidence_scores present", "confidence_scores" in result),
    ], "Test A — Portal Auth Failure")


def validate_thirdparty(result: dict) -> tuple:
    root = result.get("root_cause", {})
    impact = result.get("customer_impact", {})
    gaps = " ".join(result.get("data_gaps", []))
    unaffected = " ".join(impact.get("unaffected_functionality", []))
    return _run_checks([
        ("affected_service is remediation-service",
         "remediation" in result.get("affected_service", "").lower()),
        ("severity == SEV-2",
         result.get("severity", "").upper() == "SEV-2"),
        ("root_cause mentions Microsoft or Graph",
         any(kw in json.dumps(root).lower() for kw in ["microsoft", "graph api", "graph.microsoft"])),
        ("root_cause trigger is null or external",
         root.get("trigger") is None
         or any(kw in str(root.get("trigger", "")).lower()
                for kw in ["microsoft", "external", "graph", "null"])),
        ("data_gaps mention external dependency",
         any(kw in gaps.lower() for kw in ["microsoft", "external", "third-party", "third party", "graph"])),
        ("detection noted as unaffected",
         any(kw in (unaffected + " " + gaps).lower()
             for kw in ["detection", "ies", "email detection", "email security"])),
        ("confidence_scores present", "confidence_scores" in result),
    ], "Test B — Third-party Dependency")


# ── Output writers ─────────────────────────────────────────────────────────────

# CSV columns consumed by the communication drafter (next pipeline step).
# Lists are semicolon-joined so a single cell stays readable and splittable.
_CSV_COLUMNS = [
    "source_dir",
    "incident_summary",
    "affected_service",
    "affected_products",       # list → semicolon-joined
    "severity",
    "cause_time_utc",
    "onset_time_utc",
    "detection_time_utc",
    "mitigation_time_utc",
    "recovery_time_utc",
    "resolved_time_utc",
    "root_cause_summary",
    "root_cause_status",       # confirmed | hypothesized | unknown
    "root_cause_trigger",
    "customer_impact_description",
    "severity_assessment",     # degraded_performance | partial_outage | full_outage
    "affected_functionality",  # list → semicolon-joined
    "unaffected_functionality",# list → semicolon-joined
    "resolution_action",
    "resolution_confirmed_by",
    "confidence_root_cause",
    "confidence_scope",
    "confidence_timeline",
    "confidence_customer_impact",
    "data_gaps",               # list → semicolon-joined
    "internal_details_to_exclude",  # list → semicolon-joined
]


def _join(value) -> str:
    """Flatten a list to a semicolon-joined string; pass scalars through."""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return "" if value is None else str(value)


def write_outputs(result: dict, source_dir: str) -> None:
    """Write per-incident JSON and append a row to the shared incidents CSV."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = source_dir.replace("/", "_").strip("_")

    # Full structured JSON — comm drafter can load this directly for rich context
    json_path = OUTPUT_DIR / f"{slug}_analysis.json"
    json_path.write_text(json.dumps(result, indent=2))

    # Flat CSV row — one row per incident, all incidents in one file
    csv_path = OUTPUT_DIR / "incidents.csv"
    write_header = not csv_path.exists()

    tl = result.get("timeline", {})
    rc = result.get("root_cause", {})
    ci = result.get("customer_impact", {})
    res = result.get("resolution", {})
    cs = result.get("confidence_scores", {})

    row = {
        "source_dir": source_dir,
        "incident_summary": result.get("incident_summary", ""),
        "affected_service": result.get("affected_service", ""),
        "affected_products": _join(result.get("affected_products", [])),
        "severity": result.get("severity", ""),
        "cause_time_utc": tl.get("cause_time_utc", ""),
        "onset_time_utc": tl.get("onset_time_utc", ""),
        "detection_time_utc": tl.get("detection_time_utc", ""),
        "mitigation_time_utc": tl.get("mitigation_time_utc", ""),
        "recovery_time_utc": tl.get("recovery_time_utc", ""),
        "resolved_time_utc": tl.get("resolved_time_utc", ""),
        "root_cause_summary": rc.get("summary", ""),
        "root_cause_status": rc.get("status", ""),
        "root_cause_trigger": _join(rc.get("trigger")),
        "customer_impact_description": ci.get("description", ""),
        "severity_assessment": ci.get("severity_assessment", ""),
        "affected_functionality": _join(ci.get("affected_functionality", [])),
        "unaffected_functionality": _join(ci.get("unaffected_functionality", [])),
        "resolution_action": res.get("action_taken", ""),
        "resolution_confirmed_by": res.get("confirmed_by", ""),
        "confidence_root_cause": cs.get("root_cause", ""),
        "confidence_scope": cs.get("scope", ""),
        "confidence_timeline": cs.get("timeline", ""),
        "confidence_customer_impact": cs.get("customer_impact", ""),
        "data_gaps": _join(result.get("data_gaps", [])),
        "internal_details_to_exclude": _join(result.get("internal_details_to_exclude", [])),
    }

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(f"  → JSON: {json_path}")
    print(f"  → CSV row appended: {csv_path}")


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_pipeline(data_dir: Path, validate_fn, test_name: str) -> tuple:
    print(f"\n{'='*55}")
    print(f"TEST: {test_name}")
    print(f"Dir:  {data_dir}")

    files_by_type = load_incident_files(data_dir)
    print(f"Detected: {list(files_by_type.keys())}")

    user_message = build_user_message(files_by_type)
    print(f"User message: ~{len(user_message.split())} words")

    print("Calling Claude...")
    result = call_api(user_message)

    print("\n── Analysis ──")
    print(json.dumps(result, indent=2))

    write_outputs(result, str(data_dir))

    return validate_fn(result)


def main():
    # Parse command line arguments
    custom_folder = None
    if len(sys.argv) > 1:
        custom_folder = sys.argv[1]
        print(f"📁 Using custom test folder: {custom_folder}")
    
    # Clear previous CSV so reruns produce a clean file
    csv_path = OUTPUT_DIR / "incidents.csv"
    if csv_path.exists():
        csv_path.unlink()

    total_p = total_c = 0

    if custom_folder:
        # Run pipeline on custom folder only
        folder_path = Path(custom_folder)
        if not folder_path.exists():
            print(f"❌ Error: Folder {custom_folder} does not exist")
            return
        
        # Generic validation for custom test cases
        def validate_custom(result: dict) -> tuple:
            return _run_checks([
                ("has_incident_summary", bool(result.get("incident_summary", "").strip())),
                ("has_affected_service", bool(result.get("affected_service", "").strip())),
                ("has_severity", bool(result.get("severity", "").strip())),
                ("has_timeline", bool(result.get("timeline", {}))),
                ("has_root_cause", bool(result.get("root_cause", {}))),
                ("has_customer_impact", bool(result.get("customer_impact", {}))),
                ("has_resolution", bool(result.get("resolution", {}))),
                ("confidence_scores_present", "confidence_scores" in result),
                ("source_attribution_present", "source_attribution" in result),
            ], f"Custom test case: {custom_folder}")
        
        p, c = run_pipeline(folder_path, validate_custom, f"Custom test case: {custom_folder}")
        total_p += p; total_c += c
    else:
        # Run default test cases
        p, c = run_pipeline(Path("data"), validate_original, "Original incident (v1 data, v2 schema)")
        total_p += p; total_c += c

        p, c = run_pipeline(Path("test_data_portal"), validate_portal, "Portal auth failure (synthetic)")
        total_p += p; total_c += c

        p, c = run_pipeline(Path("test_data_thirdparty"), validate_thirdparty, "Third-party dependency (synthetic)")
        total_p += p; total_c += c

    print(f"\n{'='*55}")
    print(f"TOTAL: {total_p}/{total_c} checks passed across all 3 test cases")
    print(f"Outputs written to: {OUTPUT_DIR.resolve()}")
    
    # Automatically trigger communication generation
    trigger_communication_generation()


def trigger_communication_generation():
    """Automatically trigger communication generation after analysis"""
    try:
        import subprocess
        print("\n🚀 Triggering communication generation...")
        
        # Check if we're running with a custom folder
        custom_folder = sys.argv[1] if len(sys.argv) > 1 else None
        
        # Build command with optional custom output directory
        cmd = ["python", "generate_comms.py"]
        if custom_folder:
            # Use custom folder name for both input and output
            cmd.append(f"comms_{custom_folder.replace('/', '_')}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        if result.returncode == 0:
            print("📝 Communications generated successfully")
            if result.stdout:
                print(result.stdout)
        else:
            print("⚠️  Communication generation failed")
            if result.stderr:
                print("Error:", result.stderr)
    except Exception as e:
        print(f"⚠️  Could not trigger communication generation: {e}")


if __name__ == "__main__":
    main()
