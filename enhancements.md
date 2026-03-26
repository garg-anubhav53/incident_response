# Enhancements Summary

---

## 1. Extraction Prompt — Accuracy and Honesty Rules

**Rule 0 (Null over hallucination):** Added explicit override forcing unknown fields to `null`/[] instead of invented values.

**Rollback = Confirmation:** Formalized that successful rollback = confirmed root cause even without engineer statement.

**Portal/Detection Incompatibility:** Added constraint that `portal_auth_failure` is incompatible with `detection_status=degraded/offline`.

**What-Is-Not-Broken Guidance:** Requires specific logged absence or engineer statement, not just service names that "seem fine."

**Confidence Structure Clarification:** Distinguished three confidence structures and their purposes.

---

## 2. Generation Prompt — Communication Structure Rules

**What's Not Affected Placement:** Must be the second sentence in every update, never buried.

**Customer Action in All Stages:** Removed exemption — Investigating stage now requires action line.

**Word Count Trim Priority:** Ranked trim order — never cut "what's not affected" sentence.

**Identified Stage Guidance:** Tied to `root_cause.status` — confirmed/hypothesized/unknown determines language/presence.

**Concrete Example Message:** Added few-shot example (79 words) to anchor output format.

**DST Handling:** Specified PDT vs PST conversion, always label as "PT."

---

## 3. Metrics Preprocessing — Verbatim Evidence Support

`summarize_metrics()` now returns two-part output: human-readable summary + `RAW ANOMALOUS VALUES` section with verbatim timestamp-value pairs for precise evidence citations.

---

## 4. User Message Construction — Filename Annotation

`build_user_message()` detects file types internally and annotates section headers with original filenames for accurate `source_file` citations.

---

## 5. Deployment Correlation — Multi-Metric Consensus and Post-Onset Window

**Multi-metric consensus:** Requires ≥2 metrics anomalous in same 5-minute window for onset detection.

**Post-onset window:** Added 30-minute post-onset scan for potential worsening factors, labeled "POST-ONSET."

**PR number exclusion:** Removed internal PR numbers from UI output.

---

## 6. Validation — Consistency Checks and Communication Rules

**validate_extraction_consistency():** New function cross-checks pattern vs security function impact for logical contradictions.

**Customer action validation:** Removed Investigating exemption — all stages require action line.

**Word count validation:** Added >110 word warning with medium severity.

**SFI validation:** Ensures detection status is mentioned when confirmed operational, prevents false reassurance.

---

## 7. UI Rendering — Zone Organization and Visual Improvements

**6 named zones:** Pre-Flight Context → Status Page Preview → Quality Checks → IC Verification → Analyst View → Raw Extraction Data.

**Deployment alerts:** Custom `.deploy-high` CSS class for HIGH relevance, separate expander for POST-ONSET.

**Status page enhancements:** Duration badge ("Resolved after Xh Ym"), word count badges per stage.

**Evidence trace:** Conclusion preview in headers, disputed cards auto-expand.

**Pattern analysis:** Inference entries grouped by type, confidence summary line.

---

## 8. Session State Management

Added `consistency_flags` session state key, initialized as [], reset in Start Over handler.

---

## 9. Documentation Updates

Updated CODEBASE_WALKTHROUGH.md and all iterative prompt files to reflect implementation changes.
