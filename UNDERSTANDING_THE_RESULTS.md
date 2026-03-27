# Understanding the Results Page

This document explains every section of the results page produced by the Incident Communications Generator. For each section, it covers what you see, how the system derived it, why it matters, and who it serves. Each section is written to be self-contained — you should be able to read any one section with no prior knowledge and walk away able to explain it to a cybersecurity practitioner.

---

## What happened before the results page

The user uploaded some combination of raw incident data files — PagerDuty alerts, CloudWatch application logs, Prometheus time-series metrics, GitHub deployment records, and Slack thread conversations. Not all five are required; the system works with any subset. The system then ran a pipeline with four steps:

1. **Deployment correlation** (no AI). Pure timestamp math. Checks whether any code deployments happened near the incident start time.
2. **Extraction** (Claude Sonnet). The AI reads all the raw data and produces a single structured JSON object: what happened, when, to what, how bad, what caused it, what's still working, and how confident it is about each claim.
3. **Generation** (Claude Sonnet). The AI reads the extraction and writes customer-facing status page communications.
4. **Validation** (no AI). Keyword-based rules check whether each generated message contains required fields, and whether the extraction contradicts itself internally.

Everything on the results page is a rendering of these four outputs. The extraction is the single source of truth — every other section either displays it directly or displays something derived from it.

---

## Page structure at a glance

The results page flows top to bottom in decision order. The top shows what the IC (Incident Commander — the person responsible for publishing the communication) needs to act on immediately. The bottom shows optional deep-dive sections for analysts.

A small instruction line at the top of the results reads:

> ① Review the draft → ② Check quality flags → ③ Verify evidence → ④ Complete checklist → Copy.

This is the intended workflow. Each numbered zone on the page corresponds to one of these steps. The zone numbers are dynamic — if a section has nothing to show (e.g., no deployments were flagged), it is hidden entirely and the remaining zones renumber so there is no confusing gap.

---

## Pre-Flight Context — deployments near onset

### What you see

Orange alert banners, one per flagged deployment. Each banner states: which service was deployed, the PR title or description, who deployed it, the exact timestamp, and how many minutes before the incident it happened. Banners are labeled HIGH, LOW, or POST-ONSET.

If no deployments were flagged, this entire zone is hidden. You will not see a gap or an empty section — the next zone simply takes the first position.

Below the HIGH banners, a collapsed expander holds LOW-relevance deployments (different service from the alert, within 60 minutes before onset) and another holds POST-ONSET deployments (happened after the incident started, potential worsening factors).

### How it is derived

This is the only section on the page with zero AI involvement. The system:

1. Parses the PagerDuty alert to find the incident onset time and the alerted service name.
2. Optionally refines the onset time using Prometheus metrics. It looks for the earliest moment where at least two metrics simultaneously became anomalous within a 5-minute window. This matters because metrics often show degradation before anyone notices or an alert fires — the true onset may be several minutes earlier than the PagerDuty alert.
3. Scans every deployment in the GitHub deployments file. Any deployment within 60 minutes before onset or 30 minutes after onset is flagged.
4. A deployment gets **HIGH** relevance if it was deployed to the same service that triggered the alert AND happened before onset. **LOW** if it was a different service. **POST-ONSET** if it happened after the incident started.

### Why it matters

The most common root cause of production incidents is a recent deployment. During an incident, the IC's first question is almost always "did we deploy something?" But answering that question normally requires opening a deployment dashboard, filtering by time, cross-referencing with the alert — all while also coordinating the engineering response.

This section answers that question in one glance, before the IC even reads the AI's analysis. If a HIGH-relevance deployment appears, the IC's immediate next action is usually clear: initiate a rollback of that deployment.

### Who it serves

The IC, within the first 5 seconds of viewing the results. Also useful for the on-call engineer who may be asked "should we roll back?"

---

## Status Page Draft

This is the primary output of the entire system — the customer-facing text that will be published to the status page.

### The header row

Two badges appear side by side at the top.

**Left badge — severity and resolution status.** One of four states:

| Badge | Color | Meaning |
|---|---|---|
| Resolved | Green | Incident is over. Duration displayed (e.g., "Resolved after 2h 25m"). |
| Degraded Performance | Yellow | Service is slower or partially impaired but mostly working. Most requests succeed. |
| Partial Outage | Orange | Significant error rate. Many customers are experiencing failures. |
| Full Outage | Red | Service is essentially down. Nearly all requests are failing. |

