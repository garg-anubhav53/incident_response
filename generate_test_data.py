#!/usr/bin/env python3
"""
Test Data Generator for Incident Communications Generator
=========================================================

Generates a folder of realistic synthetic incident data files from a plain-language
description of an incident scenario. The generated files exactly match the formats
consumed by the pipeline:

  pagerduty_incident.json   — alert, service name, severity, timestamps
  cloudwatch_logs.json      — application error logs
  prometheus_metrics.json   — time-series metrics showing anomaly and recovery
  github_deployments.json   — deployment records near the incident window
  incident_context.txt      — Slack thread with engineer discussion

Usage (interactive):
  python generate_test_data.py

Usage (scripted):
  python generate_test_data.py --output-dir my_test_scenario

The script calls Claude to generate all five files simultaneously, ensuring they
are internally consistent (same timestamps, same service names, corroborating facts).
"""

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Schema reference strings embedded in the generation prompt so the model
# produces data in exactly the right format for our preprocessors.
# ---------------------------------------------------------------------------

PAGERDUTY_SCHEMA = """{
  "incident": {
    "id": "P<alphanumeric>",
    "title": "<human-readable alert title>",
    "status": "resolved | triggered | acknowledged",
    "urgency": "high | low",
    "severity": "SEV-1 | SEV-2 | SEV-3",
    "created_at": "<ISO 8601 UTC timestamp>",
    "acknowledged_at": "<ISO 8601 UTC timestamp or null>",
    "resolved_at": "<ISO 8601 UTC timestamp or null>",
    "service": "<internal service name>",
    "assigned_to": "<engineer-email@example.com>",
    "timeline": [
      { "timestamp": "<ISO 8601>", "type": "trigger | acknowledge | resolve", "message": "..." },
      ...
    ]
  }
}"""

CLOUDWATCH_SCHEMA = """{
  "logs": [
    {
      "timestamp": "<ISO 8601 UTC>",
      "level": "ERROR | WARN | INFO",
      "service": "<service name>",
      "message": "<log message>",
      "context": { <key-value pairs relevant to the error> }
    },
    ...
  ]
}"""

PROMETHEUS_SCHEMA = """{
  "metrics": [
    {
      "metric_name": "<snake_case metric name>",
      "labels": { "<label_key>": "<label_value>", ... },
      "values": [
        { "timestamp": "<ISO 8601 UTC>", "value": <float> },
        ...
      ]
    },
    ...
  ]
}"""

GITHUB_SCHEMA = """{
  "deployments": [
    {
      "timestamp": "<ISO 8601 UTC>",
      "service": "<service name>",
      "pr_number": <integer>,
      "commit_sha": "<7-char hex>",
      "author": "<dev-email@example.com>",
      "title": "<PR title>",
      "description": "<PR description>",
      "files_changed": ["<path/to/file>", ...],
      "diff_snippet": "<optional relevant diff lines>"
    },
    ...
  ]
}"""

SLACK_FORMAT = """=== Incident Context ===
Started: <human-readable date and time Pacific>
Affected Service: <service> (<description>)

--- Slack #incidents Thread ---
[HH:MM PM] @engineer: <message>
[HH:MM PM] @engineer: <message>
...
"""

