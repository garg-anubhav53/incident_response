import streamlit as st
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
logger.info("=== APP STARTUP ===")
logger.info(f"Python version: {sys.version}")
logger.info(f"Streamlit version: {st.__version__}")
logger.info(f"Current working directory: {os.getcwd()}")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
logger.info(f"Anthropic client initialized, API key present: {bool(os.getenv('ANTHROPIC_API_KEY'))}")

st.set_page_config(
    page_title="Incident Communications Generator",
    page_icon="🚨",
    layout="centered",
    initial_sidebar_state="expanded",
)
logger.info("Streamlit page config set")

# ── CSS ────────────────────────────────────────────────────────────────────────
# Every custom HTML element has an explicit color — never inherited from Streamlit's
# theme (which may be dark). Config.toml forces light base, but we don't rely on it.
#
# Color system:
#   Page bg:    #f0f2f6  (set in .streamlit/config.toml)
#   Card bg:    #ffffff  (content surfaces)
#   Text:       #0f172a (headings) / #334155 (body) / #64748b (labels) / #94a3b8 (muted)
#   Brand:      #4f46e5 → #7c3aed  (indigo-violet gradient)
#   Resolved:   #059669  (emerald-600)
#   Monitoring: #0284c7  (sky-600)
#   Warning:    #d97706  (amber-600)
#   Alert:      #ea580c  (orange-600)
#   Outage:     #dc2626  (red-600)
CSS_STYLES = """
<style>
/* ── Layout ── */
.main .block-container { padding-top: 2rem; max-width: 1100px; }

/* ── Page header banner ── */
.main-header {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    padding: 2.5rem 2rem;
    text-align: center;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 20px rgba(79,70,229,0.3);
}
.main-header h1 {
    margin: 0;
    font-size: 2.1rem;
    font-weight: 800;
    color: #ffffff !important;
    letter-spacing: -0.5px;
}
.main-header p {
    margin: 0.75rem 0 0 0;
    font-size: 1.05rem;
    color: #e0e7ff !important;
}

/* ── Info / feature cards (upload page tiles) ── */
.info-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    color: #334155;
}
.info-card h3 {
    margin: 0 0 0.85rem 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: #0f172a;
}
.info-card p  { margin: 0; color: #475569; font-size: 0.9rem; }
.info-card ul { margin: 0.5rem 0 0 0; padding-left: 1.25rem; color: #475569; font-size: 0.9rem; }
.info-card li { margin-bottom: 0.35rem; }
.info-card li strong { color: #1e293b; }
.info-card em { color: #64748b; }

/* ── Progress step indicators ── */
.progress-step {
    padding: 0.7rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
    border-left: 4px solid #cbd5e1;
    background: #f1f5f9;
    color: #64748b;
}
.progress-step.active {
    border-left-color: #4f46e5;
    background: #eef2ff;
    color: #3730a3;
    font-weight: 600;
}
.progress-step.completed {
    border-left-color: #059669;
    background: #f0fdf4;
    color: #065f46;
    font-weight: 600;
}

/* ── Status page container ── */
.status-container { max-width: 760px; margin: 0 auto; padding: 0 8px; }

/* ── Overall status badge ── */
.overall-status { text-align: center; padding: 16px 0 28px 0; }
.overall-status .badge {
    display: inline-block;
    padding: 8px 22px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
.badge-resolved { background: #059669; color: #ffffff !important; }
.badge-degraded { background: #d97706; color: #ffffff !important; }
.badge-outage   { background: #dc2626; color: #ffffff !important; }

/* ── Date group label ── */
.date-label {
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    padding-bottom: 10px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 18px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* ── Incident card ── */
.incident-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 1.5rem 1.75rem;
    box-shadow: 0 2px 14px rgba(0,0,0,0.08);
    margin-bottom: 24px;
    border: 1px solid #e2e8f0;
}
.incident-title {
    font-size: 16px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* ── Status dots ── */
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.dot-green  { background: #059669; }
.dot-yellow { background: #d97706; }
.dot-orange { background: #ea580c; }
.dot-red    { background: #dc2626; }

/* ── Update timeline entries ── */
.status-update {
    padding: 0 0 18px 22px;
    border-left: 3px solid #e2e8f0;
    margin-left: 5px;
}
.status-update-last { border-left: 3px solid transparent; }

/* ── Stage labels (colored text on white card bg) ── */
.stage-label {
    font-weight: 700;
    font-size: 12px;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stage-resolved      { color: #059669 !important; }
.stage-monitoring    { color: #0284c7 !important; }
.stage-identified    { color: #ea580c !important; }
.stage-investigating { color: #ea580c !important; }

/* ── Update body text ── */
.update-message {
    font-size: 14px;
    color: #334155;
    line-height: 1.7;
    margin-bottom: 4px;
}
.update-timestamp { font-size: 11px; color: #94a3b8; margin-top: 4px; }

/* ── Deployment alert banner (above status page) ── */
.deploy-high {
    background: #fff7ed;
    border: 1px solid #fdba74;
    border-left: 4px solid #ea580c;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.75rem;
    color: #7c2d12;
}
.deploy-high strong { color: #7c2d12; }
.deploy-high code {
    background: #ffedd5;
    color: #9a3412;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
}

/* ── Validation pass message ── */
.val-pass {
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-left: 4px solid #059669;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.5rem;
    color: #14532d;
    font-weight: 600;
    font-size: 0.95rem;
}

/* ── Security function impact badges (next to severity badge) ── */
.sfi-badge {
    display: inline-block;
    padding: 8px 18px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-left: 10px;
    vertical-align: middle;
}
.sfi-badge-detection    { background: #dc2626; color: #ffffff !important; }
.sfi-badge-remediation  { background: #ea580c; color: #ffffff !important; }
.sfi-badge-operational  { background: #059669; color: #ffffff !important; }
.sfi-badge-unknown      { background: #94a3b8; color: #ffffff !important; }

/* ── Security function status pills (in structured analysis expander) ── */
.sfi-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 4px;
}
.sfi-operational { background: #f0fdf4; color: #065f46; border: 1px solid #bbf7d0; }
.sfi-degraded    { background: #fefce8; color: #713f12; border: 1px solid #fde68a; }
.sfi-offline     { background: #fef2f2; color: #7f1d1d; border: 1px solid #fecaca; }
.sfi-unknown     { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }
</style>
"""
st.markdown(CSS_STYLES, unsafe_allow_html=True)

