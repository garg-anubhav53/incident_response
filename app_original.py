import streamlit as st
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Page configuration
st.set_page_config(page_title="Incident Comms Generator", layout="centered")

# System prompts (from existing pipeline files)
EXTRACTION_SYSTEM_PROMPT = """You are an incident analysis engine for a SaaS security platform. You receive raw technical data from multiple sources about a production incident. Extract a structured, accurate analysis.

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
    "mitigation_time_utc": "When fix was deployed (rollback, config change, etc.)",
    "recovery_time_utc": "When metrics returned to baseline",
    "resolved_time_utc": "When incident was declared resolved after monitoring"
  },
  "root_cause": {
    "summary": "Clear technical explanation of what triggered the incident",
    "status": "confirmed | hypothesized | unknown",
    "trigger": "Specific event that caused the incident (deployment, config change, etc.)",
    "mechanism": "How the trigger caused the observed symptoms"
  },
  "customer_impact": {
    "description": "What customers experienced in plain language",
    "severity_assessment": "degraded_performance | partial_outage | full_outage",
    "affected_functionality": ["List of what didn't work for customers"],
    "unaffected_functionality": ["List of what continued working normally"]
  },
  "resolution": {
    "action_taken": "What fixed the incident",
    "confirmed_by": "Evidence that the fix worked (metrics returned to normal, engineer confirmation, etc.)"
  },
  "confidence_scores": {
    "root_cause": "high | medium | low",
    "scope": "high | medium | low",
    "timeline": "high | medium | low",
    "customer_impact": "high | medium | low"
  },
  "source_attribution": {
    "root_cause": ["List of evidence supporting root cause conclusion"],
    "timeline": ["List of evidence supporting timeline reconstruction"],
    "customer_impact": ["List of evidence supporting customer impact assessment"]
  },
  "data_gaps": ["List of important unknowns that the data doesn't answer"],
  "internal_details_to_exclude": ["List of internal details that should not appear in customer communications"]
}"""

GENERATION_SYSTEM_PROMPT = """You are a status page communications writer for an enterprise SaaS security company. You receive a structured incident analysis and generate customer-facing status page updates.

You write in 4 stages: Investigating, Identified, Monitoring, Resolved. Not every incident needs all 4 — use judgment. A fast-resolved incident may skip straight from Investigating to Resolved.

VOICE AND TONE:
- Professional, calm, direct. No panic, no minimizing.
- First person plural ("We are investigating", "Our team has identified").
- Empathetic but not apologetic until Resolved ("We apologize for any inconvenience" only in the final update).
- Never defensive. Never assign blame — not to your own team, not to third parties. If a third-party caused it, say "an upstream service provider" or "an external dependency", never name them.
- No technical jargon. Translate everything to customer experience language.

STRUCTURE PER UPDATE:
- Title: Short, customer-symptom-focused (e.g., "API Performance Degradation", "Portal Access Issues", "Delayed Threat Remediation"). Never include severity codes, internal service names, or root cause in the title.
- Status: Investigating | Identified | Monitoring | Resolved
- Message body (3-5 sentences max):
  1. What's happening (customer-observable symptoms)
  2. What's affected and what's NOT affected (if confirmed in the data — use the unaffected_functionality field)
  3. What we're doing about it
  4. When to expect the next update

RULES:
1. NEVER include anything from the internal_details_to_exclude list. No engineer names, no database hostnames, no PR numbers, no commit SHAs, no internal service names.
2. If data_gaps exist around scope, be honest but not alarming: "Some customers may experience..." rather than "All customers are affected" (when you don't know) or silence (when you do know).
3. Timestamps in PT (Pacific Time), formatted like "2:30 PM PT". Convert from UTC.
4. For the Resolved update, include a brief summary block:
   - Incident start time (approximate)
   - Resolution time
   - Total duration
   - Impact summary (one line)
5. If unaffected_functionality has confirmed items, mention them prominently — especially if detection/security functions are unaffected. For a security product, "detection remained fully operational" is the most reassuring thing you can say.
6. Keep each update under 100 words. Status pages are scanned, not read.
7. For Identified stage, reference the cause abstractly: "a configuration change", "an infrastructure issue", "an upstream service disruption" — never the technical specifics.
8. Include a "Next update in X minutes" commitment in Investigating and Identified stages.
9. The Monitoring stage should reference observable improvement: "response times are returning to normal", "error rates have decreased significantly."

Return ONLY valid JSON, no markdown fencing:

{
  "title": "Customer-facing incident title",
  "communications": [
    {
      "stage": "investigating",
      "posted_at_pt": "2:30 PM PT",
      "message": "Investigating message (3-5 sentences max)..."
    },
    {
      "stage": "identified", 
      "posted_at_pt": "2:45 PM PT",
      "message": "Identified message..."
    },
    {
      "stage": "monitoring",
      "posted_at_pt": "3:15 PM PT", 
      "message": "Monitoring message..."
    },
    {
      "stage": "resolved",
      "posted_at_pt": "4:50 PM PT",
      "message": "Resolved message with summary block..."
    }
  ]
}"""

