# AI-Enhanced Incident Management Communications

**Author:** Anubhav Jain | **Date:** March 2026

---

## The Problem

During a production incident at Abnormal, the person fixing the problem is also responsible for telling customers what's happening. The bottleneck isn't writing — it's synthesis. An incident commander has to pull signal from Slack threads, PagerDuty alerts, CloudWatch metrics, and deployment records, distill it into something customer-appropriate, and do this under time pressure while also coordinating the engineering response. This takes 10-20 minutes per update, and the quality varies with the author and the severity of the situation.

The cost is compounding: delayed first communications, inconsistent tone across incidents, cognitive overhead on the people who should be focused on resolution, and — most critically for a security vendor — the risk of miscommunicating whether customers are still protected.

## Vision

One extraction, many outputs. The system ingests raw incident data once, builds a structured understanding of what happened, and generates purpose-built communications for every audience that needs one — starting with the status page, extending to customer-specific outreach, executive summaries, and support talking points. Every output traces back to the same verified facts.

---

## Assumptions

1. The hard part is synthesis under cognitive load, not prose composition. The AI's primary value is structured understanding, not polished paragraphs.

2. Customer impact must be *derived* from technical signals. "Connection pool exhausted" needs to become "customers experienced degraded API performance." This requires reasoning about what customers experience, not reformatting what engineers observe.

3. For a security vendor, the most dangerous error is false reassurance about detection status. Getting a sentence wrong about protection is categorically worse than awkward phrasing.

4. Detection and remediation are architecturally independent from portal and operational tools at Abnormal. Most incidents don't affect core protection, and the communication must make this distinction clearly — it's the first thing a customer's security team needs to know.

5. A human must approve every external communication. The AI drafts and verifies; people decide what ships.

---

## Who This Serves

The system serves four audiences whose needs diverge from the same underlying incident.

**The Incident Commander** gets a structured incident summary — affected services, security function impact, severity, timeline, root cause — that they can verify in seconds rather than assembling from raw data. An evidence trace presents fixed verification questions with verbatim source citations so the IC reviews evidence, not prose. During shift changes, the structured extraction doubles as a handoff brief.

**The Support or Comms Reviewer** gets the status page draft alongside automated quality checks — validation for completeness, consistency, and the single most dangerous error: false reassurance about detection status. They verify a structured checklist rather than mentally reconstructing whether the facts in a paragraph are correct.

**The Customer Success Manager** today improvises account-specific talking points from the same generic status page text every customer sees. The architecture — one extraction, many outputs — makes it straightforward to generate tailored communications for specific accounts. That's a near-term extension, not a rebuild.

**The Customer's Security Team** is making real decisions based on the status page. Over 75% of Abnormal's customers have consolidated their advanced email security on Abnormal, replacing their legacy secure email gateway. During an incident, they retain baseline Microsoft or Google native filtering, but they're exposed to the behavioral attacks only Abnormal catches. Their first question is "am I still protected?" The system answers this by classifying detection and remediation status independently and placing "what's not affected" as the second sentence of every communication, by structural rule.

---

## User Stories

- As an **incident commander**, I want a structured summary generated from raw incident data so I can verify facts and publish an update in under five minutes instead of synthesizing from multiple sources.
- As an **IC during a shift change**, I want the extraction to serve as a handoff brief so the incoming commander has full context without a verbal download.
- As a **comms reviewer**, I want automated consistency checks — especially for false reassurance about detection — so I'm catching errors against a checklist rather than relying on careful reading under pressure.
- As a **CSM**, I want to generate a customer-specific email from the same incident extraction so I can send tailored outreach without rewriting the status page by hand.
- As a **customer security team member**, I want the status page to tell me whether detection and remediation are affected before anything else, so I can decide whether to activate contingency measures.

---

## Architecture

The central design decision is separating extraction from generation.

**Extraction** processes five source types (PagerDuty alerts, CloudWatch logs, Prometheus metrics, GitHub deployments, Slack threads) and produces a structured incident model: affected services, security function impact (detection and remediation as independent fields), root cause with evidence classification, an inference log tagging every factual claim with its source, and an evidence trace with verbatim excerpts. A deterministic deployment correlation runs before any LLM analysis, flagging suspicious deployments through multi-metric consensus so the IC has an independent cross-check against the AI's conclusions.

**Generation** reads the structured model and produces audience-appropriate outputs. Today that's status page communications across four incident stages (Investigating, Identified, Monitoring, Resolved). Adding new output types — executive summaries, customer-specific emails, support talking points — is a prompt-level change, not a pipeline rebuild.

This separation matters because it makes factual review happen once, before any prose is generated. The IC verifies the extraction. Every downstream output inherits that verified foundation.

### Workflow Integration

The tool meets the existing incident response process where it already happens. When an incident is declared, the IC (or a support engineer) pastes or uploads the available data sources. The system produces the extraction and draft communication. The IC verifies using the structured checklist, edits if needed, and publishes. In later phases, data ingestion is automated via API connections to PagerDuty, CloudWatch, GitHub, and Slack — eliminating the manual upload step and enabling real-time draft updates as new information arrives.

---

## Key Design Decisions

| Decision | What We Chose | Why |
|----------|--------------|-----|
| Two-phase pipeline | Separate extraction from generation | Factual review happens once. Every output inherits verified facts. |
| Security function as independent fields | Detection and remediation tracked separately | Portal down ≠ detection down. This classification determines what the communication says about protection. |
| "What's not affected" as structural rule | Enforced as second sentence, never buried | For most Abnormal incidents, this is the most important sentence in the update. |
| Five fixed verification questions | Non-negotiable checklist before publish | Prevents skimming past uncertain claims. The IC engages with every high-risk assertion. |
| Deterministic deployment correlation | Pre-LLM, multi-metric consensus | Independent cross-check the IC can trust even if they distrust the AI's reasoning. |

