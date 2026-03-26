# Enhancements Summary & Equivalent Structured Prompt

---

## Part 1: Enhancements Made

### 1. Extraction Prompt — Accuracy and Honesty Rules

**Rule 0 (Null over hallucination):** Added an explicit override rule that forces unknown fields to `null` or `[]` rather than allowing the model to invent plausible-sounding values. This addresses the most common failure mode in structured extraction: confident-sounding wrong answers.

**Rollback = Confirmation (Rule 2):** Formalized the inference that a successful rollback of a specific deployment constitutes a confirmed root cause even without an explicit engineer statement. Without this, the model would leave `root_cause.status` as `hypothesized` for the most common incident type in the dataset.

**Portal/Detection Incompatibility (Rule 11):** Added an explicit constraint that `portal_auth_failure` is logically incompatible with `detection_status=degraded/offline`. Portal UI failures do not impair email scanning. This prevents a category error that would cause the generation prompt to apply the wrong urgency calibration.

**What-Is-Not-Broken Guidance (Rule 14):** The previous rule allowed the model to list service names that "seemed fine." Changed to require either a specific logged absence or an explicit engineer statement. If neither exists, the model must use a template phrase ("No error data found...") rather than assert operational status with no evidence. This is the highest-stakes false-positive for a security product.

**Confidence Structure Clarification:** Added a note distinguishing the three confidence structures (`confidence_scores`, `inference_log`, `evidence_trace`) — what each is for and who consumes it. Without this, models conflate them or populate one while leaving others empty.

---

### 2. Generation Prompt — Communication Structure Rules

**What's Not Affected Placement:** Made explicit that the "what's not affected" sentence must be the second sentence in every update — not buried at the end. Abnormal's real status page always leads with scope containment early in the message. This is the single most important reassurance for a security product customer.

**Customer Action in All Stages:** Removed an implicit exemption that allowed the Investigating stage to omit a customer action line. Added explicit rule that all stages including Investigating require "No action is required at this time."

**Word Count Trim Priority:** Added a ranked trim order — if a message exceeds 100 words, cut (1) next-update timing, (2) extra impact detail, (3) timestamp precision. Never cut the "what's not affected" sentence. Without this, models optimizing for brevity cut the wrong fields.

**Identified Stage Guidance:** Tied the Identified stage to `root_cause.status` values — `confirmed` uses direct language, `hypothesized` uses hedged language, `unknown` skips the stage entirely. Previously the model would generate an Identified update even when no cause was known.

**Concrete Example Message:** Added a few-shot example of a correctly structured Investigating update (79 words) to anchor the model's output format.

**DST Handling:** Specified PDT (UTC-7, March–October) vs. PST (UTC-8, November–February) and instructed the model to always label as "PT" rather than UTC or a bare time.

---

### 3. Metrics Preprocessing — Verbatim Evidence Support

`summarize_metrics()` now returns a two-part output: a human-readable anomaly summary (for context) and a separate `RAW ANOMALOUS VALUES` section with verbatim timestamp-value pairs for every anomalous series. The LLM is instructed to cite values from the raw section in `evidence_trace`, enabling specific citations like `"http_request_duration_seconds: 2.5 at 2025-01-15T14:20Z"` instead of `"latency was elevated"`.

---

### 4. User Message Construction — Filename Annotation

`build_user_message()` was updated to detect file types internally (removing a fragile pre-computed type map dependency) and to annotate each section header with the original filename: `=== CloudWatch Logs (filename: cloudwatch_logs.json) ===`. This gives the LLM the information it needs to populate `source_file` accurately in `evidence_trace` citations.

---

### 5. Deployment Correlation — Multi-Metric Consensus and Post-Onset Window

**False onset prevention:** Replaced single-metric onset detection with multi-metric consensus — onset is only recognized when ≥2 independent metrics are simultaneously anomalous within the same 5-minute window. A single transient spike no longer sets the correlation anchor.

**Post-onset window:** Added a 30-minute post-onset window (separate from the 60-minute pre-onset window) that surfaces deployments that may have worsened an ongoing incident rather than caused it. These appear in a separate collapsed expander labeled "potential worsening factors."

**Internal detail exclusion:** `pr_number` is now intentionally excluded from returned deployment flags. PR numbers are internal identifiers that should not surface in the IC's view per Rule 7 of the extraction prompt.