# CSS styling (from prompt specification)
CSS_STYLES = """
<style>
/* Page config */
body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Top header bar */
.status-header {
    text-align: center;
    padding: 24px 0 16px 0;
    border-bottom: 1px solid #e8e8e8;
    margin-bottom: 32px;
}
.status-header h1 {
    font-size: 22px;
    font-weight: 600;
    color: #333;
    margin: 0;
}

/* Overall status badge — appears below header */
.overall-status {
    text-align: center;
    padding: 12px 0 24px 0;
}
.overall-status .badge {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 500;
}
.badge-resolved { background: #d4edda; color: #155724; }
.badge-degraded { background: #fff3cd; color: #856404; }
.badge-outage   { background: #f8d7da; color: #721c24; }

/* Date group */
.date-group {
    margin-bottom: 32px;
}
.date-label {
    font-size: 14px;
    font-weight: 600;
    color: #555;
    padding-bottom: 8px;
    border-bottom: 1px solid #e0e0e0;
    margin-bottom: 16px;
}

/* Incident card */
.incident-card {
    margin-bottom: 24px;
}
.incident-title {
    font-size: 16px;
    font-weight: 600;
    color: #333;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Colored dot before incident title */
.dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}
.dot-green  { background-color: #2fcc66; }
.dot-yellow { background-color: #f1c40f; }
.dot-orange { background-color: #e67e22; }
.dot-red    { background-color: #e74c3c; }

/* Individual status update entry */
.status-update {
    padding: 0 0 16px 20px;
    border-left: 2px solid #e8e8e8;
    margin-left: 4px;
    margin-bottom: 0;
    position: relative;
}
.status-update:last-child {
    border-left: 2px solid transparent;
}

/* Stage label (bold) */
.stage-label {
    font-weight: 700;
    font-size: 14px;
    margin-bottom: 4px;
}
.stage-resolved      { color: #2fcc66; }
.stage-monitoring    { color: #3498db; }
.stage-identified    { color: #e67e22; }
.stage-investigating { color: #e67e22; }

/* Message body */
.update-message {
    font-size: 14px;
    color: #555;
    line-height: 1.6;
    margin-bottom: 4px;
}

/* Timestamp */
.update-timestamp {
    font-size: 12px;
    color: #999;
    margin-top: 4px;
}

/* Responsive */
.status-container {
    max-width: 720px;
    margin: 0 auto;
    padding: 0 16px;
}

@media (max-width: 768px) {
    .status-container { padding: 0 12px; }
    .incident-title { font-size: 15px; }
    .update-message { font-size: 13px; }
}
</style>
"""

# Inject CSS
st.markdown(CSS_STYLES, unsafe_allow_html=True)

# Header
st.markdown("""
<div class="status-container">
    <div class="status-header">
        <h1>Incident Communications Generator</h1>
    </div>
</div>
""", unsafe_allow_html=True)

# Helper functions
def parse_llm_json(text: str) -> dict:
    """Parse JSON response from Claude, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove first line
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())

def call_claude(system_prompt: str, user_content: str, max_tokens: int, temperature: float = 0.2) -> dict:
    """Send prompt to Claude, parse JSON response, return dict."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        text = response.content[0].text
        return parse_llm_json(text)
    except Exception as e:
        st.error(f"Error calling Claude: {str(e)}")
        raise

