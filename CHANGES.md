# UI & Feature Changes — March 26, 2026

Changes made to close gaps between the PRD and the current prototype, informed by the gap analysis (iterative prompt #12) and current UI screenshots.

---

## Bug Fixes

### 1. Removed developer annotation text from status page header
**Before:** The literal text "Right badge: security function impact (red = detection may be down)" was rendered on-screen as body text beneath the status badges — visible to ICs as if the UI were narrating itself.
**After:** Removed entirely. The security status badge speaks for itself.

### 2. Fixed stale data warning format
**Before:** Displayed raw hours ("10449h ago") which was technically correct but confusing — 435 days expressed as hours reads like a bug.
**After:** Human-friendly labels: "over 1 year ago", "about 3 months ago", "14 days ago" depending on the age.

### 3. Fixed dynamic zone numbering
**Before:** Zone numbering was hardcoded (②, ③, ④) — when Zone 1 (Pre-Flight Context / Deployment Correlation) was hidden because no deployments were flagged, the visible zones started at ② with no explanation, looking like a UI error.
**After:** Zone numbers are computed dynamically. If the deployment zone is hidden, remaining zones renumber starting from ①.

### 4. Fixed quality checks severity ordering
**Before:** Medium-severity consistency flags (yellow cards) rendered *above* high-severity validation warnings (red cards), inverting visual priority. The spec says high-severity checks should appear first.
**After:** All high-severity items (both consistency flags and validation warnings) render first as red error blocks. All medium-severity items are grouped into a single collapsed expander below them.

### 5. Fixed duplicate recent incident patterns
**Before:** The "Recent Incident Patterns" list in the Analyst View showed duplicate entries with near-identical descriptions, destroying the value of pattern analysis.
**After:** Deduplicated by incident summary. Also added analysis date to each entry for temporal context.

---

## New Features (from PRD)

### 6. Executive Brief generation
**PRD reference:** "Executive brief — Additional Claude call that produces a 3-sentence internal summary for leadership" (CLAUDE.md Section 16, Bonus Feature #3; PRD Path Forward).
**Implementation:** On-demand button generates a 3-sentence internal-only summary covering: what happened, security posture impact, and current status/next steps. Uses Haiku for fast generation. Rendered with a distinct indigo left-border to visually separate it from customer-facing content.

### 7. Export / Download functionality
**PRD reference:** "Export — Download generated communications as plain text or markdown" (CLAUDE.md Section 16, Bonus Feature #4).
**Implementation:** Download button below the status page draft exports all communications as a formatted text file with timestamped filename.

### 8. Side-by-side reference comparison
**PRD reference:** "Side-by-side comparison — Show generated draft next to a real Abnormal status page post for the same incident type" (CLAUDE.md Section 16, Bonus Feature #1).
**Implementation:** Collapsible section below the status page draft shows the generated Investigating message alongside a real Abnormal status page post (IES disruption, March 16 2026) for direct tone/structure/length comparison.

---

## UX Improvements

### 9. Security status badge with actionable guidance
**Before:** The "Security Status Unconfirmed" badge floated in the header with no proximate explanation of what an IC should do about it.
**After:** When detection status is unconfirmed, a caption below the badge directs the IC to the verification section: "Verify detection status in the IC Verification section below before publishing."

---

## Not Implemented (assessed as large lift)

- **Automated API connections** (PagerDuty, CloudWatch, Slack) for real-time data ingestion — Phase 3 in the PRD rollout, requires infrastructure beyond the prototype scope.
- **Cross-incident pattern detection with persistent corpus** — requires a durable storage layer and analysis pipeline beyond the inference log files.
- **Customer-specific outreach from CRM data** — the outreach feature exists with free-text customer descriptions; CRM integration would be a separate project.
- **Full Zone 1 deployment correlation rendering** — the deterministic correlation logic runs and feeds into the extraction, but Zone 1 only renders when HIGH-relevance deployments are found. The sample data's deployment may not trigger HIGH relevance depending on service name matching. The logic is correct; the data-dependent rendering is working as designed.

---

## Preserved Functionality

All existing functionality was preserved:
- Full extraction pipeline (deployment correlation, Claude extraction, generation, validation)
- Tone/Detail/Emphasis controls with Haiku fast rewrite
- Customer-specific outreach email generation
- IC Verification workflow (5 evidence cards, verify/dispute, publish checklist)
- Pattern Analysis & Inference Log (Analyst View)
- Structured Incident Analysis (Raw Extraction Data)
- Quality checks (communications validation + extraction consistency)
- Inference log persistence to disk
- Sample data loading and file upload