GENERATION_PROMPT = """You are generating synthetic but realistic incident data files for testing an incident communications system at a SaaS security company called Abnormal Security. Abnormal Security makes email security products.

## Incident Scenario

{scenario}

## Difficulty / Data Quality Parameters

{difficulty_notes}

## Output Required

Generate all five data files simultaneously. They MUST be internally consistent:
- Same service names throughout all files
- Same timestamps (PagerDuty alert fires ~5-10 min after metrics first show anomaly)
- Slack thread references specific log errors and metric values from the other files
- If there is a causal deployment, its timestamp appears in github_deployments AND engineers discuss it in Slack

Use realistic Abnormal Security internal context:
- Engineer emails: firstname.lastname@abnormalsecurity.com
- Services may include: ies-pipeline, ies-api, portal-frontend, auth-service, api-gateway, ato-service, aism-service, soar-webhook, siem-delivery, notification-service
- Products map to: Inbound Email Security (IES), Account Takeover (ATO), AI Security Mailbox (AISM), Portal Application
- Customers are typically enterprise, mid-market, or government (Abnormal Gov)
- Slack handles: @alice.sre, @bob.eng, @carol.ic, @dave.oncall, @oncall-bot, etc.

## File Schemas

### pagerduty_incident.json
{pagerduty_schema}

### cloudwatch_logs.json
{cloudwatch_schema}

### prometheus_metrics.json (IMPORTANT: first 2 values per metric must be baseline/normal; anomaly begins at value 3+; recovery appears in last 2-3 values)
{prometheus_schema}

### github_deployments.json
{github_schema}

### incident_context.txt (plain text, NOT JSON)
Format:
{slack_format}

## Rules

1. ALL timestamps must be ISO 8601 UTC in the JSON files. Slack thread uses human-readable Pacific Time.
2. Prometheus metrics: generate 3-4 distinct metrics. First 2 readings = baseline (normal). Readings 3+ show the anomaly. Last 2-3 readings show recovery or continued degradation.
3. If the scenario has a causal deployment: place it 5-15 minutes before the PagerDuty alert fires. Have engineers identify it in Slack.
4. If the scenario has NO clear root cause: make the Slack thread show confused engineers, multiple hypotheses, escalation. Do NOT put a clean causal deployment in github_deployments.
5. If data quality is "noisy": add irrelevant bot messages in Slack, add unrelated ERROR logs for other services, add deployments to unrelated services in the same window.
6. If data quality is "ambiguous": use vague service names, have engineers partially contradict each other, leave root cause unresolved.
7. Cloudwatch logs: 4-8 entries. Mix of ERROR during incident window, at least one INFO at recovery.
8. Github deployments: 1-4 entries. May include unrelated deployments to add noise.
9. Slack thread: 8-18 messages. Must include: initial alert, engineer acknowledgment, diagnostic observations, hypothesis/confirmation of cause (or confusion if ambiguous), resolution action, post-resolution monitoring note.
10. The incident_context field must be plain text, NOT JSON.

Return ONLY valid JSON with this structure (no markdown fencing, no explanation):
{{
  "pagerduty_incident": {{ ... }},
  "cloudwatch_logs": {{ ... }},
  "prometheus_metrics": {{ ... }},
  "github_deployments": {{ ... }},
  "incident_context": "<full plain text of the Slack thread file>"
}}"""


# ---------------------------------------------------------------------------
# Difficulty presets — maps user-friendly choices to prompt language
# ---------------------------------------------------------------------------

DIFFICULTY_PRESETS = {
    "1": {
        "label": "Clean — clear root cause, unambiguous data",
        "notes": (
            "Data quality is HIGH. Root cause is obvious and confirmed by engineers in Slack. "
            "Metrics show a clean before/during/after pattern. Logs are precise. "
            "There is exactly one causal deployment clearly identified. "
            "No noise or irrelevant entries. Easy for an extraction model to parse."
        ),
    },
    "2": {
        "label": "Moderate — some noise, root cause eventually identified",
        "notes": (
            "Data quality is MODERATE. Root cause is identified by engineers but takes some investigation. "
            "Slack thread includes a few dead-end hypotheses before the real cause is found. "
            "Logs include some warnings for unrelated services. "
            "GitHub deployments include one unrelated deployment in the same window. "
            "Metrics show the anomaly clearly but recovery is gradual, not sudden."
        ),
    },
    "3": {
        "label": "Hard — ambiguous signals, noisy data, uncertain root cause",
        "notes": (
            "Data quality is LOW. Root cause is NOT confirmed — engineers have competing hypotheses. "
            "Slack thread shows confusion, escalation, and partial contradictions between engineers. "
            "GitHub deployments include 2-3 deployments of which only one is suspicious, "
            "and engineers are not certain it caused the issue. "
            "Logs from multiple services, some irrelevant. "
            "Metrics are noisy — one metric seems to contradict others. "
            "The incident may still be under investigation when the thread ends. "
            "Hard for an extraction model: low confidence on root cause, unclear scope."
        ),
    },
    "4": {
        "label": "Expert — third-party dependency, no internal root cause",
        "notes": (
            "Root cause is an EXTERNAL dependency (upstream provider, Microsoft Graph API, AWS service). "
            "Internal logs show errors that reference the external service failing. "
            "Engineers quickly determine it's not an internal deployment issue. "
            "GitHub deployments exist but are clearly unrelated. "
            "Slack thread references external status page or support ticket. "
            "The challenge is correctly classifying this as third_party_dependency, not deployment_induced. "
            "Customer impact may be limited to a specific region or integration."
        ),
    },
    "5": {
        "label": "Custom — describe difficulty manually",
        "notes": None,  # Will be filled in interactively
    },
}

CUSTOMER_PRESETS = {
    "1": "US enterprise customers (standard Abnormal Security deployment)",
    "2": "EU customers only (EU-region portal and IES)",
    "3": "Government customers on Abnormal Gov (FedRAMP environment, formal context)",
    "4": "Mixed — both US and EU customers affected with different impact profiles",
    "5": "API-heavy customers using SOAR/SIEM integrations",
    "6": "All customers globally",
}