def detect_file_type(filename: str, content: str) -> str:
    """Detect file type based on content patterns."""
    content_lower = content.lower()
    filename_lower = filename.lower()
    
    # PagerDuty incident - specific pattern
    if '"incident"' in content_lower and '"urgency"' in content_lower and '"severity"' in content_lower:
        return "pagerduty_incident"
    # GitHub deployments - specific pattern  
    elif '"deployments"' in content_lower and '"pr_number"' in content_lower:
        return "github_deployments"
    # Prometheus metrics - specific pattern
    elif '"metrics"' in content_lower and '"labels"' in content_lower and '"values"' in content_lower:
        return "prometheus_metrics"
    # CloudWatch logs - specific pattern
    elif '"logs"' in content_lower and '"timestamp"' in content_lower and '"level"' in content_lower:
        return "cloudwatch_logs"
    # Incident context - fallback for text files with Slack-like content
    elif filename_lower.endswith('.txt') or ('@' in content and ('pm' in content_lower or 'am' in content_lower)):
        return "incident_context"
    else:
        return "unknown"

def build_user_message(files_by_type: dict) -> str:
    """Build user message from file contents."""
    sections = []
    
    # PagerDuty incident
    if "pagerduty_incident" in files_by_type:
        sections.append("=== PAGERDUTY INCIDENT ===")
        sections.append(files_by_type["pagerduty_incident"])
        sections.append("")
    
    # CloudWatch logs
    if "cloudwatch_logs" in files_by_type:
        sections.append("=== CLOUDWATCH LOGS ===")
        sections.append(files_by_type["cloudwatch_logs"])
        sections.append("")
    
    # Prometheus metrics (summarize if needed)
    if "prometheus_metrics" in files_by_type:
        sections.append("=== PROMETHEUS METRICS ===")
        sections.append(files_by_type["prometheus_metrics"])
        sections.append("")
    
    # GitHub deployments
    if "github_deployments" in files_by_type:
        sections.append("=== GITHUB DEPLOYMENTS ===")
        sections.append(files_by_type["github_deployments"])
        sections.append("")
    
    # Incident context/Slack
    if "incident_context" in files_by_type:
        sections.append("=== INCIDENT CONTEXT ===")
        sections.append(files_by_type["incident_context"])
        sections.append("")
    
    return "\n".join(sections)

def run_extraction(file_contents: dict) -> dict:
    """Run incident extraction pipeline."""
    # Detect file types
    files_by_type = {}
    for filename, content in file_contents.items():
        file_type = detect_file_type(filename, content)
        if file_type != "unknown":
            files_by_type[file_type] = content
    
    # Build user message
    user_message = build_user_message(files_by_type)
    
    # Call Claude
    return call_claude(EXTRACTION_SYSTEM_PROMPT, user_message, max_tokens=4096, temperature=0.2)

def run_generation(extraction: dict) -> dict:
    """Run communication generation pipeline."""
    user_message = json.dumps(extraction, indent=2)
    return call_claude(GENERATION_SYSTEM_PROMPT, user_message, max_tokens=2048, temperature=0.4)

def _extract_date_label(extraction: dict) -> str:
    """Extract date label from timeline."""
    timeline = extraction.get("timeline", {})
    detection_time = timeline.get("detection_time_utc")
    if detection_time:
        try:
            dt = datetime.fromisoformat(detection_time.replace('Z', '+00:00'))
            pt_time = dt.astimezone(timezone(timedelta(hours=-8)))
            return pt_time.strftime("%B %d, %Y")
        except:
            pass
    return "Today"

