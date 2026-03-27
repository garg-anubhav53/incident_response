# Results Page Walkthrough: Incident Analysis Output

This document explains what the incident analysis system exposes to users and why each component matters for incident response.

## Context: Sample Incident Analysis

The system analyzed an incident involving **API latency degradation** in the `api-gateway` service. The root cause was a deployment that changed HTTP client timeout from 10s to 30s, causing database connection pool exhaustion.

## What the System Extracts

### 1. Incident Timeline & Impact
- **What**: Precise timestamps for incident onset, detection, acknowledgment, mitigation, and resolution
- **Why**: Critical for understanding incident duration and response time metrics
- **Example**: Onset at 14:20 UTC (metrics show latency spike), detection at 14:23 UTC (PagerDuty alert), resolution at 16:45 UTC

### 2. Root Cause Analysis
- **What**: Specific deployment changes that triggered the incident, with causal mechanism
- **Why**: Enables targeted fixes and prevents recurrence
- **Example**: Deployment at 14:15 UTC changed HTTP timeout from 10s to 30s, causing connections to be held 3× longer and exhausting the database connection pool

### 3. Customer Impact Classification
- **What**: Severity assessment (degraded_performance / partial_outage / full_outage) and affected functionality
- **Why**: Communicates actual customer experience rather than internal metrics
- **Example**: "degraded_performance" — API worked but with high latency; most requests succeeded

### 4. Security Function Impact
- **What**: Whether email threat detection or automated remediation were impaired, classified as fully_operational / degraded / offline / unknown
- **Why**: For a security product, customers need to know whether their protection was compromised — this is the single highest-priority classification in the system
- **How it drives communications**: The detection_status and remediation_status values determine the exact language of the second sentence in every generated status update (see Zone 2 below)

### 5. Evidence Trail
- **What**: Verbatim raw data excerpts supporting each conclusion — exact log lines, metric values with timestamps, Slack messages with author and timestamp
- **Why**: Enables IC verification before publishing; provides audit trail for post-incident review

## How Results Are Organized

The results page renders six zones in decision order. An IC can make a publish/no-publish decision from Zones 1–3 without reading Zones 4–6.

### Zone 1: Pre-Flight Context *(only shown when deployment data exists)*
**Deployments Near Incident Onset**
- Only rendered if the deterministic deployment correlation found flagged deployments; hidden entirely when there are none
- Flags deployments as HIGH (same service as alert, pre-onset), LOW (different service, pre-onset), or POST-ONSET (possible worsening factor)
- Uses multi-metric consensus detection: requires ≥2 metrics anomalous in the same 5-minute window before trusting a Prometheus-derived onset time
- Example: HIGH relevance deployment to api-gateway at 14:15 UTC (5 minutes before onset)

### Zone 2: Status Page Draft
**AI-Generated Customer Communications**
- Generates 2–4 stages depending on what is applicable. Always generates Investigating and Resolved. Skips Identified if root cause is unknown or low-confidence. Skips Monitoring if the incident resolved within 30 minutes of mitigation or if timeline data is insufficient.
- Each stage follows a fixed sentence order: (1) What happened + timestamp. (2) What is NOT affected — mandatory second sentence, never repositioned or trimmed. (3) Customer impact. (4) Engineering team action. (5) Customer action. (6) Next update timing.
- Sentence 2 content is driven by `detection_status` and `remediation_status`:
  - **Both fully_operational**: "Email security detection and automated remediation remain fully operational and continue to protect against threats."
  - **detection degraded**: "Email security detection is currently degraded, and some threats may not be detected or acted upon automatically."
  - **detection offline**: "Email security detection is currently offline, and threats may not be detected or remediated automatically."
  - **detection unknown**: "We are confirming the status of email security detection services and will provide an update shortly."
- Word count badge per message: green ≤100w, orange ≤110w, red >110w