---

### 6. Validation — New Checks and Consistency Cross-Validation

**`validate_extraction_consistency()` (new function):** Catches logical contradictions between `pattern_classification` and `security_function_impact` before the IC reads anything:
- `portal_auth_failure` + detection degraded/offline → high flag
- `root_cause.status=confirmed` + overall confidence low → medium flag
- `deployment_induced` + `root_cause.status=unknown` → medium flag
- `third_party_dependency` + no external service in trigger → medium flag

**Word count check:** Added a medium warning when any stage message exceeds 110 words.

**Investigating exemption removed:** Customer action validation now applies to all stages. The previous code skipped the Investigating stage for this check.

---

### 7. UI — Scannability and Information Hierarchy

**6 named result zones** with visual separators in deliberate order: Pre-Flight Context → Status Page Preview → Quality Checks → IC Verification → Analyst View → Raw Extraction Data. This mirrors the IC's decision flow: see context first, see output second, verify third, drill down if needed.

**Deployment alerts:** `render_deployment_alerts()` now actually uses the `.deploy-high` CSS class (orange-bordered HTML card) for HIGH-relevance deployments. The previous code rendered `st.warning()` boxes despite the CSS class being defined and unused.

**Status page word count badges:** Each stage message in the status page preview now shows a word count badge — green (≤100), amber (≤110), red (>110) — so the IC can see at a glance whether any message is over-length before reading it.

**Duration display:** If both onset and resolution timestamps parse, shows "Resolved after Xh Ym" in the status page header. Visible without expanding anything.

**Evidence card headers:** Each verification card header now shows the conclusion preview (80 chars) so the IC can scan all 5 conclusions without expanding any cards. Cards with `verify_status=disputed` auto-expand.

**Inference log grouping:** Inference entries are grouped into 4 collapsible sub-groups by type (`engineer_confirmation`, `direct_observation`, `cross_reference`, `absence_of_evidence`). Engineer confirmations auto-expand; others are collapsed. A confidence summary line shows the high/medium/low distribution.

---

## Part 2: The Equivalent Structured Prompt

This is the prompt that would be needed to produce the same changes using a model that requires explicit, one-to-one instruction rather than high-level intent.

---

```
You are modifying app.py in a Streamlit incident communications tool.
Make the following specific changes in order. Do not make changes beyond what
is listed. After all changes, verify app.py parses with `python -c "import ast;
ast.parse(open('app.py').read())"`.

---

CHANGE 1 — EXTRACTION_SYSTEM_PROMPT: Add Rule 0

At the start of the rules section (before Rule 1), add:

  "0. NULL OVER HALLUCINATION (OVERRIDES ALL RULES): If a required field
  cannot be determined from the data provided, set scalar fields to null and
  arrays to []. Never invent plausible-sounding values to fill gaps."

---

CHANGE 2 — EXTRACTION_SYSTEM_PROMPT: Update Rule 2

Find the text describing root cause confirmation. Add after the existing rule:

  "ROLLBACK = CONFIRMATION: if a rollback of a specific deployment resolves
  the incident, set root_cause.status='confirmed' even without an explicit
  engineer statement."

---

CHANGE 3 — EXTRACTION_SYSTEM_PROMPT: Update Rule 11

Find Rule 11 (PATTERN CLASSIFICATION). At the end of the rule, add:

  "NOTE: portal_auth_failure is INCOMPATIBLE with
  detection_status=degraded/offline. Portal/UI failures do not impair email
  detection. If this combination appears in your analysis, add it to
  data_gaps."

---

CHANGE 4 — EXTRACTION_SYSTEM_PROMPT: Update Rule 14

Find the guidance for what_is_not_broken inside Rule 14. Replace whatever is
there with:

  "For what_is_not_broken: do NOT list service names that appear fine.
  Cite either (a) a specific logged absence: 'No errors appear for [service]
  in [filename] during the incident window', or (b) an explicit engineer
  statement. If you cannot find either, use exactly one evidence item:
  raw_excerpt='No error data found for this service in any provided source',
  relevance='Absence of evidence — weaker than positive confirmation'."

---

CHANGE 5 — EXTRACTION_SYSTEM_PROMPT: Add confidence structure clarification