def render_status_page(comms: dict, extraction: dict):
    """Render the status page output."""
    # Determine dot color and badge from severity
    severity = extraction.get("customer_impact", {}).get("severity_assessment", "degraded_performance")
    dot_class = {
        "degraded_performance": "dot-yellow",
        "partial_outage": "dot-orange", 
        "full_outage": "dot-red"
    }.get(severity, "dot-yellow")
    
    badge_class = {
        "degraded_performance": "badge-degraded",
        "partial_outage": "badge-outage",
        "full_outage": "badge-outage"
    }.get(severity, "badge-degraded")
    
    # Determine if resolved
    communications = comms.get("communications", [])
    if communications:
        last_stage = communications[-1]["stage"]
        is_resolved = last_stage == "resolved"
        if is_resolved:
            dot_class = "dot-green"
            badge_class = "badge-resolved"
        
        badge_text = "Resolved" if is_resolved else severity.replace("_", " ").title()
    else:
        badge_text = "Unknown"
    
    # Overall status badge
    st.markdown(f"""
    <div class="status-container">
        <div class="overall-status">
            <span class="badge {badge_class}">{badge_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Extract date for the date label
    incident_date = _extract_date_label(extraction)
    
    # Build the status page HTML
    # Communications should display in REVERSE chronological order (newest first)
    updates_html = ""
    if communications:
        reversed_comms = list(reversed(communications))
        for i, comm in enumerate(reversed_comms):
            stage = comm["stage"]
            stage_class = f"stage-{stage}"
            stage_display = {
                "investigating": "Investigating",
                "identified": "Identified", 
                "monitoring": "Monitoring",
                "resolved": "Resolved"
            }.get(stage, stage.title())
            
            is_last = i == len(reversed_comms) - 1
            updates_html += f"""
            <div class="status-update" {'style="border-left: 2px solid transparent;"' if is_last else ''}>
                <div class="stage-label {stage_class}">{stage_display}</div>
                <div class="update-message">{comm['message']}</div>
                <div class="update-timestamp">{comm.get('posted_at_pt', '')}</div>
            </div>
            """
    
    st.markdown(f"""
    <div class="status-container">
        <div class="date-group">
            <div class="date-label">{incident_date}</div>
            <div class="incident-card">
                <div class="incident-title">
                    <span class="dot {dot_class}"></span>
                    {comms.get('title', 'Incident')}
                </div>
                {updates_html}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Expandable section: structured extraction details
    with st.expander("📋 Structured Incident Analysis"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Timeline**")
            timeline = extraction.get("timeline", {})
            for key, val in timeline.items():
                if val:
                    label = key.replace("_utc", "").replace("_", " ").title()
                    st.text(f"{label}: {val}")
            
            st.markdown("**Root Cause**")
            rc = extraction.get("root_cause", {})
            st.text(f"Status: {rc.get('status', 'unknown')}")
            st.text(f"Summary: {rc.get('summary', 'N/A')}")
        
        with col2:
            st.markdown("**Confidence**")
            conf = extraction.get("confidence_scores", {})
            for key, val in conf.items():
                emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(val, "⚪")
                st.text(f"{key.title()}: {emoji} {val}")
            
            st.markdown("**Data Gaps**")
            gaps = extraction.get("data_gaps", [])
            for gap in gaps:
                st.text(f"⚠️ {gap}")
        
        st.markdown("**Internal Details Excluded from Communications**")
        excluded = extraction.get("internal_details_to_exclude", [])
        st.code(", ".join(excluded) if excluded else "None identified")

# Sidebar: File upload
with st.sidebar:
    st.header("Upload Incident Data")
    uploaded_files = st.file_uploader(
        "Upload incident data files",
        type=["json", "txt"],
        accept_multiple_files=True,
        help="Upload any combination of: incident_context.txt, cloudwatch_logs.json, prometheus_metrics.json, pagerduty_incident.json, github_deployments.json"
    )
    analyze_btn = st.button("🔍 Analyze Incident", type="primary", use_container_width=True)

# Processing logic
if analyze_btn and uploaded_files:
    file_contents = {}
    for f in uploaded_files:
        file_contents[f.name] = f.read().decode("utf-8")
    
    with st.spinner("Extracting incident data..."):
        try:
            extraction = run_extraction(file_contents)
        except Exception as e:
            st.error(f"Failed to extract incident data: {str(e)}")
            st.stop()
    
    with st.spinner("Generating communications..."):
        try:
            comms = run_generation(extraction)
        except Exception as e:
            st.error(f"Failed to generate communications: {str(e)}")
            st.stop()
    
    # Store in session state
    st.session_state["extraction"] = extraction
    st.session_state["comms"] = comms

# Display results (if available in session state)
if "comms" in st.session_state:
    render_status_page(st.session_state["comms"], st.session_state["extraction"])