### Zone 3: Quality Checks
**Automated Validation**
- Shows a green "All communications pass" confirmation when no issues are found — no noisy empty zone
- When issues exist, splits into high-severity (red, shown inline) and medium-severity (collapsed expander)
- High-severity checks include:
  - Missing "what's not affected" field (critical for a security vendor)
  - False reassurance: communication says detection is operational when `detection_status` is degraded/offline
  - Missing detection status confirmation when `detection_status` is fully_operational
- Consistency checks between extraction fields include:
  - portal_auth_failure pattern + detection degraded/offline (logical contradiction)
  - deployment_induced pattern + no deployment flags from deterministic correlation (AI may be guessing)
  - Confirmed root cause with low confidence score

### Zone 4: IC Verification *(collapsed cards)*
**Evidence-Based Claims Verification with Copy-Lock**
- Five fixed verification questions: What's broken? What caused it? When did it happen? What's not broken? How bad is it?
- Each card shows verbatim evidence (exact log lines, exact metric values as "metric_name: value at timestamp", exact Slack messages with author + timestamp) — never paraphrased summaries
- Each card has a three-state toggle: Verified ✅ / Disputed ❌ / Reset ⬜
- Disputed cards auto-expand and accept a free-text note explaining the problem
- Summary bar shows N/5 verified · N disputed · N unverified
- Copy output is gated: unlocks only when all 5 checklist items are checked AND zero cards are disputed. Disputed state blocks copy even if all checklist items are checked.
- Stale data warning if incident timestamps are more than 24 hours old

### Zone 5: Analyst View *(collapsed by default)*
**Pattern Classification & Inference Log**
- Incident pattern (deployment_induced, infrastructure_cascade, portal_auth_failure, etc.) with confidence and reasoning
- Inference chain grouped by type: engineer confirmations, cross-references, direct observations, absence-of-evidence
- Capped at 10 entries; includes only meaningful inferences — engineer confirmations, cross-source correlations, and key direct observations. Trivial observations (e.g., "no resolved timestamp found") are omitted.
- Recent incident patterns from persisted inference logs (cross-incident history)

### Zone 6: Raw Extraction Data *(collapsed by default)*
**Complete Structured Analysis**
- Full AI output: timeline, root cause, confidence scores, data gaps, internal terms excluded
- Security function status (detection/remediation) with reasoning
- Source attribution for root cause, timeline, and customer impact claims

## Why Each Zone Matters

### For Incident Commanders (Zones 1–3)
- **Zone 1** surfaces the most likely causal deployment candidate without requiring log searches
- **Zone 2** produces publish-ready text — the IC reviews rather than drafts
- **Zone 3** catches the highest-risk error (false security reassurance) before it reaches customers

### For Verification (Zone 4)
- Verbatim evidence lets the IC validate AI reasoning against raw source data in under 60 seconds
- The copy-lock enforces engagement with each claim before publishing — deliberate friction

### For Security Operations (Zones 5–6)
- Pattern classification identifies incident type for post-incident review and trend tracking
- Inference log provides auditability: every claim traceable to a source type and confidence level
- Persisted inference logs enable cross-incident pattern analysis over time

## Consistency Checks the System Runs

| Check | Severity | Description |
|---|---|---|
| Missing "what's not affected" | High | Every status update must state what continues working |
| False detection reassurance | High | Catches communications that say detection is operational when it is degraded/offline |
| Missing detection confirmation | High | When detection is confirmed operational, every update must say so explicitly |
| portal_auth_failure + detection degraded | High | Logical contradiction — portal failures do not impair email detection |
| deployment_induced + no deployment flags | Medium | AI pattern claim not supported by deterministic correlation |
| Confirmed root cause + low confidence | Medium | Inconsistent confidence signals |
| deployment_induced + unknown root cause | Medium | Pattern requires at least a hypothesized trigger |
| third_party_dependency + no external trigger | Medium | Pattern requires an identifiable external dependency |