After the JSON schema, add a note:

  "NOTE ON THE THREE CONFIDENCE STRUCTURES:
  - confidence_scores: aggregate confidence per top-level field
  - inference_log: per-claim attribution with inference_type and confidence
  - evidence_trace: per-verification-question evidence with raw excerpts
  All three must be fully populated. They serve different consumers."

---

CHANGE 6 — GENERATION_SYSTEM_PROMPT: What's not affected placement

Find the required fields list. Change field #2 to read:

  "2. WHAT'S NOT AFFECTED — place this as the SECOND SENTENCE in every update.
  Never move it lower to meet word count."

---

CHANGE 7 — GENERATION_SYSTEM_PROMPT: Customer action all stages

Find field #6 (Customer Action). Change it to read:

  "6. CUSTOMER ACTION: Required in ALL stages including Investigating.
  Use 'No action is required at this time.' for Investigating/Identified/
  Monitoring. Use support contact language for Resolved."

---

CHANGE 8 — GENERATION_SYSTEM_PROMPT: Add word count trim priority rule

After the word count target, add:

  "If you must trim to hit the word count target, cut in this order:
  (1) next-update timing detail, (2) extra impact description,
  (3) timestamp precision. NEVER cut field #2 (what's not affected)."

---

CHANGE 9 — GENERATION_SYSTEM_PROMPT: Identified stage guidance

Add a rule:

  "IDENTIFIED STAGE: If root_cause.status='confirmed', say 'we have identified
  [abstract cause].' If 'hypothesized', say 'we believe we have identified
  what appears to be [abstract cause].' If 'unknown', omit the Identified
  stage entirely — do not generate a message for it."

---

CHANGE 10 — GENERATION_SYSTEM_PROMPT: Add DST handling

Add:

  "TIMEZONE: Convert all UTC times to PT before writing. March–October = PDT
  = UTC-7. November–February = PST = UTC-8. Always label as 'PT', not PDT/PST
  or UTC."

---

CHANGE 11 — GENERATION_SYSTEM_PROMPT: Add example message

Add a section with a concrete example:

  "EXAMPLE (correctly structured Investigating update, 79 words):
  'We are investigating an issue affecting [Service Name] that began around
  2:20 PM PT on [Date]. Email detection and automated remediation remain fully
  operational and are not impacted. [Scope] customers may experience [impact
  description]. No action is required at this time. Abnormal's engineering
  team is actively investigating and working to resolve the issue. The next
  update will be provided within 1 hour or when further information is
  obtained.'"

---

CHANGE 12 — summarize_metrics(): Add raw anomalous values section

Find the summarize_metrics() function. After the existing summary output,
append a second section:

  raw_anomalous = {metric_name: [{"timestamp": ts, "value": val}, ...]}
  # Populated only for series where at least one value is anomalous

  Return value should be:
  "METRIC SUMMARY:\n" + existing_summary +
  "\n\nRAW ANOMALOUS VALUES (cite these verbatim in evidence_trace):\n" +
  json.dumps(raw_anomalous, indent=2)

---

CHANGE 13 — build_user_message(): Internal type detection + filename annotation

In build_user_message(file_contents, deployment_flags=None):

  1. Call detect_file_type(filename, content) internally for each file rather
     than accepting a pre-computed type map.
  2. When writing each section header, use the format:
     f"=== {label} (filename: {filename}) ==="
     so the LLM can produce accurate source_file citations.

---

CHANGE 14 — correlate_deployments(): Multi-metric consensus

Find the code that determines onset_dt from Prometheus data.
Replace the single-metric approach with:

  1. Collect first_anomaly_timestamp per metric series into a list.
  2. For each timestamp t in the list, count how many other timestamps fall
     within [t, t+5min].
  3. onset_dt = the earliest t where count >= 2.
  4. Fall back to PagerDuty created_at if no consensus window found.

---

CHANGE 15 — correlate_deployments(): Post-onset window

After the 60-minute pre-onset scan, add a second scan:
  post_window_end = onset_dt + timedelta(minutes=30)

Deployments in this window get relevance="POST-ONSET".
Sort order: HIGH → LOW → POST-ONSET; by proximity within each group.
Do NOT include pr_number in the returned dict for any deployment.

