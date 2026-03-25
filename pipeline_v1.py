import os
import json
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DATA_DIR = Path("data")

SYSTEM_PROMPT = """You are an incident analysis engine. You receive raw technical data from multiple sources about a production incident. Extract a structured analysis as JSON with exactly these fields:

{
  "incident_summary": "One sentence: what happened, to what, for how long",
  "affected_service": "Service name from PagerDuty/logs",
  "severity": "From PagerDuty",
  "timeline": {
    "trigger_time_utc": "When degradation began in metrics",
    "detection_time_utc": "When alert fired",
    "acknowledged_time_utc": "When engineer responded",
    "mitigation_time_utc": "When fix was deployed",
    "recovery_time_utc": "When metrics returned to normal",
    "resolved_time_utc": "When incident was formally closed"
  },
  "root_cause": {
    "summary": "One sentence confirmed root cause",
    "trigger": "What specific change/event caused it",
    "mechanism": "How the trigger led to customer impact"
  },
  "customer_impact": {
    "description": "What customers experienced in plain language",
    "severity_assessment": "degraded_performance | partial_outage | full_outage",
    "affected_functionality": ["list of affected features/capabilities"]
  },
  "resolution": {
    "action_taken": "What fixed it",
    "confirmed_by": "What evidence shows it's fixed (metrics, logs)"
  },
  "data_gaps": ["List anything you cannot determine from the provided data"],
  "internal_details_to_exclude": ["Any internal names, infra details, or engineer names that must NOT appear in customer communications"]
}

Rules:
- Only state facts supported by the data. If you cannot determine something, put it in data_gaps.
- Distinguish confirmed root cause (engineers agreed on it) from initial hypotheses.
- Cross-reference timestamps across sources to build the timeline.
- All timestamps in UTC.
- Return ONLY valid JSON, no markdown fencing."""


def build_user_message() -> str:
    files = {
        "PAGERDUTY INCIDENT": DATA_DIR / "pagerduty_incident.json",
        "CLOUDWATCH LOGS": DATA_DIR / "cloudwatch_logs.json",
        "PROMETHEUS METRICS": DATA_DIR / "prometheus_metrics.json",
        "GITHUB DEPLOYMENTS": DATA_DIR / "github_deployments.json",
        "INCIDENT CONTEXT (SLACK THREAD)": DATA_DIR / "incident_context.txt",
    }
    sections = []
    for label, path in files.items():
        content = path.read_text()
        sections.append(f"=== {label} ===\n{content}")
    return "\n\n".join(sections)


def call_api(user_message: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = response.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text.strip())


def validate(result: dict) -> None:
    checks = [
        ("affected_service == api-gateway",
         result.get("affected_service", "").lower() == "api-gateway"),
        ("severity == SEV-2",
         result.get("severity", "").upper() == "SEV-2"),
        ("root_cause mentions timeout or PR #12345",
         any(kw in json.dumps(result.get("root_cause", {})).lower()
             for kw in ["timeout", "pr #12345", "pr#12345"])),
        ("trigger_time is around 14:15-14:20 UTC",
         any(ts in result.get("timeline", {}).get("trigger_time_utc", "")
             for ts in ["14:15", "14:20", "22:15", "22:20"])),
        ("resolution mentions rollback",
         any(kw in json.dumps(result.get("resolution", {})).lower()
             for kw in ["rollback", "rolled back"])),
        ("customer_impact severity == degraded_performance",
         result.get("customer_impact", {}).get("severity_assessment") == "degraded_performance"),
        ("data_gaps mentions customers or regional scope",
         any(kw in " ".join(result.get("data_gaps", [])).lower()
             for kw in ["regional", "customer", "region", "which product"])),
        ("internal_details includes rds-prod-main",
         any("rds-prod-main" in d for d in result.get("internal_details_to_exclude", []))),
        ("internal_details includes engineer names",
         any(name in " ".join(result.get("internal_details_to_exclude", []))
             for name in ["alice", "bob", "john"])),
    ]

    print("\n── Validation ──")
    passed = 0
    for label, ok in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label}")
        if ok:
            passed += 1
    print(f"\n{passed}/{len(checks)} checks passed")


def main():
    print("Building prompt...")
    user_message = build_user_message()
    print(f"User message: ~{len(user_message.split())} words\n")

    print("Calling Claude...")
    result = call_api(user_message)

    print("\n── Structured Analysis ──")
    print(json.dumps(result, indent=2))

    validate(result)


if __name__ == "__main__":
    main()