INCIDENT_TYPE_HINTS = {
    "deployment": "Include a causal deployment 5-15 minutes before the alert.",
    "infrastructure": "No deployment trigger. Multiple services fail simultaneously.",
    "portal": "Portal/UI is down but email detection and remediation are fully operational.",
    "third_party": "External dependency (Microsoft Graph, AWS, etc.) is the root cause.",
    "detection": "Email detection pipeline is impaired — this is high severity for a security product.",
    "remediation": "Automated remediation (quarantine/deletion) is broken; detection is fine.",
    "regional": "Issue is scoped to one region only (US or EU).",
    "silent": "No hard errors — quality metrics drift gradually with no obvious trigger.",
}


def interactive_prompt() -> tuple[str, str, str]:
    """
    Walk the user through describing their scenario interactively.
    Returns (scenario_text, difficulty_notes, output_dir_name).
    """
    print("\n" + "=" * 60)
    print("  Incident Test Data Generator")
    print("  Abnormal Security — Internal Tool")
    print("=" * 60)
    print()
    print("Describe the incident scenario you want to generate test data for.")
    print("The more detail you provide, the more realistic and useful the data.")
    print()

    # --- Scenario description ---
    print("── SCENARIO DESCRIPTION ─────────────────────────────────")
    print("What is the incident? Describe freely — the affected service,")
    print("what customers experience, how it starts, how it ends.")
    print("(Press Enter twice when done)\n")

    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    scenario = "\n".join(lines).strip()

    if not scenario:
        print("No scenario provided. Exiting.")
        sys.exit(1)

    # --- Optional incident type hint ---
    print("\n── INCIDENT TYPE (optional) ──────────────────────────────")
    for key, hint in INCIDENT_TYPE_HINTS.items():
        print(f"  {key:<12} — {hint[:60]}...")
    print("  (press Enter to skip)")
    itype = input("Type: ").strip().lower()
    if itype in INCIDENT_TYPE_HINTS:
        scenario += f"\n\nIncident type hint: {INCIDENT_TYPE_HINTS[itype]}"

    # --- Customer scope ---
    print("\n── CUSTOMER SCOPE ────────────────────────────────────────")
    for k, v in CUSTOMER_PRESETS.items():
        print(f"  {k}. {v}")
    cust = input("Select (1-6, or describe): ").strip()
    if cust in CUSTOMER_PRESETS:
        scenario += f"\n\nAffected customer scope: {CUSTOMER_PRESETS[cust]}"
    elif cust:
        scenario += f"\n\nAffected customer scope: {cust}"

    # --- Difficulty ---
    print("\n── DATA QUALITY / DIFFICULTY ─────────────────────────────")
    for k, v in DIFFICULTY_PRESETS.items():
        print(f"  {k}. {v['label']}")
    diff_choice = input("Select (1-5): ").strip()

    if diff_choice in DIFFICULTY_PRESETS and diff_choice != "5":
        difficulty_notes = DIFFICULTY_PRESETS[diff_choice]["notes"]
    elif diff_choice == "5":
        print("Describe the data quality / difficulty characteristics:")
        difficulty_notes = input("> ").strip()
    else:
        difficulty_notes = DIFFICULTY_PRESETS["1"]["notes"]

    # --- Output folder name ---
    print("\n── OUTPUT FOLDER ─────────────────────────────────────────")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suggested = f"test_data_{ts}"
    folder_input = input(f"Folder name [{suggested}]: ").strip()
    output_dir = folder_input if folder_input else suggested

    return scenario, difficulty_notes, output_dir


def build_prompt(scenario: str, difficulty_notes: str) -> str:
    return GENERATION_PROMPT.format(
        scenario=scenario,
        difficulty_notes=difficulty_notes,
        pagerduty_schema=PAGERDUTY_SCHEMA,
        cloudwatch_schema=CLOUDWATCH_SCHEMA,
        prometheus_schema=PROMETHEUS_SCHEMA,
        github_schema=GITHUB_SCHEMA,
        slack_format=SLACK_FORMAT,
    )