---

CHANGE 16 — validate_communications(): Remove Investigating exemption

Find the check for customer action keywords. The current code has a condition
like `if stage not in ("investigating",)`. Remove the exemption so the check
applies to all stages without exception.

---

CHANGE 17 — validate_communications(): Add word count check

After the existing checks, add:
  word_count = len(comm.get("message", "").split())
  if word_count > 110:
      warnings.append({
          "stage": stage, "field": "Message length",
          "severity": "medium",
          "detail": f"{word_count} words — target is under 100"
      })

---

CHANGE 18 — Add validate_extraction_consistency() function

Add a new function with this signature:
  def validate_extraction_consistency(extraction: dict) -> list[dict]:

It should return a list of {field, detail, severity} dicts for these checks:
  1. pattern=portal_auth_failure AND detection_status in (degraded, offline)
     → severity=high, detail="Portal failures do not affect email detection."
  2. root_cause.status=confirmed AND overall confidence=low
     → severity=medium
  3. pattern=deployment_induced AND root_cause.status=unknown
     → severity=medium
  4. pattern=third_party_dependency AND no external service in trigger
     → severity=medium

---

CHANGE 19 — render_deployment_alerts(): Use .deploy-high CSS class

Find where HIGH-relevance deployments are rendered. Replace any st.warning()
or st.info() call with:
  st.markdown(f"""
  <div class="deploy-high">
    <strong>{timing_label} — same service as alert</strong><br>
    <code>{service}</code> · {title} · {author}<br>
    <small>{timestamp}</small>
  </div>""", unsafe_allow_html=True)

Add a separate collapsed expander for POST-ONSET deployments titled:
  "N deployment(s) after incident onset (potential worsening factors)"

---

CHANGE 20 — render_status_page(): Add duration display

After parsing onset and resolution timestamps, compute:
  delta_mins = int((res_dt - onset_dt).total_seconds() / 60)
  h, m = divmod(delta_mins, 60)

Display as a badge in the status page header: "Resolved after Xh Ym"

---

CHANGE 21 — render_status_page(): Add word count badges per stage

For each stage message rendered, compute word count and show a colored badge:
  ≤100 words → green
  101–110 words → amber
  >110 words → red

---

CHANGE 22 — render_evidence_trace(): Conclusion preview in headers

For each evidence card header, truncate the conclusion to 80 characters:
  conclusion_preview = conclusion[:80] + ("…" if len(conclusion) > 80 else "")

Use it in the expander label:
  f"{status_icon} **{label}** {conf_emoji} — _{conclusion_preview}_"

Auto-expand cards where verify_status == "disputed".
Keep all other cards collapsed by default.

---

CHANGE 23 — render_pattern_analysis(): Group inference entries by type

Group inference_log entries by inference_type into these 4 groups:
  - engineer_confirmation (auto-expanded)
  - direct_observation (collapsed)
  - cross_reference (collapsed)
  - absence_of_evidence (collapsed)

Above the groups, show a confidence summary line:
  "Inference Chain 🟢 N high 🟡 N medium 🔴 N low"

---

CHANGE 24 — Results rendering: 6 named zones in correct order

Render results in exactly this order, with a visual zone separator between each:
  1. PRE-FLIGHT CONTEXT
  2. STATUS PAGE PREVIEW — what will be published
  3. QUALITY CHECKS — before you publish
  4. INCIDENT COMMANDER VERIFICATION
  5. ANALYST VIEW — optional
  6. RAW EXTRACTION DATA — optional

In QUALITY CHECKS, show validate_extraction_consistency() results first
(high → st.error, medium → st.warning), then validate_communications() results.

Store consistency_flags in st.session_state. Initialize it as [] on startup
and reset it to [] in the Start Over handler.

---

CHANGE 25 — Documentation updates

After all code changes, update these files to be consistent with the
implementation:
  - CODEBASE_WALKTHROUGH.md: update all function descriptions, layout
    diagrams, and accuracy mechanisms to reflect the changes above
  - iterative_prompts/4.streamlit_ui.md
  - iterative_prompts/5.pattern_matching_deployment_correlation_required_fields.md
  - iterative_prompts/6.security_function_classification.md
  - iterative_prompts/7.evidence_trace.md
```