The severity comes from the AI extraction's `customer_impact.severity_assessment` field. The resolution status is determined by checking whether the last generated communication stage is "resolved." The duration is calculated by subtracting onset time from resolution time in the extraction's timeline.

**Right badge — security function impact.** This is the single most important classification for a security vendor. One of four states:

| Badge | Color | Meaning |
|---|---|---|
| Detection & Remediation Operational | Green | Email threat detection and automated response are working normally. Customers are protected. |
| Detection Impacted | Red | The system that identifies malicious emails is degraded or offline. Customers may be exposed to threats. |
| Remediation Impacted | Orange | Threats are being detected but automated response (quarantine, deletion) is broken. |
| Security Status Unconfirmed | Gray | The AI could not determine from the available data whether detection is affected. |

When the gray "Unconfirmed" badge appears, a caption beneath it reads: "Verify detection status in the IC Verification section below before publishing." This exists because publishing a communication without knowing the detection status is risky for a security vendor — the IC needs to resolve this ambiguity before going public.

**Why the right badge exists at all.** Abnormal Security is an email security product. Over 75% of Abnormal's customers have consolidated their advanced email security on Abnormal, replacing their legacy secure email gateway. During an incident, they retain baseline Microsoft or Google native filtering, but they are exposed to the behavioral attacks — the sophisticated, targeted threats — that only Abnormal catches. Their first question when they see a status page update is: "Am I still protected?" The right badge answers that question before the customer reads a single word of the communication.

### Incident title and date

Below the badges: the incident date (in Pacific Time) and a bold incident title. The title is generated by the AI to describe the customer-visible symptom — "API Performance Degradation" or "Portal Access Issues" — never internal service names ("api-gateway connection pool exhaustion") or severity codes.

### Word count legend and message cards

A small inline legend shows the color coding for per-message word counts:
- **Green** = 100 words or fewer (target length)
- **Orange** = 101–110 words (acceptable)
- **Red** = over 110 words with a warning marker (too long for a scannable status update)

Below the legend, each generated communication stage appears as a bordered card, displayed in **reverse chronological order** (newest first — Resolved on top if present, Investigating at the bottom). Each card shows:

- **Stage label** — color-coded: green for Resolved, blue for Monitoring, orange for Identified and Investigating.
- **Timestamp** — when this update would be posted, in Pacific Time (e.g., "9:45 AM PT").
- **Word count badge** — colored per the legend.
- **Message body** — the full customer-facing text.

### How the messages are structured

Every message follows a strict six-sentence structure. This structure is not a suggestion to the AI — it is enforced by the generation prompt as a non-negotiable ordering:

1. **What happened + timestamp.** "Starting around 7:20 AM PT, we detected a significant slowdown affecting API performance."
2. **What is NOT affected.** This is always the second sentence. It is never cut, never repositioned, never buried later in the message. Its content is determined entirely by the security function classification:
   - Detection fully operational: "Email security detection and automated remediation remain fully operational and continue to protect against threats."
   - Detection degraded: "Email security detection is currently degraded, and some threats may not be detected or acted upon automatically."
   - Detection offline: "Email security detection is currently offline, and threats may not be detected or remediated automatically."
   - Detection unknown: "We are confirming the status of email security detection services and will provide an update shortly."
   - Remediation impaired, detection fine: "Email security detection remains fully operational; however, automated remediation is [degraded/offline], and detected threats should be reviewed manually in the portal."
3. **Customer impact.** What customers are experiencing, in plain language ("You may experience slower API response times and occasional timeout errors").
4. **Engineering action.** What the team is doing ("Our team is actively investigating the cause").
5. **Customer action.** Usually "No action is needed from you" during the incident. For Resolved: "If you continue experiencing issues, please contact support."
6. **Next update timing.** "We will provide an update within 30 minutes." Omitted for Resolved.

**Why sentence 2 is structurally enforced.** For most Abnormal incidents — portal slowness, API latency, notification delays — email detection and remediation are completely unaffected. That fact is the most important sentence in the entire communication. A customer's security team reading the status page needs to know within 5 seconds whether they should activate contingency measures. Making "what's not affected" the mandatory second sentence ensures that information is always in the same place, every time, across every incident.