def generate_data(scenario: str, difficulty_notes: str) -> dict:
    """Call Claude to generate all five files. Returns parsed dict."""
    print("\n⏳ Calling Claude to generate incident data...")
    prompt = build_prompt(scenario, difficulty_notes)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        temperature=0.7,  # some creativity for realistic variation
        system=(
            "You are a senior reliability engineer and technical writer at a SaaS security company. "
            "You generate realistic synthetic incident data for testing. "
            "You produce precise, internally consistent data that matches real production patterns. "
            "Return ONLY valid JSON as instructed — no markdown, no explanation."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        print(f"\n❌ Claude returned invalid JSON: {e}")
        print("Raw response (first 500 chars):", raw[:500])
        sys.exit(1)

    return data


def save_files(data: dict, output_dir: str) -> Path:
    """Write the five files to output_dir. Returns the Path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    file_map = {
        "pagerduty_incident":  ("pagerduty_incident.json",  True),
        "cloudwatch_logs":     ("cloudwatch_logs.json",      True),
        "prometheus_metrics":  ("prometheus_metrics.json",   True),
        "github_deployments":  ("github_deployments.json",   True),
        "incident_context":    ("incident_context.txt",      False),
    }

    written = []
    for key, (filename, is_json) in file_map.items():
        if key not in data:
            print(f"  ⚠️  Missing key '{key}' in response — skipping {filename}")
            continue

        content = data[key]
        path = out / filename

        if is_json:
            # Re-serialize with pretty printing for readability
            if isinstance(content, str):
                # Model may have returned JSON as a string inside the outer JSON
                try:
                    content = json.loads(content)
                except Exception:
                    pass
            path.write_text(json.dumps(content, indent=2))
        else:
            # Plain text (incident_context.txt)
            path.write_text(content if isinstance(content, str) else str(content))

        written.append(filename)
        print(f"  ✅  {filename}")

    return out


def write_scenario_readme(output_dir: Path, scenario: str, difficulty_notes: str) -> None:
    """Write a README.md to the output folder documenting what was generated."""
    readme = output_dir / "README.md"
    content = textwrap.dedent(f"""\
        # Generated Test Data

        **Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

        ## Scenario

        {scenario}

        ## Data Quality / Difficulty

        {difficulty_notes}

        ## Files

        | File | Contents |
        |---|---|
        | `pagerduty_incident.json` | Alert, service, severity, timestamps |
        | `cloudwatch_logs.json` | Application error logs |
        | `prometheus_metrics.json` | Time-series metrics (anomaly + recovery) |
        | `github_deployments.json` | Deployment records near incident window |
        | `incident_context.txt` | Slack thread with engineer discussion |

        ## Usage

        Load in the app by clicking "Load Sample Data" if this folder is named `data/`,
        or upload the files individually via the file uploader.
        """)
    readme.write_text(content)


def validate_output(data: dict) -> list[str]:
    """Basic sanity checks on generated data. Returns list of warnings."""
    warnings = []

    pd = data.get("pagerduty_incident", {}).get("incident", {})
    if not pd.get("service"):
        warnings.append("pagerduty_incident missing 'service' field")
    if not pd.get("created_at"):
        warnings.append("pagerduty_incident missing 'created_at'")

    metrics = data.get("prometheus_metrics", {}).get("metrics", [])
    if len(metrics) < 2:
        warnings.append(f"prometheus_metrics has only {len(metrics)} metric(s) — expected 3+")
    for m in metrics:
        vals = m.get("values", [])
        if len(vals) < 4:
            warnings.append(f"Metric '{m.get('metric_name')}' has only {len(vals)} values — too few for anomaly detection")

    logs = data.get("cloudwatch_logs", {}).get("logs", [])
    if not logs:
        warnings.append("cloudwatch_logs is empty")

    deployments = data.get("github_deployments", {}).get("deployments", [])
    if not deployments:
        warnings.append("github_deployments is empty — no deployment records generated")

    context = data.get("incident_context", "")
    if len(context) < 200:
        warnings.append("incident_context is very short — Slack thread may be inadequate")

    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic incident test data for the Incident Communications Generator."
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to write files to (default: prompted interactively)",
    )
    parser.add_argument(
        "--scenario",
        help="Incident scenario description (if omitted, prompted interactively)",
    )
    parser.add_argument(
        "--difficulty",
        choices=["1", "2", "3", "4"],
        help="Difficulty preset: 1=clean, 2=moderate, 3=hard, 4=third-party",
    )
    args = parser.parse_args()

    if args.scenario:
        # Non-interactive mode
        scenario = args.scenario
        difficulty_key = args.difficulty or "1"
        difficulty_notes = DIFFICULTY_PRESETS[difficulty_key]["notes"]
        output_dir = args.output_dir or f"test_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        # Interactive mode
        scenario, difficulty_notes, output_dir = interactive_prompt()

    print(f"\n📂 Output folder: {output_dir}")

    # Generate
    data = generate_data(scenario, difficulty_notes)

    # Validate
    warnings = validate_output(data)
    if warnings:
        print("\n⚠️  Validation warnings:")
        for w in warnings:
            print(f"   • {w}")

    # Save
    print("\n💾 Writing files:")
    out_path = save_files(data, output_dir)
    write_scenario_readme(out_path, scenario, difficulty_notes)
    print(f"   ✅  README.md")

    print(f"\n✅ Done. Test data written to: {out_path.resolve()}")
    print("\nTo use in the app:")
    print(f"  • Rename the folder to 'data/' to make it the default sample, or")
    print(f"  • Upload the files individually via the file uploader.")
    print()


if __name__ == "__main__":
    main()