# ── Extraction system prompt ───────────────────────────────────────────────────
EXTRACTION_SYSTEM_PROMPT = """You are an incident analysis engine for a SaaS security platform. You receive raw technical data from multiple sources about a production incident. Extract a structured, accurate analysis.

CRITICAL RULES:
0. NULL OVER HALLUCINATION (OVERRIDES ALL): If a required field cannot be determined from the provided data, use null for scalar fields and [] for arrays. Never invent plausible-sounding values. A confident-looking fabrication is worse than an explicit null. When uncertain, be explicitly uncertain.
1. NEVER state a fact without source support. If you cannot determine something, say so in data_gaps with a specific explanation of what is missing and why it matters.
2. Distinguish CONFIRMED root cause (engineers said "found it", "confirmed", "that's it") from HYPOTHESIS ("I think", "maybe", "could be"). Set root_cause.status accordingly. ROLLBACK = CONFIRMATION: if a rollback of a specific deployment resolves the incident, set root_cause.status="confirmed" even without an explicit engineer statement — a successful rollback is confirmation in action.
3. Cross-reference timestamps across ALL sources. Flag inconsistencies in data_gaps.
4. A deployment is root cause ONLY IF: deployed to SAME failing service AND timing correlates AND (engineers confirmed OR rollback fixed it). Unrelated deploys: note in inference_log but do not attribute causation.
5. For metrics: baseline = pre-incident normal (first 2 readings). Anomaly = >2x or <0.5x baseline. Note if recovery is gradual or sudden. Cite specific timestamp-value pairs — do not summarize to counts.
6. For scope: only state what data proves. If data mentions only one region/service, flag others as unconfirmed — do NOT assume unaffected.
7. EXCLUDE from customer comms: engineer emails, internal hostnames, cluster names, PR numbers, commit SHAs, internal Slack channels. List ALL found in internal_details_to_exclude.
8. Map technical symptoms to customer experience: connection pool exhaustion → "API performance degradation"; 500 errors → "intermittent errors" (partial) or "service unavailable" (total); auth failures → "login issues"; detection pipeline errors → "delayed threat detection" (URGENT — security product).
9. Severity: degraded_performance = works but slow, most requests succeed; partial_outage = significant error rate but partially functional; full_outage = nearly all requests failing.
10. Timeline: use EARLIEST corroborating signal for onset (often metrics, before the alert). Use LATEST confirmation for resolution (post-monitoring). Alert time = detection, not onset.
11. PATTERN CLASSIFICATION: Classify into exactly one primary pattern. Definitions — deployment_induced: code/config deploy correlates with onset AND confirmed by engineers or rollback fixed it; infrastructure_cascade: multiple services fail simultaneously, no deployment trigger; regional_failure: errors scoped to a specific region; portal_auth_failure: UI/login errors but core processing (email, detection) unaffected; third_party_dependency: errors reference external APIs (Microsoft Graph, AWS, etc.) with no internal cause; integration_api_failure: outbound webhooks/SIEM/SOAR failing, core product fine; silent_degradation: no hard errors but quality metrics drift; isolated_environment: Gov/FedRAMP-scoped. If ambiguous, pick the stronger pattern and explicitly note the alternative in reasoning. NOTE: portal_auth_failure is INCOMPATIBLE with detection_status=degraded/offline — portal issues do not impair detection. Flag any such combination in data_gaps.
12. INFERENCE LOG: Log the inference chain for key factual claims only — not every observation. inference_type values: direct_observation (fact explicitly stated in one source), cross_reference (derived by correlating multiple sources), absence_of_evidence (conclusion based on what's NOT in the data), engineer_confirmation (engineers explicitly agreed in Slack). Cap at 10 entries total. Priority: (1) all engineer_confirmation entries, (2) cross_reference entries where multiple sources were correlated, (3) direct_observation for root cause, onset time, and recovery only. Include absence_of_evidence only when the absence materially affects confidence in a high-stakes claim. Omit trivial observations such as "no resolved timestamp was found" or restatements of alert data.
13. SECURITY FUNCTION CLASSIFICATION: Classify what security function is impacted. Detection signals: IES/email scanning errors, threat scoring failures, ML model errors, ATO monitoring failures, AIPC errors, engineers mentioning missed threats. Remediation signals: quarantine/deletion errors, Microsoft Graph failures, SOAR errors, threats detected but automated response broken. Other signals: portal/auth errors (detection unaffected), SIEM delivery, EPR, notification delays, infrastructure confirmed not impacting security pipeline. CRITICAL safeguards — (a) For ambiguous service names (api-gateway, platform), classify from symptoms and engineer discussion, NOT service name alone. (b) If engineers confirm detection unaffected, set detection_status=fully_operational. (c) If uncertain whether detection is impacted, set detection_status=unknown and add to data_gaps — NEVER default to fully_operational when uncertain. (d) When ambiguous, classify toward higher severity: detection > remediation > other.
14. EVIDENCE TRACE: For each of the 5 verification questions (what_is_broken, what_caused_it, when_did_it_happen, what_is_not_broken, how_bad_is_it), cite specific raw evidence from the source data. Requirements: (a) raw_excerpt must be verbatim — copy exact log lines, exact Slack messages with author+timestamp, exact metric values as "metric_name: value at timestamp." Never paraphrase. (b) For metrics, cite baseline values, first anomalous value, peak, and recovery point as specific timestamp-value pairs from the RAW ANOMALOUS VALUES section if present. (c) Always populate counter_evidence — include anything that weakens the conclusion, even if later dismissed. Empty array only if truly nothing contradicts. (d) For what_is_not_broken: do NOT merely list service names that seem fine. Cite a specific absence: "No errors appear for [service] in [filename] during the incident window" — OR cite an explicit engineer statement. If you cannot find either, use a single evidence item with raw_excerpt="No error data found for this service in any provided source" and relevance="Absence of evidence — weaker than positive confirmation." Never claim a service is unaffected based solely on its name. (e) verification_suggestion must be a specific action the IC can complete in under 2 minutes (check a named dashboard, ask a specific person, run a specific query — never a generic "review logs").

NOTE ON THE THREE CONFIDENCE STRUCTURES: confidence_scores gives aggregate confidence by analysis dimension (root_cause, scope, timeline, customer_impact). inference_log gives per-claim confidence with source attribution. evidence_trace gives per-verification-question evidence with actionable IC steps. All three must be fully populated — they serve different consumers and are not redundant.

Return ONLY valid JSON, no markdown fencing:

{
  "incident_summary": "One sentence: what happened, to what service(s), for how long, at what severity",
  "affected_service": "Primary service from alert data",
  "affected_products": ["Customer-facing product names if determinable, otherwise 'unknown'"],
  "severity": "From PagerDuty if available",
  "timeline": {
    "cause_time_utc": "When the triggering event occurred — null if unknown",
    "onset_time_utc": "When degradation first appeared in metrics/logs",
    "detection_time_utc": "When alert fired or engineers noticed",
    "acknowledged_time_utc": "When engineer responded",
    "mitigation_time_utc": "When fix was deployed",
    "recovery_time_utc": "When metrics returned to baseline",
    "resolved_time_utc": "When incident was formally closed"
  },
  "root_cause": {
    "summary": "One sentence confirmed root cause, or 'not confirmed in available data'",
    "status": "confirmed | hypothesized | unknown",
    "trigger": "Specific causal event, or null",
    "mechanism": "How trigger caused impact, or null"
  },
  "customer_impact": {
    "description": "What customers experienced in plain language",
    "severity_assessment": "degraded_performance | partial_outage | full_outage",
    "affected_functionality": ["what didn't work"],
    "unaffected_functionality": ["what continued working — only if confirmed"]
  },
  "resolution": {
    "action_taken": "What fixed the incident",
    "confirmed_by": "Evidence of recovery"
  },
  "confidence_scores": {
    "root_cause": "high | medium | low",
    "scope": "high | medium | low",
    "timeline": "high | medium | low",
    "customer_impact": "high | medium | low"
  },
  "source_attribution": {
    "root_cause": ["evidence supporting root cause"],
    "timeline": ["evidence for timestamps"],
    "customer_impact": ["evidence for impact assessment"]
  },
  "pattern_classification": {
    "primary_pattern": "deployment_induced | infrastructure_cascade | regional_failure | portal_auth_failure | third_party_dependency | integration_api_failure | silent_degradation | isolated_environment | unknown",
    "confidence": "high | medium | low",
    "reasoning": "2-3 sentences: why this pattern, what evidence supports it, any alternative considered"
  },
  "security_function_impact": {
    "primary_category": "detection | remediation | other",
    "secondary_category": "detection | remediation | other | null",
    "confidence": "high | medium | low",
    "reasoning": "2-3 sentences: what evidence connects the failing service to this security function category",
    "detection_status": "fully_operational | degraded | offline | unknown",
    "remediation_status": "fully_operational | degraded | offline | unknown"
  },
  "inference_log": [
    {
      "claim": "What was inferred",
      "sources": ["data points supporting this"],
      "inference_type": "direct_observation | cross_reference | absence_of_evidence | engineer_confirmation",
      "confidence": "high | medium | low"
    }
  ],
  "evidence_trace": [
    {
      "question": "what_is_broken | what_caused_it | when_did_it_happen | what_is_not_broken | how_bad_is_it",
      "conclusion": "One sentence answer to this verification question",
      "evidence": [
        {"source_file": "filename.json", "raw_excerpt": "Verbatim text or data from source", "relevance": "Why this supports the conclusion"}
      ],
      "counter_evidence": [
        {"source_file": "filename", "raw_excerpt": "Verbatim text", "relevance": "Why this weakens the conclusion"}
      ],
      "verification_suggestion": "Specific actionable step the IC can take in under 2 minutes"
    }
  ],
  "data_gaps": ["Important unknowns — be specific about what's missing and why it matters"],
  "internal_details_to_exclude": ["Internal names, emails, hostnames, PRs, SHAs found in the data"]
}"""

# ── Generation system prompt ───────────────────────────────────────────────────
GENERATION_SYSTEM_PROMPT = """You are a status page communications writer for an enterprise SaaS security company. Generate customer-facing status page updates from a structured incident analysis.

Write in 2–4 stages: Investigating, Identified, Monitoring, Resolved. Always generate Investigating and Resolved. Apply these skip rules strictly — fewer stages is better than padding with low-information updates:
- SKIP Identified if: root_cause.status is "unknown" OR root_cause.status is "hypothesized" with low or medium confidence. Never write an Identified stage without a confirmed or high-confidence root cause.
- SKIP Monitoring if: the incident resolved within 30 minutes of mitigation, OR mitigation_time_utc and resolved_time_utc are within 15 minutes, OR both are null (fast rollback or unknown timeline). When detection or remediation was impaired, Monitoring is valuable — keep it in those cases regardless of timing.
- Return only the stages that apply. Do NOT return empty-string entries or placeholder objects for skipped stages.

VOICE AND TONE:
- Professional, calm, direct. No panic, no minimizing.
- First person plural ("We are investigating", "Our team has identified").
- Never defensive. Never name third parties — say "an external dependency" or "an upstream service provider."
- No technical jargon. Translate to customer experience language.

TITLE: Short, customer-symptom-focused ("API Performance Degradation", "Portal Access Issues"). Never include severity codes, internal service names, or root cause.

MESSAGE STRUCTURE — compose every stage message with sentences in this exact order. This is the sentence structure, not just a field list:
1. WHAT HAPPENED + TIMESTAMP: Lead with what is happening/happened and when. ("Starting around 2:20 PM PT, we are investigating an issue affecting...")
2. WHAT IS NOT AFFECTED — THIS IS THE SECOND SENTENCE, MANDATORY, NEVER MOVED OR TRIMMED: Explicitly state what continues working. Never position this later in the message for any reason.
3. CUSTOMER IMPACT: What customers are experiencing in plain language.
4. WHAT WE ARE DOING: Engineering team action.
5. CUSTOMER ACTION (ALL stages including Investigating): "No action is required at this time." Resolved: "If you continue to experience issues, please contact our support team."
6. NEXT UPDATE TIMING (omit for Resolved): "We will provide an update within 30 minutes."

Sentence 2 content depends on detection_status and remediation_status (see URGENCY CALIBRATION). Never omit sentence 2. If word count must be reduced, cut sentences 4 or 6 first.

URGENCY CALIBRATION — sentence 2 content is determined by detection_status and remediation_status. Use the exact language below. Do not infer status independently.
- detection_status "degraded": Sentence 2 MUST state the active risk: "Email security detection is currently degraded, and some threats may not be detected or acted upon automatically." Do NOT use reassurance language. Do NOT say detection is operational.
- detection_status "offline": Sentence 2 MUST state: "Email security detection is currently offline, and threats may not be detected or remediated automatically." Title must reference threat detection or email security.
- remediation_status "degraded" or "offline", detection operational: Sentence 2: "Email security detection remains fully operational; however, automated remediation [is degraded / is offline], and detected threats should be reviewed manually in the portal."
- Both fully_operational (primary_category=other): Sentence 2: "Email security detection and automated remediation remain fully operational and continue to protect against threats."
- detection_status "unknown": Sentence 2: "We are confirming the status of email security detection services and will provide an update shortly." Do NOT say detection is operational or degraded.

RULES:
1. NEVER include anything from internal_details_to_exclude. No engineer names, hostnames, PR numbers, commit SHAs.
2. Timestamps in PT (Pacific Time) formatted "2:30 PM PT". Convert from UTC. DST: March–October = PDT = UTC-7; November–February = PST = UTC-8. Always label as "PT" (not PST or PDT).
3. Resolved update: include start time, resolution time, total duration, and one-line impact summary.
4. Keep each update under 100 words. If you must trim, cut in this order: (1) the next-update timing detail, (2) extra impact description, (3) timestamp precision. NEVER cut field #2 (what's not affected).
5. Identified stage: reference cause abstractly ("a configuration change", "an infrastructure issue", "an upstream service disruption"). If root_cause.status="confirmed", say "we have identified [abstract cause]." If "hypothesized", say "we believe we have identified what appears to be [abstract cause] and are working to confirm."

EXAMPLE of a correctly-structured Investigating update (79 words):
"We are investigating an issue affecting [service name] that began around 2:20 PM PT. Email security detection and automated remediation remain fully operational and continue to protect against threats. Some customers may experience [plain-language impact description]. Our engineering team is actively working to identify the cause and restore full service. We will provide an update within 30 minutes. No action is required at this time."

Return ONLY valid JSON, no markdown fencing:

{
  "title": "Customer-facing incident title",
  "communications": [
    {"stage": "investigating", "posted_at_pt": "2:30 PM PT", "message": "..."},
    {"stage": "identified",    "posted_at_pt": "2:45 PM PT", "message": "..."},
    {"stage": "monitoring",    "posted_at_pt": "3:15 PM PT", "message": "..."},
    {"stage": "resolved",      "posted_at_pt": "4:50 PM PT", "message": "..."}
  ]
}"""


