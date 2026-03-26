# Codebase Walkthrough: Incident Communications Generator

## Overview

A single-file Streamlit application (`app.py`) that takes raw incident data from multiple technical sources and produces professional, customer-facing status page communications — the kind Abnormal Security actually publishes at status.abnormalsecurity.com.

The core value: an on-call engineer can drop in 2-5 raw files from an active incident and within ~30 seconds get structured facts, security function impact classification, evidence-backed reasoning, quality-checked communications, and an IC verification workflow before anything is published.

---

## Who Uses This

On-call incident commanders (ICs) and comms teams at Abnormal Security responding to production incidents. The tool is not meant to auto-publish — it generates a draft and supports human verification before anything goes out. The audience for the output is paying enterprise security customers who need to know whether their email threat detection is still protecting them.

---

## Application Architecture

### Single-File Structure

The entire app lives in `app.py` with clear functional sections:

```
Lines 1–277      Imports, configuration, logging setup, CSS
Lines 279–450    Two embedded system prompts (extraction + generation)
Lines 450–1200   Core logic: LLM helpers, data processing, pipeline functions,
                 validation, consistency checking
Lines 1200–1700  UI rendering functions
Lines 1700–1760  Session state initialization, sample data loading
Lines 1760–end   Main application flow (step routing: upload / processing / results)
```

Two additional legacy files exist (`pipeline_v1.py`, `pipeline_v2.py`) but are not used by the running app.

### Data Flow

```
User uploads files
       ↓
detect_file_type()              Content-based routing into 5 categories
       ↓
correlate_deployments()         Pre-LLM: flag suspicious GitHub deployments
                                (multi-metric Prometheus onset + pre/post windows)
       ↓
build_user_message()            Assembles prompt input; annotates filenames
                                for source citation accuracy
       ↓
run_extraction()  [Claude #1]   Structured incident analysis (24k tokens)
       ↓
save_inference_log()            Persist analysis (incl. evidence_trace) to disk
       ↓
run_generation()  [Claude #2]   Draft status page communications (16k tokens)
                                Stage order enforced in Python after LLM returns
       ↓
validate_communications()       Keyword checks + SFI checks + word count
validate_extraction_consistency() Cross-checks pattern vs. security function impact
       ↓
Results rendered across 6 named zones
```

---

## User Experience

### Step 1: Upload

Users see a file uploader that accepts drag-and-drop. A "Load Sample Data" button pulls the five pre-built incident files from `data/` for instant demos. The "Analyze Incident" button stays disabled until at least one file is loaded.

Supported file types (detected by content, not filename):
- `pagerduty_incident.json` — alert metadata, severity, service, lifecycle timestamps
- `cloudwatch_logs.json` — application logs, errors, stack traces
- `prometheus_metrics.json` — time-series metrics for baseline/anomaly/recovery detection
- `github_deployments.json` — deployment history, PRs, commit SHAs
- `incident_context.txt` — Slack thread excerpts, engineer notes, root cause discussions

### Step 2: Processing

A progress bar advances through weighted checkpoints reflecting actual time distribution: 0% → 10% (deployment correlation) → 20% (extraction starts) → 60% (extraction completes — this is the slow LLM call) → 65% (inference log saved) → 95% (generation completes — second slow LLM call) → 100% (validation done).

The pipeline runs sequentially — the generation call depends on the extraction output.

### Step 3: Results — Six Named Zones

The page is divided into six visually-labeled zones, each with a subtitle communicating its purpose to a non-technical user:

1. **Pre-Flight Context** — suspicious deployments flagged before any LLM reasoning
2. **Status Page Preview** — what will be published
3. **Quality Checks** — before you publish (consistency flags + communication field validation)
4. **Incident Commander Verification** — review evidence before publishing
5. **Analyst View** — optional (pattern classification and inference log)
6. **Raw Extraction Data** — optional (full structured LLM output)

This ordering means a comms person can make a publish decision top-to-bottom without scrolling through technical analysis. The analyst and developer sections follow, collapsed by default.

---

## AI Pipeline

### Claude Call #1: Extraction (`EXTRACTION_SYSTEM_PROMPT`)

**Role:** Incident analysis engine — extracts structured facts from raw multi-source data.

**Token budget:** 24,000 max tokens. All calls use `stream=True`.