---

## Error Taxonomy

| Error | Consequence | Mitigation |
|-------|-----------|------------|
| False reassurance about detection | Customers believe they're protected when they aren't | Consistency validator catches contradictions; highest-priority automated check |
| Hallucinated facts | Plausible claims with no basis in source data | Extraction rule: null over invention. Inference log tags every claim with source. |
| Internal details leaked | Exposes architecture, personnel, or process | Exclusion list in prompt; excluded terms surfaced for IC spot-check |
| Upstream attribution missed | Abnormal blamed for a provider outage | Extraction distinguishes third-party dependency patterns |
| Premature resolution | "Resolved" followed by recurrence | Resolution confidence scored by evidence type; system defaults to "monitoring" |

---

## Path Forward

The prototype validates the core pipeline: accurate extraction and status page generation from real incident data. The next capabilities extend the platform to address the remaining problems — inconsistency, manual overhead, and the gap between generic status updates and what specific customers need.

**Customer-Specific Outreach.** The extraction already identifies affected services and customer impact. The next layer generates tailored communications from natural language context about the account ("non-technical buyer, needs plain language" or "enterprise CISO, wants root cause detail"). This turns the tool from a status page writer into an incident communications platform.

**Adjustable Tone and Content Controls.** After the initial draft, the IC or reviewer should be able to tune tone (more technical ↔ more reassuring), detail level, and emphasis without rewriting. This addresses the inconsistency problem: different ICs write differently, but adjustable controls on a consistent base produce communications that vary intentionally.

**Cross-Incident Pattern Detection.** The inference logs from every analyzed incident persist to disk. Over time, this corpus surfaces structural patterns: "Three of the last five incidents involved configuration changes without load testing." This moves the tool from reactive communication to proactive risk reduction.

---

## Rollout

**Phase 1 — Shadow.** Run the pipeline on every incident alongside the manual process. Compare AI output to what humans wrote. The IC sees both and flags discrepancies.
*Gate:* 80%+ of drafts need two or fewer factual edits. No false reassurance errors in shadow output.

**Phase 2 — Draft-first.** AI generates the default draft. The IC reviews using the verification workflow and publishes. Manual drafting becomes the fallback, not the default.
*Gate:* Time-to-first-communication drops below 10 minutes. Zero factual errors reach customers over a 30-day window.

**Phase 3 — Integrated platform.** API connections for automated data ingestion. Multi-audience generation enabled. Tone controls and customer-specific outreach in production. Cross-incident pattern analysis begins accumulating data.

---

## Measuring Quality

The metrics are ordered by severity of failure, not ease of measurement.

- **False reassurance rate.** Communications claiming detection is operational when it isn't. Target: zero. This is the only metric with a zero-tolerance threshold.
- **Service identification accuracy.** Correct affected and unaffected services vs. incident record. Target: >95%.
- **Draft usefulness.** Percentage of drafts published with two or fewer edits. Target: >70% in Phase 2.
- **Communication completeness.** Each update includes: affected service, what's not affected, customer impact, action guidance, timestamp, next-update commitment.
- **Time-to-first-communication.** From incident declaration to first published update. Baseline vs. AI-assisted, tracked per severity level.
- **Evidence trace dispute rate.** Claims marked "disputed" by ICs during verification. Elevated rates signal extraction problems requiring prompt-level fixes.

---

## Competitive Context

Incident.io, Rootly, and PagerDuty offer AI-assisted incident communication as part of broader incident management platforms. Their generation is general-purpose — trained on generic incident patterns, not the specific dynamics of a security product.

An Abnormal-specific solution understands that "detection and remediation remained fully operational" is the most important sentence in most updates. It classifies security function impact because the audience — security teams — is making real protection decisions based on what the status page says. General-purpose tools produce adequate communications. Domain-specific tools produce communications that security teams trust enough to act on.

---

## Prototype Notes

The prototype demonstrates the full extraction→generation pipeline on the provided anonymized incident data. It processes real logs, metrics, alerts, deployment records, and Slack threads to produce structured incident analysis and status page drafts — not static templates.

The prototype intentionally shows analytical breadth (deployment correlation, evidence traces, inference logs, consistency validation) rather than a narrow polished workflow. The goal is to demonstrate what the extraction makes possible across multiple decision contexts, then learn which capabilities matter most in practice.

---

## Appendix: Extended Assumptions

**On security function classification.** The distinction between detection issues, remediation issues, and operational issues is the most important classification for Abnormal's incident communications. This is based on studying Abnormal's real status page, where "detection and remediation remained fully operational" appears consistently in updates about portal or operational issues. If customers don't actually differentiate their response based on this classification, the system over-invests in a distinction that doesn't matter. We believe they do.

**On inference logging.** Persisting the AI's reasoning chain for every incident creates compound value: IC verification in the short term, cross-incident pattern detection in the medium term, prompt improvement data in the long term. If ICs don't find inference logs useful and patterns don't yield actionable insights, the cost is low — disk storage and a collapsed UI section.

**On evidence verbatim requirements.** Requiring the AI to cite verbatim log lines and metric values (rather than summaries) improves IC trust and verification speed at the cost of occasionally awkward raw excerpts. We err toward over-citation because under-citation in a security context has asymmetric consequences.

**On the five fixed verification questions.** A non-negotiable checklist is more effective than free-form review, though some ICs may find it rigid for low-severity incidents. A production version could scale requirements by severity. We default to five-for-all because under-verification is harder to recover from than over-verification.