# ── LLM helpers ───────────────────────────────────────────────────────────────
def parse_llm_json(text: str) -> dict:
    original_text = text
    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]

    # Find the end of the outermost JSON object/array (handle trailing text)
    brace_count = 0
    bracket_count = 0
    in_string = False
    escape_next = False
    json_end = -1
    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
            if brace_count == 0 and bracket_count == 0 and i > 0:
                json_end = i + 1
                break
    if json_end > 0:
        text = text[:json_end]

    try:
        result = json.loads(text.strip())
        logger.info(f"parse_llm_json: OK — {len(original_text)} chars in, keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"parse_llm_json FAILED: {e}")
        logger.error(f"--- RAW LLM RESPONSE ({len(original_text)} chars) ---")
        # Log in 2000-char chunks so nothing is truncated
        for i in range(0, len(original_text), 2000):
            logger.error(original_text[i:i+2000])
        logger.error("--- END RAW LLM RESPONSE ---")
        raise


# ── Configuration ───────────────────────────────────────────────────────────────
# ⚙️  TOKEN LIMITS - Easy to adjust for different use cases:
# - extraction: Complex incident analysis with inference logs (needs more tokens)
# - generation: Multi-stage communications (moderate tokens)
# - default: Fallback for other calls
# 💡 Increase these if you get JSON truncation errors, decrease to save costs
TOKEN_LIMITS = {
    "extraction": 24000,   # Complex incident analysis with inference logs (4x increased)
    "generation": 16000,   # Multi-stage communications (4x increased)
    "default": 8000       # Fallback for other calls (4x increased)
}

# ── LLM helpers ───────────────────────────────────────────────────────────────
def call_claude(user_message: str, system_prompt: str, max_tokens: int = None, temperature: float = 0.2, model: str = "claude-sonnet-4-5") -> dict:
    if max_tokens is None:
        max_tokens = TOKEN_LIMITS["default"]

    api_key = os.getenv("ANTHROPIC_API_KEY")
    logger.info(f"call_claude: model={model} max_tokens={max_tokens} temp={temperature} "
                f"user_msg={len(user_message)}chars system={len(system_prompt)}chars "
                f"api_key={'SET ('+api_key[:8]+'...)' if api_key else 'MISSING'}")

    import traceback as _tb
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_message}],
            system=system_prompt,
            stream=True,
        )

        content = ""
        stop_reason = None
        for chunk in response:
            if chunk.type == "content_block_delta":
                content += chunk.delta.text
            elif chunk.type == "message_delta":
                stop_reason = getattr(chunk.delta, "stop_reason", None)

        logger.info(f"call_claude: stream done — {len(content)} chars received, stop_reason={stop_reason}")
        if stop_reason == "max_tokens":
            logger.warning("call_claude: RESPONSE TRUNCATED (hit max_tokens) — JSON may be incomplete")

        result = parse_llm_json(content)
        logger.info(f"call_claude: SUCCESS — result keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
        return result

    except Exception as e:
        logger.error(f"call_claude FAILED: {type(e).__name__}: {e}")
        logger.error("call_claude TRACEBACK:\n" + _tb.format_exc())
        raise


# ── File detection & preprocessing ────────────────────────────────────────────
def detect_file_type(filename: str, content: str) -> str:
    cl = content.lower()
    fn = filename.lower()
    if fn.startswith("pagerduty") or ('"incident"' in cl and '"severity"' in cl and '"urgency"' in cl):
        return "pagerduty_incident"
    elif fn.startswith("cloudwatch") or fn.startswith("app_logs") or ("loggroup" in cl or "logstream" in cl):
        return "cloudwatch_logs"
    elif fn.startswith("prometheus") or ("metric" in cl and ("timestamp" in cl or "value" in cl)):
        return "prometheus_metrics"
    elif fn.startswith("github") or ("deployments" in cl and ("timestamp" in cl or "service" in cl)):
        return "github_deployments"
    elif "slack" in fn or ("channel" in cl and "user" in cl and "ts" in cl):
        return "slack_thread"
    elif "incident" in fn or ("summary" in cl and ("timeline" in cl or "impact" in cl)):
        return "incident_context"
    return "unknown"


def _parse_prometheus(data: dict) -> list:
    """Return [(name, labels_str, [(ts, val)])] from either Prometheus format."""
    logger.info(f"=== _parse_prometheus STARTED ===")
    logger.info(f"Input data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
    
    result = []
    
    try:
        if "metrics" in data:
            logger.info("Processing 'metrics' format")
            metrics = data["metrics"]
            logger.info(f"Found {len(metrics)} metrics")
            
            for i, m in enumerate(metrics):
                logger.info(f"Processing metric {i+1}/{len(metrics)}")
                name = m.get("metric_name", "metric")
                labels = ",".join(f"{k}={v}" for k, v in m.get("labels", {}).items())
                values = [(v["timestamp"], float(v["value"])) for v in m.get("values", [])]
                logger.info(f"Metric {name}: {len(values)} values")
                result.append((name, labels, values))
                
        elif "data" in data and "result" in data["data"]:
            logger.info("Processing Prometheus query API format")
            for r in data["data"]["result"]:
                name = r["metric"].get("__name__", "metric")
                labels = ",".join(f"{k}={v}" for k, v in r["metric"].items() if k != "__name__")
                values = [(v[0], float(v[1])) for v in r.get("values", [])]
                logger.info(f"Metric {name}: {len(values)} values")
                result.append((name, labels, values))
        else:
            logger.warning("Unknown Prometheus data format")
            
        logger.info(f"=== _parse_prometheus COMPLETED: {len(result)} metrics parsed ===")
        return result
        
    except Exception as e:
        logger.error(f"Error parsing Prometheus data: {e}")
        logger.info("=== _parse_prometheus FAILED ===")
        return []


def _is_anomalous(val: float, baseline: float) -> bool:
    logger.debug(f"Checking anomaly: val={val}, baseline={baseline}")
    if baseline == 0:
        is_anomalous = val > 0
        logger.debug(f"Baseline=0, anomaly check: {is_anomalous}")
        return is_anomalous
    is_anomalous = val > 2 * baseline or val < 0.5 * baseline
    logger.debug(f"Anomaly check result: {is_anomalous}")
    return is_anomalous


def summarize_metrics(content: str) -> str:
    """Summarize Prometheus metrics for LLM input.

    Returns a two-section string:
    - METRIC SUMMARY: human-readable overview (anomalous vs normal per metric)
    - RAW ANOMALOUS VALUES: verbatim timestamp-value pairs for anomalous series only,
      enabling the evidence trace to cite exact metric readings.
    """
    logger.info(f"=== summarize_metrics STARTED ===")
    logger.info(f"Content length: {len(content)} chars")

    try:
        data = json.loads(content)
        logger.info("JSON parsed successfully")
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return "Metrics parsing failed"

    summary_lines = []
    raw_anomalous = {}

    try:
        for name, labels, values in _parse_prometheus(data):
            logger.info(f"Processing metric: {name} with {len(values)} values")
            if len(values) < 3:
                logger.warning(f"Skipping {name}: insufficient values ({len(values)})")
                continue

            baseline = (values[0][1] + values[1][1]) / 2
            logger.info(f"Baseline for {name}: {baseline:.4f}")

            anomalies = [(ts, val) for ts, val in values[2:] if _is_anomalous(val, baseline)]

            if anomalies:
                first_ts, first_val = anomalies[0]
                peak_ts, peak_val = max(anomalies, key=lambda x: abs(x[1] - baseline))
                logger.info(f"Found {len(anomalies)} anomalies in {name}; first={first_val:.4f}@{first_ts}, peak={peak_val:.4f}@{peak_ts}")
                summary_lines.append(
                    f"{name}: {len(anomalies)} anomalies — "
                    f"baseline={baseline:.4f}, first anomaly={first_val:.4f} at {first_ts}, "
                    f"peak={peak_val:.4f} at {peak_ts}"
                )
                raw_anomalous[name] = [
                    {"timestamp": ts, "value": round(val, 6)} for ts, val in anomalies
                ]
            else:
                logger.info(f"No anomalies found in {name}")
                summary_lines.append(f"{name}: normal (baseline={baseline:.4f})")

        if not summary_lines:
            return "No metrics data"

        result = "METRIC SUMMARY:\n" + "\n".join(summary_lines)
        if raw_anomalous:
            result += "\n\nRAW ANOMALOUS VALUES (cite these verbatim in evidence_trace):\n"
            result += json.dumps(raw_anomalous, indent=2)

        logger.info(f"=== summarize_metrics COMPLETED: {len(summary_lines)} metrics, {len(raw_anomalous)} anomalous ===")
        return result

    except Exception as e:
        logger.error(f"Error summarizing metrics: {e}")
        logger.info("=== summarize_metrics FAILED ===")
        return "Metrics summarization failed"


def build_user_message(file_contents: dict, deployment_flags: list = None) -> str:
    """Build the extraction user message from raw file contents.

    Detects each file's type, routes it to the correct section, and annotates
    each section header with the original filename so the LLM can produce
    accurate source_file citations in evidence_trace.
    """
    logger.info(f"=== build_user_message STARTED ===")
    logger.info(f"Input files: {list(file_contents.keys())}")
    logger.info(f"Deployment flags: {len(deployment_flags) if deployment_flags else 0} items")

    # Detect types and build type→(filename, content) map (last file wins per type)
    typed: dict[str, tuple[str, str]] = {}
    for filename, content in file_contents.items():
        ftype = detect_file_type(filename, content)
        typed[ftype] = (filename, content)
        logger.info(f"Routed {filename} → {ftype}")

    order = [
        ("pagerduty_incident",  "PAGERDUTY INCIDENT"),
        ("cloudwatch_logs",     "CLOUDWATCH LOGS"),
        ("prometheus_metrics",  "PROMETHEUS METRICS (pre-processed)"),
        ("github_deployments",  "GITHUB DEPLOYMENTS"),
        ("incident_context",    "INCIDENT CONTEXT (SLACK THREAD)"),
    ]

    sections = []
    for ftype, label in order:
        if ftype not in typed:
            logger.debug(f"Skipping {label} - not found in files")
            continue
        filename, content = typed[ftype]
        logger.info(f"Adding section: {label} (source: {filename})")
        if ftype == "prometheus_metrics":
            content = summarize_metrics(content)
        # Include filename so LLM can cite it verbatim in evidence_trace.source_file
        sections.append(f"=== {label} (filename: {filename}) ===\n{content}")

    if deployment_flags:
        logger.info("Adding deployment correlation section")
        sections.append(
            "=== PRE-COMPUTED DEPLOYMENT CORRELATION ===\n"
            + json.dumps(deployment_flags, indent=2)
            + "\n\nUse this to inform root cause analysis, but verify with other sources before confirming causation."
        )
    else:
        logger.debug("No deployment flags to add")

    result = "\n\n".join(sections)
    logger.info(f"Built user message with {len(sections)} sections, total length: {len(result)} chars")
    logger.info("=== build_user_message COMPLETED ===")
    return result


# ── Deployment correlation ─────────────────────────────────────────────────────
def correlate_deployments(file_contents: dict) -> list:
    logger.info("=== Deployment Correlation Started ===")
    logger.info(f"Input files: {list(file_contents.keys())}")
    
    try:
        pd_content = next((v for k, v in file_contents.items()
                           if detect_file_type(k, v) == "pagerduty_incident"), None)
        gh_content = next((v for k, v in file_contents.items()
                           if detect_file_type(k, v) == "github_deployments"), None)
        pm_content = next((v for k, v in file_contents.items()
                           if detect_file_type(k, v) == "prometheus_metrics"), None)

        logger.info(f"Found files - PagerDuty: {bool(pd_content)}, GitHub: {bool(gh_content)}, Prometheus: {bool(pm_content)}")

        if not gh_content:
            logger.info("No GitHub deployments found, returning empty list")
            return []

        onset_dt = None
        alert_service = ""

        if pd_content:
            logger.info("Processing PagerDuty content for onset time")
            try:
                pd = json.loads(pd_content)
                inc = pd.get("incident", {})
                alert_service = inc.get("service", "").lower()
                created = inc.get("created_at")
                logger.info(f"PagerDuty service: {alert_service}, created_at: {created}")
                if created:
                    onset_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    logger.info(f"Onset time from PagerDuty: {onset_dt}")
            except Exception as e:
                logger.error(f"Error processing PagerDuty content: {e}")

        # Check Prometheus for an earlier signal using multi-metric consensus.
        # A single anomalous reading can be a transient spike; require at least
        # 2 metrics anomalous in the same 5-minute window before trusting the signal.
        if pm_content:
            logger.info("Checking Prometheus for earlier onset signal (multi-metric consensus)")
            try:
                pm_data = json.loads(pm_content)
                # Collect first-anomaly timestamp per metric
                metric_first_anomalies: list[datetime] = []
                for name, labels, values in _parse_prometheus(pm_data):
                    if len(values) < 3:
                        continue
                    baseline = (values[0][1] + values[1][1]) / 2
                    for ts, val in values[2:]:
                        if _is_anomalous(val, baseline):
                            try:
                                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                metric_first_anomalies.append(ts_dt)
                                logger.debug(f"First anomaly in {name}: {ts_dt}")
                            except Exception:
                                pass
                            break  # only first anomaly per metric

                # Find earliest window where ≥2 metrics are simultaneously anomalous
                metric_first_anomalies.sort()
                for i, t in enumerate(metric_first_anomalies):
                    window_end = t + timedelta(minutes=5)
                    count_in_window = sum(1 for t2 in metric_first_anomalies if t <= t2 <= window_end)
                    if count_in_window >= 2:
                        if onset_dt is None or t < onset_dt:
                            onset_dt = t
                            logger.info(f"Prometheus multi-metric onset ({count_in_window} metrics): {onset_dt}")
                        break
            except Exception as e:
                logger.error(f"Error processing Prometheus content: {e}")

        if onset_dt is None:
            logger.info("No onset time detected, returning empty list")
            return []

        logger.info(f"Final onset time: {onset_dt}")
        gh = json.loads(gh_content)
        pre_window_start  = onset_dt - timedelta(minutes=60)
        post_window_end   = onset_dt + timedelta(minutes=30)
        logger.info(f"Pre-onset window: {pre_window_start} → {onset_dt}")
        logger.info(f"Post-onset window: {onset_dt} → {post_window_end}")

        flagged = []

        for deploy in gh.get("deployments", []):
            ts_str = deploy.get("timestamp")
            if not ts_str:
                continue
            try:
                d_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                continue

            in_pre  = pre_window_start <= d_dt <= onset_dt
            in_post = onset_dt < d_dt <= post_window_end
            if not (in_pre or in_post):
                continue

            svc      = deploy.get("service", "").lower()
            same_svc = bool(alert_service and svc and (alert_service in svc or svc in alert_service))

            if in_pre:
                mins_before = int((onset_dt - d_dt).total_seconds() / 60)
                relevance = "HIGH" if same_svc else "LOW"
                timing_label = f"{mins_before}min before onset"
            else:
                mins_after = int((d_dt - onset_dt).total_seconds() / 60)
                relevance = "POST-ONSET"
                timing_label = f"{mins_after}min after onset"
                mins_before = -mins_after  # negative = after onset

            flagged.append({
                "service":               deploy.get("service", "unknown"),
                "title":                 deploy.get("title", deploy.get("description", "Deployment")),
                "author":                deploy.get("author", "unknown"),
                "timestamp":             ts_str,
                "minutes_before_onset":  mins_before,
                "timing_label":          timing_label,
                "same_service_as_alert": same_svc,
                "relevance":             relevance,
                "description":           deploy.get("description", ""),
            })
            logger.info(f"Flagged deployment: {deploy.get('service')} - {timing_label} - {relevance}")

        # Sort: HIGH first, then LOW by timing, POST-ONSET last
        order_map = {"HIGH": 0, "LOW": 1, "POST-ONSET": 2}
        flagged.sort(key=lambda d: (order_map.get(d["relevance"], 9), abs(d["minutes_before_onset"])))
        logger.info(f"Deployment correlation completed: {len(flagged)} deployments flagged")
        return flagged
    except Exception as e:
        logger.error(f"Deployment correlation failed: {e}")
        return []


# ── Pipeline calls ─────────────────────────────────────────────────────────────
def run_extraction(file_contents: dict, deployment_flags: list) -> dict:
    logger.info(f"run_extraction: {len(file_contents)} files={list(file_contents.keys())} flags={len(deployment_flags)}")
    user_message = build_user_message(file_contents, deployment_flags)
    logger.info(f"run_extraction: user_message built ({len(user_message)} chars), calling Claude...")
    result = call_claude(user_message, EXTRACTION_SYSTEM_PROMPT, max_tokens=TOKEN_LIMITS["extraction"])
    logger.info(f"run_extraction: DONE keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
    return result


def run_generation(extraction: dict) -> dict:
    logger.info(f"run_generation: extraction keys={list(extraction.keys()) if isinstance(extraction, dict) else type(extraction).__name__}")
    extraction_json = json.dumps(extraction, indent=2)
    logger.info(f"run_generation: payload {len(extraction_json)} chars, calling Claude...")
    result = call_claude(extraction_json, GENERATION_SYSTEM_PROMPT, max_tokens=TOKEN_LIMITS["generation"])
    logger.info(f"run_generation: DONE keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")

    STAGE_ORDER = {"investigating": 0, "identified": 1, "monitoring": 2, "resolved": 3}
    if isinstance(result, dict) and "communications" in result:
        result["communications"].sort(key=lambda c: STAGE_ORDER.get(c.get("stage", ""), 99))
        logger.info(f"run_generation: stages sorted={[c.get('stage') for c in result['communications']]}")

    return result


# ── Inference log persistence ──────────────────────────────────────────────────
def save_inference_log(extraction: dict) -> None:
    logger.info("=== Saving Inference Log ===")
    try:
        log_dir = Path("inference_logs")
        log_dir.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log = {
            "analysis_timestamp":     datetime.now(timezone.utc).isoformat(),
            "incident_summary":       extraction.get("incident_summary", ""),
            "severity":               extraction.get("severity", ""),
            "pattern_classification": extraction.get("pattern_classification", {}),
            "security_function_impact": extraction.get("security_function_impact", {}),
            "inference_log":          extraction.get("inference_log", []),
            "evidence_trace":         extraction.get("evidence_trace", []),
            "confidence_scores":      extraction.get("confidence_scores", {}),
            "data_gaps":              extraction.get("data_gaps", []),
        }
        log_file = log_dir / f"{ts}.json"
        log_file.write_text(json.dumps(log, indent=2))
        logger.info(f"Inference log saved to: {log_file}")
    except Exception as e:
        logger.error(f"Failed to save inference log: {e}")
        pass  # never crash the app on logging failure


def load_inference_logs(limit: int = 5) -> list:
    logger.info(f"=== Loading Inference Logs (limit={limit}) ===")
    log_dir = Path("inference_logs")
    if not log_dir.exists():
        logger.info("Inference logs directory does not exist")
        return []
    logs = []
    for f in sorted(log_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            logs.append(json.loads(f.read_text()))
            logger.info(f"Loaded inference log: {f}")
        except Exception as e:
            logger.error(f"Failed to load inference log {f}: {e}")
            pass
    logger.info(f"Loaded {len(logs)} inference logs")
    return logs


# ── Communications validation ─────────────────────────────────────────────────
def validate_communications(comms: dict, extraction: dict = None) -> list:
    logger.info("=== Communications Validation Started ===")
    logger.info(f"Input communications keys: {list(comms.keys()) if isinstance(comms, dict) else 'Not a dict'}")

    UNAFFECTED_KW  = ["not affected", "remain", "operating normally", "fully operational",
                      "continue to", "not impacted", "not reporting issues", "unaffected",
                      "still working", "remains fully"]
    IMPACT_KW      = ["may experience", "experiencing", "some customers", "customers may",
                      "impacted", "affected", "unable to", "slow", "errors", "unavailable",
                      "degraded", "delays", "intermittent"]
    TIMESTAMP_KW   = ["starting around", "starting at", "began", "as of", "pm pt", "am pt",
                      "utc", "pacific", "approximately"]
    NEXT_UPDATE_KW = ["within", "next update", "will provide", "monitoring", "update in",
                      "keep you informed", "will continue"]
    ACTION_KW      = ["no action", "contact support", "please reach out", "if you experience",
                      "continue to experience", "support team", "no action required"]
    # SFI checks
    DETECTION_CONFIRM_KW  = ["detection", "email security", "threat protection",
                              "threat detection", "email scanning", "security scanning"]
    FALSE_REASSURANCE_KW  = [
        "detection remain fully", "detection remains fully",
        "detection continue to", "threat detection remain",
        "email security remain fully", "detection is fully operational",
        # Broader coverage for LLM phrasing variations
        "all security functions", "security systems remain",
        "email detection continues", "email scanning remains",
        "threat protection remains", "detection and remediation remain",
        "detection and remediation continue", "detecting normally",
        "protected against threats", "continuing to protect",
        "email security detection remain", "email security detection continue",
    ]

    # Pull SFI data once (used per-comm below)
    sfi = (extraction or {}).get("security_function_impact", {})
    det_status = sfi.get("detection_status", "unknown")

    warnings = []
    communications_list = comms.get("communications", [])
    logger.info(f"Found {len(communications_list)} communications to validate")

    for i, comm in enumerate(communications_list):
        stage = comm.get("stage", "unknown")
        msg = comm.get("message", "").lower()
        logger.info(f"Validating stage {i+1}: {stage}, message length: {len(msg)}")

        if not any(kw in msg for kw in UNAFFECTED_KW):
            warnings.append({"stage": stage, "field": "What's not affected",
                              "severity": "high",
                              "detail": "Critical for a security vendor — must state what continues to work."})
            logger.warning(f"Missing 'unaffected' field in {stage}")
        if not any(kw in msg for kw in IMPACT_KW):
            warnings.append({"stage": stage, "field": "Customer impact",
                              "severity": "medium",
                              "detail": "Should describe what customers are experiencing."})
            logger.warning(f"Missing 'impact' field in {stage}")
        if not any(kw in msg for kw in TIMESTAMP_KW):
            warnings.append({"stage": stage, "field": "Timestamp",
                              "severity": "medium",
                              "detail": "Should state when the issue started."})
            logger.warning(f"Missing 'timestamp' field in {stage}")
        if stage != "resolved" and not any(kw in msg for kw in NEXT_UPDATE_KW):
            warnings.append({"stage": stage, "field": "Next update commitment",
                              "severity": "medium",
                              "detail": "Should tell customers when to expect the next update."})
            logger.warning(f"Missing 'next update' field in {stage}")
        if not any(kw in msg for kw in ACTION_KW):
            warnings.append({"stage": stage, "field": "Customer action",
                              "severity": "medium",
                              "detail": "Should state what customers should do (usually 'No action required at this time')."})
            logger.warning(f"Missing 'customer action' field in {stage}")

        # Word count check — generation prompt targets under 100 words
        word_count = len(comm.get("message", "").split())
        if word_count > 110:
            warnings.append({"stage": stage, "field": "Message length",
                              "severity": "medium",
                              "detail": f"Message is {word_count} words. Target is under 100. Status page updates should be scannable."})
            logger.warning(f"Message too long in {stage}: {word_count} words")

        # SFI check 1: detection confirmed operational — must say so
        if det_status == "fully_operational" and not any(kw in msg for kw in DETECTION_CONFIRM_KW):
            warnings.append({"stage": stage, "field": "Detection status confirmation",
                              "severity": "high",
                              "detail": "Detection is confirmed operational — must explicitly reassure customers of this for a security product."})
            logger.warning(f"Missing detection confirmation in {stage} (det_status=fully_operational)")

        # SFI check 2: detection degraded/offline — must not falsely reassure
        if det_status in ("degraded", "offline") and any(kw in msg for kw in FALSE_REASSURANCE_KW):
            warnings.append({"stage": stage, "field": "False detection reassurance",
                              "severity": "high",
                              "detail": "CRITICAL ERROR: Communication states detection is operational when it is degraded/offline. Remove false reassurance immediately."})
            logger.warning(f"False detection reassurance detected in {stage} (det_status={det_status})")

    logger.info(f"Validation completed: {len(warnings)} warnings found")
    return warnings


def validate_extraction_consistency(extraction: dict, deployment_flags: list = None) -> list:
    """Cross-check extraction fields for logical contradictions.

    Returns a list of consistency flag dicts with keys: field, detail, severity.
    These are shown as a separate warning block in the results, not mixed with
    communication validation.
    """
    flags = []
    pc  = extraction.get("pattern_classification", {})
    sfi = extraction.get("security_function_impact", {})
    rc  = extraction.get("root_cause", {})
    cs  = extraction.get("confidence_scores", {})

    pattern    = pc.get("primary_pattern", "")
    det_status = sfi.get("detection_status", "")
    rem_status = sfi.get("remediation_status", "")
    rc_status  = rc.get("status", "")
    rc_conf    = cs.get("root_cause", "")

    # Portal auth failures do not impair email detection
    if pattern == "portal_auth_failure" and det_status in ("degraded", "offline"):
        flags.append({
            "field": "Pattern vs. detection status",
            "detail": f"Pattern is '{pattern}' but detection_status='{det_status}'. Portal/UI failures do not affect email detection. Review security function classification.",
            "severity": "high",
        })

    # Confirmed root cause should carry at least medium confidence
    if rc_status == "confirmed" and rc_conf == "low":
        flags.append({
            "field": "Root cause confidence",
            "detail": "root_cause.status='confirmed' but confidence_scores.root_cause='low'. Confirmed causes should have medium or high confidence. Review root cause reasoning.",
            "severity": "medium",
        })

    # Deployment-induced pattern without confirmed or hypothesized root cause is suspicious
    if pattern == "deployment_induced" and rc_status == "unknown":
        flags.append({
            "field": "Pattern vs. root cause status",
            "detail": "Pattern is 'deployment_induced' but root_cause.status='unknown'. A deployment-induced pattern requires at least a hypothesized deployment trigger. Review root cause.",
            "severity": "medium",
        })

    # Third-party dependency pattern should mention an external service in root cause trigger
    if pattern == "third_party_dependency":
        trigger = rc.get("trigger", "") or ""
        external_signals = ["microsoft", "aws", "azure", "google", "external", "upstream", "third-party", "api"]
        if not any(s in trigger.lower() for s in external_signals):
            flags.append({
                "field": "Pattern vs. root cause trigger",
                "detail": "Pattern is 'third_party_dependency' but root_cause.trigger does not mention an external service. Verify the dependency name is documented.",
                "severity": "medium",
            })

    # Deployment correlation vs. LLM classification contradiction
    # deployment_flags=[] means the deterministic check found nothing suspicious
    if deployment_flags is not None and pattern == "deployment_induced" and not deployment_flags:
        flags.append({
            "field": "Deployment correlation vs. AI classification",
            "detail": "AI classified this as 'deployment_induced' but deterministic deployment correlation found no flagged deployments in the pre-onset window. The AI may be pattern-matching on service names rather than timing evidence. Review root cause reasoning carefully.",
            "severity": "medium",
        })

    logger.info(f"Extraction consistency check: {len(flags)} flags")
    return flags


# ── Evidence Trace constants ──────────────────────────────────────────────────
_ET_LABELS = {
    "what_is_broken":     "What's broken?",
    "what_caused_it":     "What caused it?",
    "when_did_it_happen": "When did it happen?",
    "what_is_not_broken": "What's not broken?",
    "how_bad_is_it":      "How bad is it?",
}
# Maps each ET question to the confidence_scores key that best represents it
_ET_CONF_KEY = {
    "what_is_broken":     "customer_impact",
    "what_caused_it":     "root_cause",
    "when_did_it_happen": "timeline",
    "what_is_not_broken": "scope",
    "how_bad_is_it":      "customer_impact",
}
_PUBLISH_CHECKS = [
    "Affected service is correct",
    "Root cause is correct (or confirmed as unconfirmed)",
    "Timeline boundaries are correct",
    "'Unaffected' claims are accurate for this security product",
    "Generated communications reviewed for tone and accuracy",
]
_EXPECTED_FILE_TYPES = {
    "pagerduty_incident": "Alert severity, service name, onset time",
    "cloudwatch_logs":    "Error details, stack traces, service-level failures",
    "prometheus_metrics": "Quantitative onset/recovery times, baseline comparison",
    "github_deployments": "Deployment correlation, causal candidates",
    "incident_context":   "Engineer discussion, root cause confirmation, Slack thread",
}


def _format_comms_for_copy(comms: dict) -> str:
    """Format communications as plain text for clipboard copy."""
    lines = [f"=== {comms.get('title', 'Incident')} ===", ""]
    for c in comms.get("communications", []):
        stage = c.get("stage", "").title()
        posted = c.get("posted_at_pt", "")
        msg = c.get("message", "")
        lines += [f"[{stage}]  {posted}", msg, ""]
    return "\n".join(lines)


def render_evidence_trace(extraction: dict, comms: dict, file_contents: dict) -> None:
    """Show the five verification cards and pre-publish checklist."""
    et = extraction.get("evidence_trace", [])
    if not et:
        return

    # ── Session state init (safe to call on every rerun) ──
    if "verify_status" not in st.session_state or st.session_state.verify_status is None:
        st.session_state.verify_status = {item.get("question", ""): "unverified" for item in et}
    if "verify_notes" not in st.session_state or st.session_state.verify_notes is None:
        st.session_state.verify_notes = {item.get("question", ""): "" for item in et}
    if "publish_checks" not in st.session_state or st.session_state.publish_checks is None:
        st.session_state.publish_checks = {c: False for c in _PUBLISH_CHECKS}

    st.markdown("### 🛡️ Verify Before Publishing")

    # ── Stale data warning ──
    tl = extraction.get("timeline", {})
    ts_str = tl.get("detection_time_utc") or tl.get("onset_time_utc")
    if ts_str:
        try:
            ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - ts_dt).total_seconds() / 3600
            if age_h > 24:
                st.warning(
                    f"⏰ Analysis based on data from **{ts_dt.strftime('%b %d, %Y %H:%M UTC')}** "
                    f"({int(age_h)}h ago). If the incident is still active, re-upload current data."
                )
        except Exception:
            pass

    # ── Summary bar ──
    statuses = [st.session_state.verify_status.get(item.get("question", ""), "unverified") for item in et]
    n_ver = statuses.count("verified")
    n_dis = statuses.count("disputed")
    n_unv = statuses.count("unverified")
    bar_color = "#dc2626" if n_dis else ("#d97706" if n_unv else "#059669")
    st.markdown(
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid {bar_color};'
        f'border-radius:8px;padding:0.7rem 1rem;margin-bottom:1rem;color:#334155;">'
        f'<b>{n_ver}/5</b> verified &nbsp;·&nbsp; '
        f'<b style="color:#dc2626">{n_dis}</b> disputed &nbsp;·&nbsp; '
        f'<b style="color:#94a3b8">{n_unv}</b> unverified'
        f'</div>',
        unsafe_allow_html=True,
    )
    if n_dis:
        st.warning("⚠️ Disputed claims should be resolved before publishing.")

    # ── 5 verification cards ──
    conf_scores = extraction.get("confidence_scores", {})
    for item in et:
        q = item.get("question", "")
        label    = _ET_LABELS.get(q, q.replace("_", " ").title())
        conclusion = item.get("conclusion", "")
        evidence   = item.get("evidence", [])
        counter    = item.get("counter_evidence", [])
        suggestion = item.get("verification_suggestion", "")

        conf_val   = conf_scores.get(_ET_CONF_KEY.get(q, ""), "")
        conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf_val, "⚪")
        v_status   = st.session_state.verify_status.get(q, "unverified")
        s_icon     = {"verified": "✅", "disputed": "❌", "unverified": "⬜"}.get(v_status, "⬜")

        # Show conclusion preview in header so IC can scan without expanding
        conclusion_preview = conclusion[:80] + ("…" if len(conclusion) > 80 else "")
        auto_expand = (v_status == "disputed")

        with st.expander(f"{s_icon} **{label}** {conf_emoji} — _{conclusion_preview}_", expanded=auto_expand):
            st.markdown(f"**Conclusion:** {conclusion}")

            # Toggle buttons
            bc1, bc2, bc3 = st.columns(3)
            if bc1.button("✅ Verified",  key=f"ev_ver_{q}"):
                st.session_state.verify_status[q] = "verified"
                st.rerun()
            if bc2.button("❌ Disputed",  key=f"ev_dis_{q}"):
                st.session_state.verify_status[q] = "disputed"
                st.rerun()
            if bc3.button("⬜ Reset",     key=f"ev_rst_{q}"):
                st.session_state.verify_status[q] = "unverified"
                st.session_state.verify_notes[q]  = ""
                st.rerun()

            if v_status == "disputed":
                note = st.text_input(
                    "What's wrong with this conclusion?",
                    value=st.session_state.verify_notes.get(q, ""),
                    key=f"ev_note_{q}",
                )
                st.session_state.verify_notes[q] = note

            # Supporting evidence
            if evidence:
                st.markdown("**Supporting Evidence**")
                for ev in evidence:
                    st.markdown(f"📄 `{ev.get('source_file', '')}`  ·  {ev.get('relevance', '')}")
                    st.code(ev.get("raw_excerpt", ""), language="text")

            # Counter-evidence (amber tint via minimal inline style)
            if counter:
                st.markdown("**Counter-Evidence** *(weakens or contradicts the conclusion)*")
                for ev in counter:
                    st.markdown(
                        f'<div style="background:#fffbeb;border-left:3px solid #f59e0b;'
                        f'padding:4px 10px;border-radius:4px;margin-bottom:4px;'
                        f'font-size:12px;color:#78350f;">⚠️ {ev.get("source_file","")}'
                        f' — {ev.get("relevance","")}</div>',
                        unsafe_allow_html=True,
                    )
                    st.code(ev.get("raw_excerpt", ""), language="text")

            if suggestion:
                st.markdown(f"_💡 To verify: {suggestion}_")

    # ── Data availability ──
    st.markdown("---")
    st.markdown("**Data available for this analysis**")
    detected_types = {detect_file_type(fn, fc) for fn, fc in (file_contents or {}).items()}
    missing = [(t, d) for t, d in _EXPECTED_FILE_TYPES.items() if t not in detected_types]
    if missing:
        for ftype, desc in missing:
            st.caption(f"⬜ **{ftype}** not uploaded — {desc} unavailable. Related confidence is reduced.")
    else:
        st.caption("✅ All 5 standard data sources were available for this analysis.")

    # ── Internal → customer language mapping ──
    internal_terms = extraction.get("internal_details_to_exclude", [])
    customer_desc  = extraction.get("customer_impact", {}).get("description", "")
    if internal_terms and customer_desc:
        with st.expander("🔤 Internal → Customer Language Mapping", expanded=False):
            st.caption("Internal terms found in source data, mapped to customer-facing language:")
            st.markdown(f"**Internal:** `{'`, `'.join(internal_terms)}`")
            st.markdown(f"**Customer-facing:** _{customer_desc}_")

    # ── Pre-publish checklist ──
    st.markdown("---")
    st.markdown("### ✔️ Ready to Publish?")
    all_checked = True
    for check in _PUBLISH_CHECKS:
        val = st.checkbox(
            check,
            value=st.session_state.publish_checks.get(check, False),
            key=f"pub_{check}",
        )
        st.session_state.publish_checks[check] = val
        if not val:
            all_checked = False

    can_publish = all_checked and n_dis == 0
    st.markdown("")
    if can_publish:
        st.success("✅ All items verified — ready to copy.")
        st.code(_format_comms_for_copy(comms), language="text")
    elif n_dis:
        st.error("❌ Resolve disputed claims before publishing.")
    else:
        remaining = sum(1 for v in st.session_state.publish_checks.values() if not v)
        st.info(f"Complete {remaining} remaining checklist item(s) to enable copy.")


# ── Date helper ───────────────────────────────────────────────────────────────
def _extract_date_label(extraction: dict) -> str:
    tl = extraction.get("timeline", {})
    ts = tl.get("detection_time_utc") or tl.get("onset_time_utc")
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            pt_offset = -7 if 3 <= dt.month <= 10 else -8
            pt = dt.astimezone(timezone(timedelta(hours=pt_offset)))
            return pt.strftime("%B %d, %Y")
        except Exception:
            pass
    return "Today"


# ── Status page renderer ──────────────────────────────────────────────────────
def render_status_page(comms: dict, extraction: dict) -> None:
    try:
        severity = extraction.get("customer_impact", {}).get("severity_assessment", "degraded_performance")
        communications = comms.get("communications", [])
        is_resolved = bool(communications) and communications[-1].get("stage") == "resolved"

        # ── Severity badge ──────────────────────────────────────────────────────
        if is_resolved:
            sev_color, sev_text = "green", "✅ Resolved"
        elif severity == "full_outage":
            sev_color, sev_text = "red", "🔴 Full Outage"
        elif severity == "partial_outage":
            sev_color, sev_text = "orange", "🟠 Partial Outage"
        else:
            sev_color, sev_text = "orange", "🟡 Degraded Performance"

        # ── Security function impact badge ─────────────────────────────────────
        sfi = extraction.get("security_function_impact", {})
        det_status = sfi.get("detection_status", "unknown")
        rem_status = sfi.get("remediation_status", "unknown")
        if det_status in ("degraded", "offline"):
            sfi_color, sfi_text = "red", "⚠️ Detection Impacted"
        elif rem_status in ("degraded", "offline"):
            sfi_color, sfi_text = "orange", "⚠️ Remediation Impacted"
        elif det_status == "fully_operational" and rem_status == "fully_operational":
            sfi_color, sfi_text = "green", "✅ Detection & Remediation Operational"
        else:
            sfi_color, sfi_text = "gray", "❓ Security Status Unconfirmed"

        # ── Duration ───────────────────────────────────────────────────────────
        duration_str = ""
        if is_resolved:
            tl = extraction.get("timeline", {})
            try:
                onset_str    = tl.get("onset_time_utc") or tl.get("cause_time_utc")
                resolved_str = tl.get("resolved_time_utc") or tl.get("mitigation_time_utc")
                if onset_str and resolved_str:
                    onset_dt   = datetime.fromisoformat(onset_str.replace("Z", "+00:00"))
                    res_dt     = datetime.fromisoformat(resolved_str.replace("Z", "+00:00"))
                    delta_mins = int((res_dt - onset_dt).total_seconds() / 60)
                    if delta_mins > 0:
                        h, m = divmod(delta_mins, 60)
                        duration_str = f"Resolved after {h}h {m}m" if h else f"Resolved after {m}m"
            except Exception:
                pass

        incident_date = _extract_date_label(extraction)

        # ── Header ─────────────────────────────────────────────────────────────
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f":{sev_color}[**{sev_text}**]" + (f"  ·  *{duration_str}*" if duration_str else ""))
        with c2:
            st.markdown(f":{sfi_color}[{sfi_text}]")

        st.markdown(
            f'<p style="font-size:13px;color:#64748b;margin:0.25rem 0 0.75rem 0;">'
            f'📅 {incident_date} &nbsp;·&nbsp; Right badge: security function impact (red = detection may be down)</p>',
            unsafe_allow_html=True,
        )

        st.markdown(f"**{comms.get('title', 'Incident')}**")
        st.markdown(
            '<p style="font-size:13px;color:#64748b;margin:0 0 0.5rem 0;">'
            '<span style="color:#16a34a;">■</span> ≤100w &nbsp;'
            '<span style="color:#d97706;">■</span> ≤110w &nbsp;'
            '<span style="color:#dc2626;">■</span> >110w — word count per message</p>',
            unsafe_allow_html=True,
        )

        # ── Stage messages ─────────────────────────────────────────────────────
        stage_colors = {
            "resolved":     "green",
            "monitoring":   "blue",
            "identified":   "orange",
            "investigating":"red",
        }

        def _wc_label(text: str) -> str:
            wc = len(text.split())
            if wc <= 100:   return f":green[{wc}w]"
            elif wc <= 110: return f":orange[{wc}w]"
            else:           return f":red[{wc}w ⚠]"

        for comm in reversed(communications):
            stage   = comm.get("stage", "unknown")
            posted  = comm.get("posted_at_pt", "")
            message = comm.get("message", "")
            color   = stage_colors.get(stage, "gray")
            with st.container(border=True):
                st.markdown(
                    f":{color}[**{stage.title()}**]  ·  "
                    f"*{posted}*  ·  {_wc_label(message)}"
                )
                st.markdown(message)

    except Exception as e:
        logger.error(f"Error in render_status_page: {e}")
        st.error(f"Error rendering status page: {e}")


def render_structured_analysis(extraction: dict) -> None:
    logger.info(f"=== render_structured_analysis STARTED ===")
    logger.info(f"Extraction keys: {list(extraction.keys()) if isinstance(extraction, dict) else 'Not a dict'}")
    
    try:
        with st.expander("📋 Structured Incident Analysis", expanded=False):
            # ── Security Function Status (top of expander) ──
            sfi = extraction.get("security_function_impact", {})
            if sfi:
                st.markdown("**Security Function Status**")
                STATUS_CLS  = {"fully_operational": "sfi-operational", "degraded": "sfi-degraded",
                               "offline": "sfi-offline", "unknown": "sfi-unknown"}
                STATUS_ICON = {"fully_operational": "🟢", "degraded": "🟡",
                               "offline": "🔴", "unknown": "⚪"}
                STATUS_LBL  = {"fully_operational": "Fully Operational", "degraded": "Degraded",
                               "offline": "Offline", "unknown": "Unknown"}
                det_s = sfi.get("detection_status", "unknown")
                rem_s = sfi.get("remediation_status", "unknown")
                c1, c2 = st.columns(2)
                with c1:
                    dcls = STATUS_CLS.get(det_s, "sfi-unknown")
                    st.markdown(
                        f'<div class="sfi-status {dcls}">{STATUS_ICON.get(det_s,"⚪")} '
                        f'Detection: {STATUS_LBL.get(det_s,"Unknown")}</div>',
                        unsafe_allow_html=True)
                with c2:
                    rcls = STATUS_CLS.get(rem_s, "sfi-unknown")
                    st.markdown(
                        f'<div class="sfi-status {rcls}">{STATUS_ICON.get(rem_s,"⚪")} '
                        f'Remediation: {STATUS_LBL.get(rem_s,"Unknown")}</div>',
                        unsafe_allow_html=True)
                pc = sfi.get("primary_category", "")
                conf = sfi.get("confidence", "")
                if pc:
                    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
                    st.markdown(f"**Category:** {pc.title()}"
                                + (f" &nbsp; {conf_emoji} {conf} confidence" if conf else ""))
                if sfi.get("reasoning"):
                    st.caption(sfi["reasoning"])
                st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Timeline**")
                timeline = extraction.get("timeline", {})
                logger.info(f"Timeline entries: {len(timeline)}")
                for key, val in timeline.items():
                    if val:
                        label = key.replace("_utc", "").replace("_", " ").title()
                        st.markdown(f"- **{label}:** {val}")
                st.markdown("**Root Cause**")
                rc = extraction.get("root_cause", {})
                logger.info(f"Root cause keys: {list(rc.keys())}")
                st.markdown(f"- **Status:** {rc.get('status', 'unknown')}")
                st.markdown(f"- **Summary:** {rc.get('summary', 'N/A')}")
            with col2:
                st.markdown("**Confidence Scores**")
                scores = extraction.get("confidence_scores", {})
                logger.info(f"Confidence scores: {list(scores.keys())}")
                for key, val in scores.items():
                    emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(val, "⚪")
                    st.markdown(f"- **{key.title()}:** {emoji} {val}")
                st.markdown("**Data Gaps**")
                gaps = extraction.get("data_gaps", [])
                logger.info(f"Data gaps: {len(gaps)}")
                for gap in gaps:
                    st.markdown(f"- ⚠️ {gap}")
            st.markdown("**Internal Details Excluded**")
            excluded = extraction.get("internal_details_to_exclude", [])
            logger.info(f"Internal details excluded: {len(excluded)}")
            st.code(", ".join(excluded) if excluded else "None identified")
        
        logger.info("=== render_structured_analysis COMPLETED ===")
        
    except Exception as e:
        logger.error(f"Error in render_structured_analysis: {e}")
        logger.info("=== render_structured_analysis FAILED ===")
        st.error(f"Error rendering structured analysis: {e}")


def render_pattern_analysis(extraction: dict) -> None:
    logger.info(f"=== render_pattern_analysis STARTED ===")
    
    try:
        pc = extraction.get("pattern_classification", {})
        il = extraction.get("inference_log", [])
        logger.info(f"Pattern classification: {bool(pc)}, Inference log entries: {len(il)}")
        
        if not pc and not il:
            logger.info("No pattern data to display")
            return

        with st.expander("🔬 Pattern Analysis & Inference Log", expanded=False):
            if pc:
                pattern = pc.get("primary_pattern", "unknown").replace("_", " ").title()
                conf = pc.get("confidence", "unknown")
                conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
                st.markdown(f"**Detected Pattern:** {pattern} &nbsp; {conf_emoji} {conf} confidence")
                st.markdown(f"_{pc.get('reasoning', '')}_")
                logger.info(f"Pattern: {pattern}, confidence: {conf}")

            if il:
                st.markdown("---")
                # Confidence summary line
                conf_counts = {"high": 0, "medium": 0, "low": 0}
                for entry in il:
                    c = entry.get("confidence", "")
                    if c in conf_counts:
                        conf_counts[c] += 1
                st.markdown(
                    f"**Inference Chain** &nbsp; "
                    f"🟢 {conf_counts['high']} high &nbsp; "
                    f"🟡 {conf_counts['medium']} medium &nbsp; "
                    f"🔴 {conf_counts['low']} low"
                )
                type_icon  = {
                    "direct_observation":   "📌",
                    "cross_reference":      "🔗",
                    "absence_of_evidence":  "❓",
                    "engineer_confirmation": "✅",
                }
                type_label = {
                    "direct_observation":   "Direct Observations",
                    "cross_reference":      "Cross-References",
                    "absence_of_evidence":  "Absence of Evidence",
                    "engineer_confirmation": "Engineer Confirmations",
                }
                # Group by inference_type
                from collections import defaultdict
                grouped: dict = defaultdict(list)
                for entry in il:
                    grouped[entry.get("inference_type", "other")].append(entry)

                type_order = ["engineer_confirmation", "direct_observation", "cross_reference", "absence_of_evidence", "other"]
                for itype in type_order:
                    entries = grouped.get(itype, [])
                    if not entries:
                        continue
                    icon  = type_icon.get(itype, "•")
                    label_text = type_label.get(itype, itype.replace("_", " ").title())
                    with st.expander(f"{icon} {label_text} ({len(entries)})", expanded=(itype == "engineer_confirmation")):
                        for i, entry in enumerate(entries):
                            conf  = entry.get("confidence", "")
                            conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
                            sources = ", ".join(entry.get("sources", []))
                            st.markdown(f"{conf_emoji} **{entry.get('claim', '')}**")
                            if sources:
                                st.caption(f"Sources: {sources}")
                            logger.info(f"Inference: {itype} - {entry.get('claim', '')[:50]}...")

            # Recent incident history
            past_logs = load_inference_logs(limit=6)
            logger.info(f"Loaded {len(past_logs)} past logs")
            # Filter out the current one (same summary)
            current_summary = extraction.get("incident_summary", "")
            past_logs = [l for l in past_logs if l.get("incident_summary") != current_summary]
            logger.info(f"After filtering current incident: {len(past_logs)} past logs")
            
            if past_logs:
                st.markdown("---")
                st.markdown("**Recent Incident Patterns**")
                for log in past_logs[:5]:
                    p = log.get("pattern_classification", {}).get("primary_pattern", "unknown")
                    summary = log.get("incident_summary", "")[:80] + ("…" if len(log.get("incident_summary", "")) > 80 else "")
                    st.markdown(f"- **{p.replace('_', ' ').title()}** — {summary}")
        
        logger.info("=== render_pattern_analysis COMPLETED ===")
        
    except Exception as e:
        logger.error(f"Error in render_pattern_analysis: {e}")
        logger.info("=== render_pattern_analysis FAILED ===")
        st.error(f"Error rendering pattern analysis: {e}")


def render_validation(warnings: list) -> None:
    logger.info(f"=== render_validation STARTED ===")
    logger.info(f"Warnings to render: {len(warnings)}")
    
    try:
        high = [w for w in warnings if w["severity"] == "high"]
        medium = [w for w in warnings if w["severity"] == "medium"]
        logger.info(f"High severity warnings: {len(high)}, Medium severity warnings: {len(medium)}")

        if not warnings:
            st.success("✅ All communications pass required field validation.")
            return

        for w in high:
            logger.warning(f"High severity warning: {w['stage']} - {w['field']}")
            st.error(f"**[{w['stage'].title()}] Missing: {w['field']}** — {w['detail']} *(Critical for security vendor)*")

        if medium:
            logger.info(f"Showing {len(medium)} medium warnings in expander")
            with st.expander(f"⚠️ {len(medium)} medium-severity field warning(s)", expanded=False):
                for w in medium:
                    logger.info(f"Medium warning: {w['stage']} - {w['field']}")
                    st.warning(f"**[{w['stage'].title()}] Missing: {w['field']}** — {w['detail']}")
        
        logger.info("=== render_validation COMPLETED ===")
        
    except Exception as e:
        logger.error(f"Error in render_validation: {e}")
        logger.info("=== render_validation FAILED ===")
        st.error(f"Error rendering validation: {e}")


def render_deployment_alerts(flags: list) -> None:
    logger.info(f"=== render_deployment_alerts STARTED ===")
    logger.info(f"Deployment flags to render: {len(flags)}")
    
    try:
        if not flags:
            logger.info("No deployment flags to display")
            return
            
        high_flags = [f for f in flags if f["relevance"] == "HIGH"]
        low_flags  = [f for f in flags if f["relevance"] == "LOW"]
        logger.info(f"High relevance flags: {len(high_flags)}, Low relevance flags: {len(low_flags)}")

        post_flags = [f for f in flags if f["relevance"] == "POST-ONSET"]

        for f in high_flags:
            logger.info(f"Rendering HIGH alert: {f['service']} - {f['title']}")
            timing = f.get("timing_label", f"{f['minutes_before_onset']}min before onset")
            st.markdown(f"""
<div class="deploy-high">
  <strong>Deployment {timing} — same service as alert</strong><br>
  <code>{f['service']}</code> &nbsp;·&nbsp; {f['title']} &nbsp;·&nbsp;
  by {f['author']} &nbsp;·&nbsp; {f['timestamp']}
</div>""", unsafe_allow_html=True)

        if low_flags:
            logger.info(f"Showing {len(low_flags)} low relevance flags in expander")
            with st.expander(f"{len(low_flags)} deployment(s) in 60-min pre-onset window (different service)", expanded=False):
                for f in low_flags:
                    timing = f.get("timing_label", f"{f['minutes_before_onset']}min before onset")
                    logger.info(f"Low flag: {f['service']} - {f['title']}")
                    st.markdown(f"- **{f['service']}** — {f['title']} ({timing})")

        if post_flags:
            logger.info(f"Showing {len(post_flags)} post-onset deployment flags")
            with st.expander(f"{len(post_flags)} deployment(s) after incident onset (potential worsening factors)", expanded=False):
                for f in post_flags:
                    timing = f.get("timing_label", "after onset")
                    svc_note = " — same service" if f.get("same_service_as_alert") else ""
                    st.markdown(f"- **{f['service']}** — {f['title']} ({timing}{svc_note})")
        
        logger.info("=== render_deployment_alerts COMPLETED ===")
        
    except Exception as e:
        logger.error(f"Error in render_deployment_alerts: {e}")
        logger.info("=== render_deployment_alerts FAILED ===")
        st.error(f"Error rendering deployment alerts: {e}")


# ── Sample data loader ────────────────────────────────────────────────────────
def load_sample_data():
    logger.info("=== Loading Sample Data ===")
    data_dir = Path("data")
    if not data_dir.exists():
        logger.warning(f"Data directory {data_dir} does not exist")
        return {}
    
    files = {
        fp.name: fp.read_text(encoding="utf-8")
        for fp in data_dir.glob("*")
        if fp.is_file() and fp.suffix in (".json", ".txt")
        and fp.name != ".DS_Store"
    }
    logger.info(f"Loaded {len(files)} sample files: {list(files.keys())}")
    return files

# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    logger.info("=== MAIN FUNCTION STARTED ===")
    
    st.markdown("""
    <div class="main-header">
        <h1>🚨 Incident Communications Generator</h1>
        <p>Transform raw incident data into professional status page communications</p>
    </div>""", unsafe_allow_html=True)

    # Session state init
    for key, default in [
        ("step", "upload"), ("extraction", None), ("comms", None),
        ("error", None), ("uploaded_files", None), ("sample_data", None),
        ("deployment_flags", None), ("validation_warnings", None),
        ("consistency_flags", None),
        ("verify_status", None), ("verify_notes", None), ("publish_checks", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default
    logger.info(f"RERUN step={st.session_state.step} "
                f"uploaded={'yes('+str(len(st.session_state.uploaded_files))+')' if st.session_state.uploaded_files else 'no'} "
                f"sample={'yes' if st.session_state.sample_data else 'no'} "
                f"extraction={'yes' if st.session_state.extraction else 'no'} "
                f"comms={'yes' if st.session_state.comms else 'no'} "
                f"error={repr(st.session_state.error)}")

    if st.session_state.error:
        logger.error(f"PIPELINE ERROR (shown on upload page): {st.session_state.error}")

    # Progress indicator
    steps = [
        ("upload",     "📤 Upload Files",  "Upload incident data files"),
        ("processing", "⚡ Processing",    "AI analysis and generation"),
        ("results",    "✨ Results",       "View generated communications"),
    ]
    current_idx = next(i for i, (s, _, _) in enumerate(steps) if s == st.session_state.step)
    logger.info(f"Current step: {st.session_state.step} (index {current_idx})")
    
    st.markdown("### Progress")
    for i, (step, icon, desc) in enumerate(steps):
        cls = "completed" if i < current_idx else ("active" if i == current_idx else "")
        suffix = " ✓" if i < current_idx else (" →" if i == current_idx else "")
        st.markdown(f'<div class="progress-step {cls}">{icon} {desc}{suffix}</div>',
                    unsafe_allow_html=True)

    # ── Step 1: Upload ──────────────────────────────────────────────────────
    if st.session_state.step == "upload":
        logger.info("=== STEP 1: UPLOAD ===")
        st.markdown("### 📤 Upload Incident Data")
        
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("""
            <div class="info-card">
                <h3>📋 Supported Files</h3>
                <ul>
                    <li><strong>incident_context.txt</strong> — Slack threads / engineer notes</li>
                    <li><strong>cloudwatch_logs.json</strong> — Application logs</li>
                    <li><strong>prometheus_metrics.json</strong> — System metrics</li>
                    <li><strong>pagerduty_incident.json</strong> — Alert data</li>
                    <li><strong>github_deployments.json</strong> — Deployment history</li>
                </ul>
                <p><em>Not all files required — pipeline works with any subset.</em></p>
            </div>""", unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="info-card"><h3>🎯 Quick Start</h3><p>Try with sample data instantly.</p></div>',
                        unsafe_allow_html=True)
            if st.button("🚀 Load Sample Data", type="secondary", use_container_width=True):
                logger.info("User clicked 'Load Sample Data'")
                sample = load_sample_data()
                if sample:
                    st.session_state.sample_data = sample
                    logger.info(f"Loaded {len(sample)} sample files: {list(sample.keys())}")
                    st.success(f"✅ Loaded {len(sample)} sample files")
                else:
                    logger.warning("No sample data found")
                    st.error("❌ No sample data found in 'data/' directory")

        uploaded = st.file_uploader(
            "Upload incident data files (JSON / TXT)",
            type=["json", "txt"],
            accept_multiple_files=True,
        )
        # Read content immediately — file objects become unreadable after rerun
        if uploaded:
            logger.info(f"User uploaded {len(uploaded)} files")
            st.session_state.uploaded_files = {f.name: f.read().decode("utf-8") for f in uploaded}
            logger.info(f"Stored uploaded files: {list(st.session_state.uploaded_files.keys())}")

        if st.session_state.uploaded_files or st.session_state.sample_data:
            st.markdown("---")
            _, col, _ = st.columns([1, 2, 1])
            with col:
                if st.button("🚀 Analyze Incident", type="primary", use_container_width=True):
                    logger.info("BUTTON CLICKED: Analyze Incident — setting step=processing")
                    st.session_state.step = "processing"
                    st.rerun()

    # ── Step 2: Processing ──────────────────────────────────────────────────
    elif st.session_state.step == "processing":
        logger.info("=== PROCESSING STEP ENTERED ===")

        # Guard: already finished (double-rerun edge case)
        if st.session_state.extraction is not None and st.session_state.comms is not None:
            logger.info("processing: guard — already done, advancing to results")
            st.session_state.step = "results"
            st.rerun()
            return

        file_contents = st.session_state.sample_data or st.session_state.uploaded_files
        if not file_contents:
            logger.error("processing: ABORT — no file_contents in session state (sample_data=None, uploaded_files=None)")
            st.session_state.step = "upload"
            st.rerun()
            return

        logger.info(f"processing: files={list(file_contents.keys())}")
        st.markdown("### ⚡ Processing Incident Data")
        bar = st.progress(0)
        status = st.empty()

        import traceback as _tb
        try:
            status.text("🔎 Running deployment correlation...")
            bar.progress(10)
            deployment_flags = correlate_deployments(file_contents)
            st.session_state.deployment_flags = deployment_flags
            logger.info(f"processing: correlation done — {len(deployment_flags)} flags")

            status.text("🧠 Extracting incident facts (Claude)...")
            bar.progress(20)
            extraction = run_extraction(file_contents, deployment_flags)
            st.session_state.extraction = extraction
            logger.info(f"processing: extraction done — keys={list(extraction.keys()) if isinstance(extraction, dict) else type(extraction).__name__}")
            bar.progress(60)

            save_inference_log(extraction)
            bar.progress(65)

            status.text("✍️ Generating communications (Claude)...")
            comms = run_generation(extraction)
            st.session_state.comms = comms
            logger.info(f"processing: generation done — keys={list(comms.keys()) if isinstance(comms, dict) else type(comms).__name__}")
            bar.progress(95)

            status.text("✔ Validating...")
            st.session_state.validation_warnings = validate_communications(comms, extraction)
            st.session_state.consistency_flags   = validate_extraction_consistency(extraction, deployment_flags)
            bar.progress(100)
            logger.info(f"processing: validation done — {len(st.session_state.validation_warnings)} warnings, "
                        f"{len(st.session_state.consistency_flags)} consistency flags")

            status.text("✅ Complete!")
            st.session_state.step = "results"
            logger.info("processing: SUCCESS — step set to results")

        except Exception as e:
            logger.error(f"processing: EXCEPTION {type(e).__name__}: {e}")
            logger.error("processing: FULL TRACEBACK\n" + _tb.format_exc())
            st.session_state.error = f"{type(e).__name__}: {e}"
            st.session_state.step = "upload"

        # st.rerun() MUST be outside the try block — it raises RerunException internally
        # which except Exception would catch, silently resetting state to upload.
        st.rerun()

    # ── Step 3: Results ─────────────────────────────────────────────────────
    elif st.session_state.step == "results":
        logger.info("=== RESULTS STEP ===")
        if not (st.session_state.comms and st.session_state.extraction):
            logger.error(f"results: missing state — comms={st.session_state.comms is not None} "
                         f"extraction={st.session_state.extraction is not None} — resetting to upload")
            st.session_state.step = "upload"
            st.rerun()
            return

        def _zone(label: str, sublabel: str = "") -> None:
            sub_html = f'<span style="font-size:12px;font-weight:400;color:#94a3b8;margin-left:10px;">{sublabel}</span>' if sublabel else ""
            st.markdown(
                f'<div style="font-size:13px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;'
                f'color:#475569;padding:0.6rem 0 0.3rem 0;border-bottom:2px solid #cbd5e1;'
                f'margin:2rem 0 0.75rem 0;">{label}{sub_html}</div>',
                unsafe_allow_html=True,
            )

        def _note(text: str) -> None:
            """Inline hint — larger than st.caption, smaller than body."""
            st.markdown(
                f'<p style="font-size:13px;color:#64748b;margin:0 0 0.75rem 0;">{text}</p>',
                unsafe_allow_html=True,
            )

        _note("① Review the draft → ② Check quality flags → ③ Verify evidence → ④ Complete checklist → Copy.")

        # ── Zone 1: Context ─────────────────────────────────────────────────
        # Only show if there are deployment flags to display
        _deployment_flags = st.session_state.get("deployment_flags") or []
        if _deployment_flags:
            _zone("① Pre-Flight Context", "deployments near onset")
            _note("HIGH = same service as alert, pre-onset. LOW = different service. POST-ONSET = possible worsening factor.")
            render_deployment_alerts(_deployment_flags)

        # ── Zone 2: Status Page Draft ─────────────────────────────────────────
        _zone("② Status Page Draft", "newest stage first")
        render_status_page(st.session_state.comms, st.session_state.extraction)

        # ── Zone 3: Quality Checks ───────────────────────────────────────────
        _consistency_flags = st.session_state.get("consistency_flags") or []
        _validation_warnings = st.session_state.get("validation_warnings") or []
        _has_quality_issues = bool(_consistency_flags) or bool(_validation_warnings)

        if _has_quality_issues:
            _zone("③ Quality Checks", "required fields validation")
            _note("Red = must fix before publishing. Yellow = recommended.")
            for cf in _consistency_flags:
                sev = cf.get("severity", "medium")
                detail = cf.get("detail", "")
                field  = cf.get("field", "")
                if sev == "high":
                    st.error(f"**Logic conflict — {field}:** {detail}")
                else:
                    st.warning(f"**Logic conflict — {field}:** {detail}")
            render_validation(_validation_warnings)
        else:
            _zone("③ Quality Checks", "all clear")
            st.success("✅ All communications pass required field and consistency validation.")

        # ── Zone 4: IC Verification ──────────────────────────────────────────
        _zone("④ IC Verification", "verify before publishing")
        _note("5 questions the AI answered from raw evidence. Mark Verified ✅ or Disputed ❌. All 5 must be verified to unlock copy.")
        _et_files = st.session_state.sample_data or st.session_state.uploaded_files or {}
        render_evidence_trace(st.session_state.extraction, st.session_state.comms, _et_files)

        # ── Zone 5: Analyst View (collapsed by default) ──────────────────────
        _zone("Analyst View", "optional")
        render_pattern_analysis(st.session_state.extraction)

        # ── Zone 6: Raw Extraction (collapsed by default) ────────────────────
        _zone("Raw Extraction Data", "optional")
        render_structured_analysis(st.session_state.extraction)

        st.markdown("---")
        _, col, _ = st.columns([1, 2, 1])
        with col:
            if st.button("🔄 Start Over", use_container_width=True):
                logger.info("User clicked 'Start Over' - resetting session state")
                for key in ("step", "extraction", "comms", "error",
                            "uploaded_files", "sample_data",
                            "deployment_flags", "validation_warnings",
                            "consistency_flags",
                            "verify_status", "verify_notes", "publish_checks"):
                    st.session_state[key] = None if key != "step" else "upload"
                st.rerun()

    logger.info(f"=== RERUN COMPLETE step={st.session_state.step} ===")


if __name__ == "__main__":
    logger.info("=== APP ENTRY POINT ===")
    main()