**15 critical rules (Rule 0 through Rule 14):**
- **Rule 0** (overrides all): Null over hallucination — unknown fields must be null/[], never invented
- **Rule 2**: Rollback = confirmation — a successful rollback sets `root_cause.status="confirmed"` even without explicit engineer statement
- **Rule 11**: Pattern classification (8 defined types). `portal_auth_failure` explicitly incompatible with `detection_status=degraded/offline`
- **Rule 12**: Inference logging — every factual claim logged with inference_type + confidence
- **Rule 13**: Security function classification — full detection/remediation/other taxonomy with explicit false-assurance safeguards
- **Rule 14**: Evidence trace — verbatim excerpts only; `what_is_not_broken` must cite specific absence, not service names; verification suggestions must be actionable in under 2 minutes

**Output schema (top-level keys):**
```
incident_summary, affected_service, affected_products, severity,
timeline (7 timestamps), root_cause (summary/status/trigger/mechanism),
customer_impact (description/severity_assessment/affected/unaffected),
resolution (action_taken/confirmed_by),
confidence_scores (root_cause/scope/timeline/customer_impact),
pattern_classification (primary_pattern/confidence/reasoning),
security_function_impact (primary_category/secondary_category/confidence/
  reasoning/detection_status/remediation_status),
inference_log (array), evidence_trace (array of 5),
data_gaps (array), internal_details_to_exclude (array)
```

### Claude Call #2: Generation (`GENERATION_SYSTEM_PROMPT`)

**Role:** Status page communications writer. First-person plural ("We are investigating...").

**Token budget:** 16,000 max tokens.

**Six required elements per stage, in specified order:**
1. Affected service (customer terms)
2. What's NOT affected — **must be the second sentence** in every update; never cut to meet word count
3. Customer impact description
4. Timestamp in PT (DST handled: March–October = PDT = UTC-7)
5. Next update commitment (omitted for Resolved)
6. Customer action — **required in ALL stages including Investigating** ("No action is required at this time")

**Key generation constraints:**
- Word count target: under 100 words. Trim order: (1) next-update timing, (2) extra impact detail. Never trim field 2.
- Identified stage language tied to `root_cause.status`: "confirmed" → "we have identified..."; "hypothesized" → "we believe we have identified..."; "unknown" → skip Identified stage entirely
- Urgency calibration from `security_function_impact`: detection degraded = highest urgency; detection unknown = hedge, do not claim operational; both operational = second sentence is standard security reassurance
- Concrete example message embedded in prompt as few-shot template (79-word investigating update)

**Stage order enforcement:** Python sorts communications by `STAGE_ORDER = {"investigating": 0, "identified": 1, "monitoring": 2, "resolved": 3}` after the LLM call, so out-of-order LLM responses don't produce a broken status page.

---

## Key Technical Functions

### Data Ingestion

**`detect_file_type(filename, content)`** — Routes files by content structure, not filename.

**`correlate_deployments(file_contents)`** — Runs before any LLM call. Two improvements over simple timestamp comparison:
- Prometheus onset uses **multi-metric consensus**: collects first-anomaly timestamps across all metric series, then finds the earliest 5-minute window where ≥2 metrics are simultaneously anomalous. Prevents a single transient spike from setting a false early onset.
- **Post-onset window** (30 minutes after onset) is scanned separately for `POST-ONSET` labeled deployments — potential worsening factors, not causes.
- PR numbers are intentionally excluded from returned flags (internal details).

**`summarize_metrics(content)`** — Returns two-part output for the LLM:
- `METRIC SUMMARY`: per-series anomaly summary with baseline/first-anomaly/peak values
- `RAW ANOMALOUS VALUES`: verbatim timestamp-value pairs for anomalous series — what the LLM cites in `evidence_trace` evidence items

**`build_user_message(file_contents, deployment_flags)`** — Detects file types internally. Annotates each section header with the original filename (`=== CLOUDWATCH LOGS (filename: cloudwatch_logs.json) ===`) so the LLM can produce accurate `source_file` citations in evidence items.

### LLM Infrastructure

**`call_claude(user_message, system_prompt, max_tokens, temperature)`** — Single function for all Claude calls. Uses `claude-sonnet-4-5` with `stream=True`. Two-attempt retry on JSON parse failure: second attempt appends a correction instruction. Verbose logging throughout.

**`parse_llm_json(text)`** — Strips markdown fencing, tracks brace/bracket depth to find the JSON boundary (handles Claude adding explanatory text after the JSON), raises detailed errors on failure.

### Validation