**Not all stages are generated.** The AI applies skip rules:
- **Identified is skipped** if root cause is unknown or low-confidence. You should not tell customers you've identified the cause if you haven't.
- **Monitoring is skipped** if the incident resolved quickly (within 30 minutes of mitigation). A 10-minute rollback does not need a separate "we're monitoring" update.

### Download button

A centered "Download as text" button exports all communications as a plain text file with a timestamped filename. For ICs who need to paste into an external status page tool or share via Slack.

### Side-by-side reference comparison

A collapsible expander labeled "Compare with real Abnormal status page post." When opened, it shows two columns:

- **Left column:** A real Abnormal Security status page post (the March 16, 2026 IES disruption Investigating message) rendered in a gray box.
- **Right column:** The system's generated Investigating message rendered in a green box.

This lets the IC visually compare tone, sentence structure, length, and vocabulary against a known-good reference. The sentence structure of the generated messages is reverse-engineered from real Abnormal posts like this one, so the comparison demonstrates the system's fidelity to the actual communication style.

Collapsed by default — it is a calibration tool, not a required review step.

---

## Adjust Communications

Three dropdown controls that reshape the generated draft without re-running the extraction.

| Control | Options | What it changes |
|---|---|---|
| **Tone** | Balanced (default), Technical, Reassuring | Word choice and register. Technical uses precise product names and exact timestamps for SOC teams. Reassuring uses plain language and leads with safety for business audiences. |
| **Detail Level** | Standard (default), Brief, Detailed | Message length. Brief: 2-3 sentences, ~50 words. Standard: 4-6 sentences, ~80 words. Detailed: up to 150 words with full timeline precision. |
| **Emphasis** | Customer Impact (default), Resolution Progress, Root Cause | What the message leads with. Customer Impact leads with what customers experienced. Resolution Progress leads with what the team is doing. Root Cause leads with why it happened. |

Clicking **"Regenerate with these settings"** sends the extraction and original communications to Claude Haiku — a faster, cheaper model — with a rewrite prompt. Haiku only adjusts phrasing, length, and emphasis; it cannot change any facts. The rewrite completes in 1-2 seconds. After regeneration, quality checks automatically re-run on the new text.

A **"Reset to original"** button restores the Sonnet-generated draft.

**Why Haiku for rewrites.** The hard work — reading raw logs, correlating timestamps, classifying security impact, reasoning about root cause — was already done by Sonnet in the extraction step. A rewrite is a prose task, not a reasoning task. Using Haiku makes regeneration feel instant, so the IC can iterate on tone without waiting.

**Who this serves.** The IC or comms reviewer who wants to shape the output to the situation. A minor portal issue warrants a brief, reassuring message. A detection outage affecting all customers warrants detailed, technical precision. Different stakeholders (VP of Support, CISO, CSM) may want different registers for the same incident.

---

## Executive Brief

**What you see.** Either a "Generate Executive Brief" button or, once generated, a three-sentence paragraph in a card with an indigo left border (visually distinct from the green/red/orange of customer-facing content).

**What the three sentences cover:**
1. What happened — service, severity, duration, customer impact scope.
2. Security posture — was detection or remediation affected? (The single most important fact for a security vendor's leadership.)
3. Current status and next step.

**How it is derived.** On-demand — the IC clicks the button. The extraction JSON is sent to Haiku with a prompt that constrains the output to exactly three sentences, under 80 words. It uses Haiku because summarization does not require the reasoning depth of Sonnet.

**Why it exists.** During an incident, a VP or CISO messages the IC asking "what's going on?" The IC is juggling Slack, dashboards, and the customer communication draft. Composing an ad-hoc summary for leadership is cognitive overhead at the worst possible time. This section produces the answer — the IC copies and sends three sentences instead of improvising under pressure.

**Key distinction from the status page draft:** The executive brief is internal-only. It can reference root cause mechanisms, deployment details, and pattern classifications that would never appear in a customer-facing communication. It speaks to leadership, not to customers.

---

## Customer-Specific Outreach

**What you see.** A text input area, a "Generate Outreach Email" button, and below them, any previously generated outreach emails as cards showing subject line, body text, and a copy expander.

**How it works.** The IC types a free-text description of a specific customer — their products, tenure, technical sophistication, integration setup, relationship context. Examples:

- "Colgate, CPG brand, runs a 24/7 SOC with extensive SOAR automation — their security team has dozens of playbooks that trigger off our remediation API."
- "Small fintech startup, only uses IES, their CEO reads these directly, keep it simple."
- "Government customer on Abnormal Gov, formal register required, compliance-sensitive."

This description, plus the full extraction and the public status page communications, is sent to Claude Sonnet. The model selects the right details for this customer — not just adjusting tone, but choosing which facts to include or emphasize based on what matters to this specific account.

**What makes the outreach different from the status page.** The status page is a broadcast — every customer sees the same message. The outreach email is tailored:

- If the customer uses SOAR automation and remediation was impacted, the email explicitly addresses whether their automated playbooks were affected.
- If the customer is technically sophisticated, the email includes root cause mechanism and precise timestamps.
- If the customer is non-technical, the email translates entirely to business impact: "your email protection was not affected."
- The email can include more detail than the status page, but it never contradicts it — same timeline, same affected services, same severity.

**Who this serves.** Customer Success Managers, Account Executives, and Support Engineers who need to proactively reach out to specific accounts after an incident. The system generates a different email for each account from the same verified extraction, ensuring factual consistency while adapting the message.

---

## Quality Checks

**What you see.** One of two states:

- **All clear:** A green success banner reading "All communications pass required field and consistency validation."
- **Issues found:** High-severity items as red error blocks (always visible), followed by medium-severity items in a collapsed expander.

### High-severity checks (red — must fix before publishing)

| Check | What it catches | Why it's high severity |
|---|---|---|
| **Missing: What's not affected** | A communication stage does not state what continues to work. | For a security vendor, omitting this sentence is the most dangerous omission. Customers may assume the worst about their protection. |
| **False detection reassurance** | A message says detection is operational when the extraction classified detection as degraded or offline. | This is the single highest-priority automated check. A status page post that falsely reassures customers about detection while they are actually exposed to threats is categorically worse than any other error. |
| **Missing detection confirmation** | Detection is confirmed operational but the message doesn't mention it. | Wastes the most valuable sentence the communication could contain — the reassurance that protection is intact. |
| **Logic conflict — Pattern vs. detection** | Pattern is "portal_auth_failure" but detection is classified as degraded. | Portal/UI failures do not impair email detection. This contradiction means the AI likely misclassified one or the other. |

### Medium-severity checks (yellow — recommended)

| Check | What it catches |
|---|---|
| Missing customer impact language | Message doesn't describe what customers are experiencing. |
| Missing timestamp | Message doesn't state when the issue started. |
| Missing next-update commitment | Non-Resolved message doesn't tell customers when to expect an update. |
| Missing customer action | Message doesn't say what customers should do (usually "no action needed"). |
| Message over 110 words | Status page updates should be scannable under pressure. |
| Deployment-induced pattern + no flagged deployments | The AI says it's deployment-caused but the deterministic correlation found nothing. |
| Confirmed root cause + low confidence | Contradictory confidence signals. |

### How validation works

Two separate passes run:

1. **Communications validation** scans each generated message for required fields using keyword lists. For example, "what's not affected" is checked by looking for phrases like "remain fully operational," "not affected," "continue to protect," etc. This is intentionally keyword-based (not AI-based) because it must be fast, deterministic, and auditable.

2. **Extraction consistency validation** cross-checks the extraction's own fields for logical contradictions — cases where the AI's own conclusions conflict with each other.

**Who this serves.** The IC or comms reviewer making the publish decision. High-severity items are non-negotiable blockers — do not publish until they are resolved. Medium-severity items are judgment calls.

---

## IC Verification

This is the most interactive section and the one that matters most for trust. It is where the IC engages with the AI's reasoning, reviews its evidence, and decides whether to trust each conclusion.

### Stale data warning

If the incident data is more than 24 hours old, an amber banner appears: "Analysis based on data from **Jan 15, 2025 14:23 UTC** (over 1 year ago). If the incident is still active, re-upload current data." This prevents the IC from publishing communications based on outdated information. The age is displayed in human-friendly terms (days, months, or years — never raw hours).

### Verification summary bar

A single-line status bar: **X/5 verified · Y disputed · Z unverified.** The left border is green when all 5 are verified, red when any are disputed, amber when some are unverified. Gives the IC an at-a-glance count of how much review work remains.

### The five evidence cards

The AI answers five fixed verification questions. Each becomes an expandable card. These five questions are not arbitrary — they correspond to the five things the IC must be confident about before publishing a communication:

#### 1. What's broken?

**What it answers.** Which service is failing and what the symptoms are.

**Why the IC must verify this.** It determines the incident title and which product's status page entry it appears under. If the AI says "api-gateway" but the actual customer-facing impact is on the Portal, the communication addresses the wrong product.

**What you see in the card.** A one-sentence conclusion (e.g., "api-gateway experienced severe latency degradation and database connection pool exhaustion, causing API requests to timeout or respond extremely slowly"). Supporting evidence as verbatim log lines and metric values. Counter-evidence if anything contradicts the conclusion. A verification suggestion — a specific action the IC can take in under 2 minutes.

#### 2. What caused it?

**What it answers.** The root cause — confirmed, hypothesized, or unknown.

**Why the IC must verify this.** It determines whether the Identified stage is generated and what it says. A wrong root cause in a customer communication is embarrassing at best, misleading at worst.

**What you see.** The conclusion (e.g., "PR #12345 deployed at 14:15:00Z increased HTTP client timeout from 10s to 30s, causing database connection pool exhaustion"). Evidence including deployment records, engineer confirmations from Slack, and the rollback that confirmed causation.

#### 3. When did it happen?

**What it answers.** The full timeline: cause, onset, detection, acknowledgment, mitigation, recovery, resolution.

**Why the IC must verify this.** Every timestamp in every communication comes from this timeline. If onset is wrong, the "Starting around X" sentence is wrong. If resolution is wrong, the "Resolved as of X" sentence is wrong.

**What you see.** The conclusion lists all timeline milestones. Evidence cites the specific deployment timestamp, the first anomalous metric reading, the PagerDuty alert time, and the recovery point.

#### 4. What's not broken?

**What it answers.** Which services continued working normally during the incident.

**Why this is the hardest question and the most important one to verify.** It directly determines the mandatory second sentence in every communication — the sentence about detection and remediation status. And it requires proving a negative, which is inherently harder than proving a positive. The AI might say "notification-service was unaffected" — but how does it know? Because there were no errors for that service in the logs? Absence of errors is weaker evidence than explicit confirmation that the service was healthy.

**What you see.** The conclusion states what was unaffected. The evidence section is particularly important here — it will often cite absence of evidence ("No errors appear for notification-service in any provided source during the incident window") and the card will typically show a yellow (medium) confidence indicator rather than green. The counter-evidence section may flag that absence of evidence is weaker than positive confirmation. The verification suggestion will point the IC to a specific dashboard or person who can provide positive confirmation.

#### 5. How bad is it?

**What it answers.** Severity classification (degraded performance, partial outage, full outage) and customer impact scope.

**Why the IC must verify this.** It determines the scope language in every communication — "some US customers" vs "all customers" vs "EU customers." Getting scope wrong means either under-communicating (customers who are affected don't know) or over-communicating (customers who aren't affected worry unnecessarily).

### What every card contains

Each card shows, in order:

- **Confidence indicator** — a colored dot next to the card header: green (high), yellow (medium), red (low). Derived from the extraction's confidence scores for the relevant dimension.
- **Conclusion preview** — the first ~80 characters of the AI's answer, visible in the collapsed card header so the IC can scan all five without expanding any.
- **Full conclusion** — the complete one-sentence answer.
- **Verify / Dispute / Reset buttons** — three buttons for the IC to mark the card's status.
- **Dispute note field** — appears only when the card is disputed. The IC types what's wrong. This is important for shift handoffs: the incoming IC sees not just that a claim was disputed, but why.
- **Supporting evidence** — verbatim excerpts from source data files. Each excerpt shows the source filename, the exact text (displayed in a code block so it's clearly raw data, not paraphrase), and a relevance note explaining why it supports the conclusion.
- **Counter-evidence** — anything that weakens or contradicts the conclusion, displayed with an amber highlight. The AI is required to always populate this. Empty counter-evidence means the AI found truly nothing contradictory, not that it didn't look.
- **Verification suggestion** — a specific, actionable step: "Check the Grafana dashboard for api-gateway database connection pool metrics between 14:15–15:45 UTC to confirm whether pool utilization accurately reflected the exhaustion state." Never generic ("review the logs").

**Why counter-evidence is mandatory.** An AI that only shows supporting evidence is trying to convince you. An AI that also shows counter-evidence is trying to help you decide. For a security vendor — where the cost of a wrong communication is customer trust — the IC needs to see what weakens a conclusion, not just what supports it.

### Data availability

Below the cards, a list shows which of the five standard source types were available: PagerDuty, CloudWatch logs, Prometheus metrics, GitHub deployments, and incident context (Slack/engineer notes). Missing sources are flagged with what they would have provided: "incident_context not uploaded — Engineer discussion, root cause confirmation, Slack thread unavailable. Related confidence is reduced."

This matters because the extraction's quality is bounded by its input. No Slack thread means no engineer confirmations, which means root cause confidence drops. The IC should weight their verification effort accordingly.

### Internal-to-customer language mapping

A collapsible section showing internal terms found in the source data (engineer emails, hostnames, PR numbers, commit SHAs, internal Slack channels) alongside the customer-facing language the AI used instead. Lets the IC verify that no internal details leaked into the generated communications.

### Pre-publish checklist

Five checkboxes:

1. Affected service is correct.
2. Root cause is correct (or confirmed as unconfirmed).
3. Timeline boundaries are correct.
4. "Unaffected" claims are accurate for this security product.
5. Generated communications reviewed for tone and accuracy.

These are intentionally redundant with the evidence cards. The cards ask "does the AI's analysis match the data?" The checklist asks "does the communication match reality as you, the IC, understand it?" The IC may know things the data does not contain — a Slack conversation that wasn't uploaded, a dashboard they checked manually. The checklist captures that human judgment.

**Copy gating.** When all five checkboxes are checked AND zero evidence cards are disputed, the full communications text appears in a copyable code block. If any card is disputed: red error, copy blocked. If checkboxes are incomplete: info message showing how many remain.

**Why the copy is gated.** This is the human-in-the-loop guarantee. The system drafts; the human decides what ships. The gating ensures the IC cannot accidentally copy and publish without explicitly affirming each dimension. For a security vendor, this is non-negotiable.

---

## Analyst View (optional, collapsed)

Not needed for the publish decision. For understanding the AI's reasoning and for post-incident analysis.

### Pattern classification

**What you see.** The detected incident pattern (e.g., "Deployment Induced"), a confidence dot, and 2-3 sentences of reasoning.

The system classifies every incident into exactly one of eight patterns:

| Pattern | Meaning |
|---|---|
| deployment_induced | A code or config deployment correlates with onset AND is confirmed by engineers or rollback. |
| infrastructure_cascade | Multiple services fail simultaneously with no deployment trigger. |
| regional_failure | Errors scoped to a specific region. |
| portal_auth_failure | UI/login errors, but core email processing (detection, remediation) is unaffected. |
| third_party_dependency | Errors reference external APIs (Microsoft Graph, AWS) with no internal cause. |
| integration_api_failure | Outbound webhooks/SIEM/SOAR failing, core product fine. |
| silent_degradation | No hard errors but quality metrics drift. |
| isolated_environment | Gov/FedRAMP-scoped. |

**Why it exists.** Pattern classification drives two things: (1) quality checks — certain pattern + detection status combinations are logically impossible and get flagged, and (2) cross-incident trend detection over time.

### Inference chain

**What you see.** The AI's key reasoning steps, grouped by inference type:

- **Engineer Confirmations** — claims supported by explicit engineer statements in Slack ("@bob: confirmed, the config change caused it"). Highest confidence. Expanded by default.
- **Direct Observations** — facts stated in one source (an error count in a log, a deployment timestamp).
- **Cross-References** — conclusions derived by correlating multiple sources (deployment time + first metric anomaly + engineer discussion = causal link). These are often the most valuable inferences.
- **Absence of Evidence** — conclusions based on what's NOT in the data. Important to surface because they are the weakest form of evidence and most likely to be wrong.

Each entry shows a confidence dot and its source data points.

**Why it exists.** If the IC disagrees with a conclusion in an evidence card, the inference chain shows which reasoning step to challenge. It also makes the weakest links visible — an absence-of-evidence inference with low confidence is a clear signal to verify independently.

### Recent incident patterns

**What you see.** A deduplicated list of previously analyzed incidents, each showing its pattern classification, a one-line summary, and the analysis date.

**How it is derived.** Every time the pipeline runs, key extraction fields are saved to a JSON file on disk. This section loads recent files and displays them.

**Why it exists.** A single deployment-induced incident is a one-off. Five in two weeks is a process problem. By surfacing recent patterns alongside the current analysis, the system nudges toward structural thinking without requiring the IC to go look for historical data. This is the seed of the cross-incident pattern detection described in the PRD.

---

## Raw Extraction Data (optional, collapsed)

The full structured extraction — the foundation of everything else on the page.

### Security function status

Two status pills: Detection and Remediation, each showing Fully Operational / Degraded / Offline / Unknown. Below them: the primary category (Detection, Remediation, or Other), confidence level, and the AI's reasoning — particularly important when status is Unknown, because it explains why the AI couldn't determine the answer ("api-gateway is a generic infrastructure service name without explicit evidence linking it to detection or remediation functions").

### Timeline

All seven milestones:

| Field | What it represents |
|---|---|
| Cause Time | When the triggering event occurred (e.g., a deployment). |
| Onset Time | When degradation first appeared in metrics/logs. Often earlier than the alert. |
| Detection Time | When the alert fired or engineers noticed. |
| Acknowledged Time | When an engineer responded. |
| Mitigation Time | When a fix was deployed. |
| Recovery Time | When metrics returned to baseline. |
| Resolved Time | When the incident was formally closed. |

The gap between onset and detection is the detection latency — a metric that matters for incident response maturity.

### Root cause

Summary and status: confirmed (engineers verified it or rollback proved it), hypothesized (evidence suggests it but unverified), or unknown.

### Confidence scores

Four dimensions rated high / medium / low: root cause, scope, timeline, customer impact. These map directly to the evidence card confidence dots. They tell the IC where to focus verification effort — a "low" on scope means spend time confirming which customers are affected, not re-checking the timeline.

### Data gaps

Specific unknowns — not generic "more data needed" but precise: "No Slack thread available — cannot confirm or deny engineer hypothesis about root cause" or "Prometheus metrics only cover api-gateway; no data for notification-service to confirm it is unaffected."

### Internal details excluded

Every internal term found in source data that was excluded from customer communications: engineer emails, hostnames, cluster names, PR numbers, commit SHAs. Displayed so the IC can verify the exclusion list is complete.

---

## How it all connects

The sections are not independent. They form a chain:

```
Raw source files
     │
     ├─→ Deployment Correlation (no AI) ──→ Pre-Flight Context
     │
     └─→ Extraction (Sonnet) ──→ Raw Extraction Data
              │                         └──→ Analyst View
              │
              ├──→ Generation (Sonnet) ──→ Status Page Draft
              │         │                       └──→ Tone controls → Rewrite (Haiku)
              │         └──→ Validation ──→ Quality Checks
              │
              ├──→ Evidence Trace ──→ IC Verification
              │
              ├──→ Executive Brief (Haiku, on-demand)
              │
              └──→ Customer Outreach (Sonnet, on-demand)
```

The extraction is the single source of truth. If the IC verifies the extraction through the evidence cards, they have verified the foundation of every other section on the page.

---

## The publish workflow, end to end

| Step | Section | Time | What the IC does |
|---|---|---|---|
| 1 | Header badges | 2 sec | Glance: how bad, is it over, are customers protected? |
| 2 | Status page draft | 30 sec | Read the Investigating and Resolved messages. |
| 3 | Quality checks | 10 sec | Any red items? Fix or note them. |
| 4 | Evidence cards | 2–5 min | Expand each card, review evidence, mark verified or disputed. |
| 5 | Checklist | 15 sec | Five checkboxes. |
| 6 | Copy | 5 sec | Text appears. Paste into status page tool. |

**Total: 3–6 minutes from raw data to published communication.** Compared to 10–20 minutes of manual synthesis — reading Slack, correlating logs, drafting prose, self-reviewing — under the cognitive pressure of an active incident.

The page is designed so the IC can stop at any depth and still have useful output. A quick glance gives them a draft to work from. Full verification gives them a vetted, evidence-backed communication. The depth of engagement scales with the severity of the incident and the IC's available attention.