**`validate_communications(comms, extraction)`** — Keyword-based checks per stage message:
1. What's not affected (high severity if missing)
2. Customer impact (medium)
3. Timestamp (medium)
4. Next update commitment (medium, skipped for Resolved)
5. Customer action (medium, **no exemptions** — all stages including Investigating)
6. Word count >110 (medium)
7. SFI check: `detection_status=fully_operational` → must mention detection (high severity if not)
8. SFI check: `detection_status=degraded/offline` → must NOT falsely claim detection operational (critical)

**`validate_extraction_consistency(extraction)`** — Cross-checks extraction fields for semantic contradictions:
- `portal_auth_failure` + detection degraded/offline → high severity (portal issues don't impair detection)
- `root_cause.status=confirmed` + `confidence_scores.root_cause=low` → medium (inconsistent)
- `deployment_induced` + `root_cause.status=unknown` → medium (deployment pattern needs at least a hypothesis)
- `third_party_dependency` + no external service in trigger → medium (dependency name should be documented)

### Persistence

**`save_inference_log(extraction)`** — Writes timestamped JSON to `inference_logs/`. Includes `evidence_trace` (added to enable future incident replay without re-running the LLM).

**`load_inference_logs(limit=5)`** — Reads the last N inference logs newest-first for pattern trend display.

---

## What Makes the Analysis Useful

### For Security Vendors Specifically

A portal outage is inconvenient. A detection failure means threats are getting through. The pipeline handles this distinction through:
- `security_function_impact` extraction with explicit `detection_status` and `remediation_status` fields
- Generation prompt rules that place security function status as the second sentence in every update
- Validation that catches false reassurance (stating detection is operational when it's degraded)
- `validate_extraction_consistency()` that flags patterns incompatible with detection impact claims

### Evidence Trace for Human-in-the-Loop

The five verification questions are answered with verbatim excerpts from source files. The metrics pre-processing now passes raw timestamp-value pairs to the LLM specifically so evidence items can cite `"http_request_duration_seconds: 2.5 at 2025-01-15T14:20Z"` rather than "latency was elevated." Counter-evidence is always populated when contradictions exist.

Card headers show the conclusion preview (80 chars) without expanding — the IC can scan all 5 questions at a glance. Disputed cards auto-expand. The copy output gate (all 5 checklist items + no disputed cards) means publishing fast is structurally harder than publishing carefully.

### Inference Logging for Auditability

Every factual claim carries an `inference_type` tag. Claims are grouped by type in the UI (engineer confirmations first, absence-of-evidence last), so the IC can check "what did engineers actually confirm?" by opening just the first sub-group.

---

## Potential Problems and Limitations

### Validation is Heuristic

`validate_communications` checks keyword presence, not semantic correctness. A message containing "remain" passes the "what's not affected" check regardless of whether the sentence actually reassures customers. False negatives and positives both occur.

### Voice Divergence from Style Guide

`CLAUDE.md` specifies third-person "Abnormal" voice. The generation prompt uses first-person "We." This was an intentional design choice but diverges from the style guide.

### Retry Logic is Minimal

On JSON parse failure, one retry with a correction instruction. If the second attempt fails, a `ValueError` surfaces as an error banner — user must start over.

### No Sidebar

Current UI uses the main column for file upload rather than `st.sidebar` as originally specified.

---

## File Structure

```
app.py                      Main application
data/                       Sample incident data (5 files)
  pagerduty_incident.json
  cloudwatch_logs.json
  prometheus_metrics.json
  github_deployments.json
  incident_context.txt
inference_logs/             Auto-created; timestamped analysis JSON files
test_data_portal/           Alternative test dataset (portal incident scenario)
test_data_thirdparty/       Alternative test dataset (third-party dep scenario)
iterative_prompts/          Development iteration notes (not used at runtime)
requirements.txt            anthropic>=0.40.0, streamlit>=1.40.0, python-dotenv>=1.0.0
.python-version             3.12.2
.streamlit/config.toml      Forces light theme
app_debug.log               Runtime debug log (auto-generated)
```

---

## Running the App

```bash
# Set API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
# → http://localhost:8501
```

For Railway deployment, set `ANTHROPIC_API_KEY` as an environment variable — the app reads it via `python-dotenv` with `load_dotenv()` at startup.

---

## Deep Dive: The Six Results Sections

After clicking "Analyze Incident," the results page renders six named zones in sequence. The ordering is intentional: the most important output appears first, with quality checks immediately below, so a comms person can make a publish decision without scrolling through technical analysis. The analyst and developer sections follow, collapsed by default.

---

### Zone 1 — Pre-Flight Context (Deployment Alerts)

**Where it comes from**

`correlate_deployments()` runs before any LLM call on the raw uploaded files. It derives incident onset time from two sources: PagerDuty's `created_at` field, and Prometheus metrics. When checking Prometheus, it uses multi-metric consensus — it collects the first-anomaly timestamp for each metric series and finds the earliest 5-minute window where at least two metrics are simultaneously anomalous. This prevents a single transient spike from setting a false early onset time.

The function scans GitHub deployments across two windows: 60 minutes before onset (looking for causes) and 30 minutes after onset (looking for worsening factors). Pre-onset deployments are scored HIGH (same service as alert, substring match) or LOW (different service). Post-onset deployments get a separate POST-ONSET label.

**How it's displayed**

HIGH-relevance deployments render as custom `.deploy-high` HTML cards — orange left-bordered, not `st.warning()`. The CSS class is defined in the codebase precisely for this purpose and produces a visually distinct alert rather than a generic amber box. Each card shows service, title, author, timestamp, and a timing label ("15min before onset"). LOW deployments go in a collapsed expander. POST-ONSET deployments go in their own collapsed expander titled "potential worsening factors" — a distinct label that correctly frames their relationship to the incident. PR numbers are intentionally excluded (internal identifiers).

**What makes it accurate today**

This section is fully deterministic — no LLM involved. The multi-metric consensus requirement for Prometheus onset detection is the key accuracy mechanism: a single anomalous metric could be noise; two metrics simultaneously anomalous is a meaningful signal. The pre/post-onset distinction surfaces information about incident evolution, not just cause. Because this runs before extraction, it also acts as an independent check: if the LLM calls an incident `deployment_induced` but no HIGH-relevance deployment appears here, that contradiction is visible.

---

### Zone 2 — Status Page Preview (Generated Communications)

**Where it comes from**

`run_generation()` makes the second Claude call, feeding it the full extraction JSON. The generation prompt requires six elements in every stage message, in specific order — most importantly, "what's not affected" must always be the second sentence, never buried or cut. Stage ordering is enforced in Python after the LLM call (`STAGE_ORDER` dict), so out-of-order LLM responses don't produce a broken status page.

**How it's displayed**

`render_status_page()` builds the layout in pure HTML via `st.markdown()`. Communications display newest-first. Two badges sit above the title: a severity badge from `severity_assessment`, and a security function badge from `detection_status` and `remediation_status`. For resolved incidents, severity badge overrides to green regardless of `severity_assessment`.

Each stage carries a word count badge (green ≤100w / amber ≤110w / red >110w) next to the stage label — an at-a-glance indicator without opening validation details. For resolved incidents, a duration label ("Resolved after 2h 15m") is computed from `onset_time_utc` and `resolved_time_utc` and shown inline with the incident title.

**What makes it accurate today**

The generation prompt's structural constraints are the main accuracy mechanism. "What's not affected" is the second sentence by rule, not by LLM judgment. The word-count trim priority (cut next-update timing first, never cut what's-not-affected) means when Claude needs to shorten a message, it removes lower-priority content. The prompt reads `detection_status` and `remediation_status` to determine exactly what the "what's not affected" sentence should say, rather than leaving it to LLM inference.

---

### Zone 3 — Quality Checks (Validation)

**Where it comes from**

Two independent validators run after generation:

`validate_extraction_consistency(extraction)` cross-checks logical relationships between extraction fields: `portal_auth_failure` + detection degraded/offline is a contradiction (portal issues don't impair detection); `deployment_induced` pattern + unknown root cause is suspicious; confirmed root cause + low confidence is inconsistent; `third_party_dependency` without an external service named in the trigger is a gap.

`validate_communications(comms, extraction)` runs five keyword-presence checks per stage plus word count and two security-function checks. Customer action is required in ALL stages — including Investigating.

**How it's displayed**

Consistency flags appear first (high as `st.error()`, medium as `st.warning()`), followed by communication field warnings. Green success message appears if everything passes. The Quality Checks zone is immediately below the status page so the IC sees pass/fail before doing detailed verification.

**What makes it accurate today**

Two layers catch different problem types. Consistency validation catches semantic contradictions in the extraction that propagate into misleading communications. Communication validation catches structural omissions that make communications incomplete regardless of whether the underlying analysis is correct. The false-reassurance check — `detection degraded + communication says "detection remains fully operational"` — is the most critical single check. It prevents the highest-stakes publication error: telling customers their security is intact when it isn't.

---

### Zone 4 — IC Verification (Evidence Trace)

**Where it comes from**

`evidence_trace` is populated as part of the extraction JSON — same Claude call, not a separate step. Rule 14 requires Claude to answer five fixed verification questions with verbatim evidence. The section header for each source file in the extraction user message is annotated with the original filename, which enables Claude to produce accurate `source_file` citations in evidence items.

Verbatim quality is enforced by rule: `raw_excerpt` must copy exact log lines, exact Slack messages with author and timestamp, and exact metric values as "metric_name: value at timestamp." For `what_is_not_broken` specifically, Claude must cite a specific absence rather than listing service names — if no confirmatory data exists, it must use `raw_excerpt: "No error data found for this service in any provided source"` labeled "Absence of evidence — weaker than positive confirmation."

For metrics, `summarize_metrics()` outputs a RAW ANOMALOUS VALUES section with verbatim timestamp-value pairs. This enables Claude to cite `"http_request_duration_seconds: 2.5 at 2025-01-15T14:20Z"` rather than "latency was elevated."

**How it's displayed**

Five expandable cards. The conclusion preview is visible in each card header (80 chars, italic) — no expanding required to scan all five. Disputed cards auto-expand. Supporting evidence displays in `st.code()` blocks (monospace, visually distinct). Counter-evidence renders in amber-tinted blocks. Three-state verification buttons (✅/❌/⬜) with note input for disputed claims. Summary bar shows N/5 verified at a glance.

Copy output unlocks only when all 5 checklist items are checked AND no cards are disputed. Stale-data warning fires if the incident timestamp is more than 24 hours old.

**What makes it accurate today**

The verbatim-excerpt requirement makes evidence checkable against the original source rather than taking the LLM's summary on faith. `st.code()` rendering makes excerpts visually distinct. Counter-evidence is required to be populated whenever contradictions exist — no one-sided evidence presentation. The confidence scores shown per card (from `confidence_scores` in the extraction) tell the IC how much to trust each conclusion.

The five questions are fixed and non-negotiable. The IC cannot engage with only the questions they care about. This structure produces a minimum baseline of verification regardless of how confident the IC feels.

---

### Zone 5 — Analyst View (Pattern Analysis and Inference Log)

**Where it comes from**

Both come from the extraction JSON. `pattern_classification` classifies the incident into one of 8 defined patterns. `inference_log` logs every factual claim with claim text, source data points, inference type, and confidence. Rule 11 defines patterns with explicit mutual-exclusivity constraints. Rule 12 requires comprehensive inference logging.

Prior incident patterns are loaded from disk: `load_inference_logs(limit=6)` reads `inference_logs/`, filters the current incident, and shows up to 5 prior entries. `evidence_trace` is now persisted alongside the inference log, so the full verification context is available for historical analysis.

**How it's displayed**

Collapsed expander in the "Analyst View" zone (labeled "optional"). Inference entries are grouped into four collapsible sub-groups by type: Engineer Confirmations (auto-expanded — most reliable), Direct Observations, Cross-References, Absence of Evidence. A confidence summary line ("4 high · 2 medium · 1 low") gives at-a-glance reliability without opening sub-groups.

**What makes it accurate today**

The inference type taxonomy lets the IC weight claims by reliability. Grouping by type means "what did engineers actually confirm?" is answerable by opening one sub-group. The `portal_auth_failure` / detection incompatibility in Rule 11 is also enforced by `validate_extraction_consistency()` — most common semantic classification error is caught at two levels.

---

### Zone 6 — Raw Extraction Data (Structured Analysis)

**Where it comes from**

Surfaces extraction fields that feed into communications and verification but aren't directly displayed elsewhere: `security_function_impact` (full object), `timeline` (all seven timestamps), `root_cause` (status + summary), `confidence_scores`, `data_gaps`, and `internal_details_to_exclude`.

**How it's displayed**

Collapsed expander in the "Raw Extraction Data" zone (labeled "optional"). Detection and remediation status shown as colored pills side by side. Timeline as bullet list, nulls skipped. Confidence scores with emoji. Data gaps and excluded internal terms at the bottom.

**What makes it accurate today**

The section renders extraction fields verbatim — no transformation. The `internal_details_to_exclude` list is the most directly verifiable field: the IC can scan it, then check whether those terms appear in the generated communications. If they do, the generation step failed its exclusion rule. The confidence scores shown here are the same ones used to compute evidence trace card confidence levels — an advanced user can verify the confidence mapping is being applied consistently across sections.
