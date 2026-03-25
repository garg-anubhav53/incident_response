# CLAUDE.md — Abnormal Incident Communications Prototype

> **Read this entire file before touching any code.** This is the single source
> of truth for architecture, interfaces, prompt contracts, style targets, and
> working rules. When this file and code disagree, this file wins.

---

## 1 · Mission Statement

Build a Streamlit proof-of-concept that takes messy incident data (Slack
threads, logs, deployment events, metrics) and produces **customer-facing
status page communications** that are indistinguishable from what Abnormal
Security actually publishes at https://status.abnormalsecurity.com.

**The product is the prompts and data preprocessing.** The Streamlit shell is a
thin display layer. Spend 70% of effort on prompt quality and data
preprocessing, 20% on pipeline interfaces and type safety, 10% on UI.

---

## 2 · Priority Stack

When making any decision, use this ranked list. Higher items override lower:

1. **Output quality** — Generated communications read like real Abnormal posts
2. **Honest uncertainty** — Gaps and unknowns are surfaced, never hallucinated over
3. **Token discipline** — Preprocessed data is compact; prompts are tight; max_tokens enforced
4. **Type safety** — Every stage returns its exact TypedDict; JSON parsing never crashes
5. **Modularity** — Any stage swappable without touching others
6. **UI simplicity** — Streamlit shows the pipeline arc; no fancy components needed

---

## 3 · Stack

```
Python 3.11+
streamlit            → app.py entry point
anthropic            → Python SDK, all LLM calls use claude-sonnet-4-5
python-dotenv        → .env for ANTHROPIC_API_KEY
```

**Environment:**
```
ANTHROPIC_API_KEY    in .env (never commit)
streamlit run app.py → http://localhost:8501
Model: claude-sonnet-4-5 for all pipeline calls
Temperature: 0.2 for extraction/gap-detection/quality, 0.4 for comm generation
```

---

## 4 · File Map & Ownership

Only open a file when you are about to edit it. This table is the complete
list of files in the project.

| Path | Responsibility |
|---|---|
| `app.py` | Streamlit shell; calls pipeline; renders output. **Zero business logic.** |
| `pipeline/preprocessor.py` | `preprocess(raw_sources) → ProcessedData` |
| `pipeline/extractor.py` | `extract_facts(processed) → FactSet` — Claude call |
| `pipeline/gap_detector.py` | `detect_gaps(facts) → GapReport` — Claude call |
| `pipeline/comm_generator.py` | `generate_comms(facts, gaps) → CommDraft` — Claude call |
| `pipeline/quality_checker.py` | `check_quality(draft, facts) → QualityReport` — Claude call |
| `prompts/*.txt` | All prompt templates (plain text, loaded at import) |
| `utils/types.py` | Shared TypedDicts — the canonical contracts |
| `utils/data_loader.py` | Loads and routes source files by type |
| `utils/llm.py` | Thin wrapper: sends prompt, parses JSON, handles errors |
| `data/` | Sample incident data files |
| `requirements.txt` | Pinned dependencies |

---

## 5 · Pipeline Architecture

```
raw_sources (dict of file paths/content)
     │
     ▼
[preprocessor]  →  Cleans Slack JSON, formats logs, strips noise
     │  returns ProcessedData
     ▼
[extractor]     →  Claude call: structured fact extraction
     │  returns FactSet
     ├──────────────────────────────────┐
     ▼                                  ▼
[gap_detector]                    [comm_generator]
 Claude call: what's               Claude call: drafts all
 unknown/unconfirmed               status page messages
     │  returns GapReport              │  returns CommDraft
     └──────────┬──────────────────────┘
                ▼
         [quality_checker]
          Claude call: scores draft
          against style checklist
                │  returns QualityReport
                ▼
           app.py renders everything
```

**gap_detector and comm_generator run in parallel** — they share only FactSet
as input and do not write shared state. Use `asyncio.gather` or sequential
calls; do not add threading complexity.

---

## 6 · Stage Interface Contracts (Canonical)

These TypedDict shapes are the law. Every pipeline function must return exactly
this shape. Every prompt must instruct the model to produce JSON matching this
shape. Put these in `utils/types.py`.

```python
from typing import TypedDict

class ProcessedData(TypedDict):
    slack_thread: str          # "HH:MM @user: message\n..." (cleaned)
    log_summary: str           # structured log entries, noise removed
    deployment_events: list    # [{"time": str, "service": str, "change": str}]
    metrics_summary: str       # narrative of anomalous metrics
    raw_timeline: list         # [{"time": str, "event": str, "source": str}]

class FactSet(TypedDict):
    incident_start_utc: str | None    # "HH:MM UTC" or None if uncertain
    incident_end_utc: str | None
    affected_services: list[str]      # MUST use product registry names only
    customer_scope: str | None        # "some US customers", "EU customers"
    customer_impact: str              # what customers couldn't do
    current_status: str               # "investigating"|"identified"|"monitoring"|"resolved"
    confidence_notes: dict            # field_name → "confirmed"|"inferred"|"unknown"

class GapReport(TypedDict):
    missing_fields: list[str]           # FactSet keys where value is None
    low_confidence: list[str]           # fields marked "inferred" or "unknown"
    internal_terms_detected: list[str]  # jargon to scrub before publishing
    suggested_placeholders: dict        # field → placeholder text for draft

class CommDraft(TypedDict):
    investigating: str    # First public message (always present)
    identified: str       # Root cause identified (may be empty string)
    monitoring: str       # Fix deployed, watching (may be empty string)
    resolved: str         # Final resolution (always present)

class QualityReport(TypedDict):
    score: int                     # 0–100
    checklist: list[dict]          # [{"item": str, "pass": bool, "note": str}]
    flagged_phrases: list[str]     # specific strings to revise
    suggested_revision: str | None # revised investigating or resolved msg
```

---

## 7 · LLM Call Pattern

Every pipeline stage that calls Claude MUST use the same pattern. Build this
as `utils/llm.py` so all stages share it.

```python
import json
import anthropic
from pathlib import Path

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def call_claude(
    system_prompt: str,
    user_content: str,
    max_tokens: int,
    temperature: float = 0.2
) -> dict:
    """Send prompt to Claude, parse JSON response, return dict.

    Raises ValueError if response is not valid JSON.
    """
    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )
    text = response.content[0].text

    # Strip markdown fences if model wraps JSON in ```json ... ```
    if text.strip().startswith("```"):
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

    return json.loads(text.strip())
```

**Token budgets per stage (hard limits):**

| Stage | max_tokens | Temperature | Why |
|---|---|---|---|
| extractor | 800 | 0.2 | Structured JSON, small output |
| gap_detector | 500 | 0.2 | Short list output |
| comm_generator | 1200 | 0.4 | Longest: 4 message drafts |
| quality_checker | 600 | 0.2 | Checklist + optional revision |

---

## 8 · Prompt Engineering Rules

This is the highest-leverage section. Follow every rule.

### 8.1 · Prompt file conventions

- All prompts live in `prompts/` as `.txt` files
- Load with `Path("prompts/xxx.txt").read_text()` at module import
- **Never** put prompt text in Python f-strings in pipeline code
- Each prompt MUST include the exact TypedDict definition for its output
- Each prompt MUST instruct: "Respond with ONLY valid JSON matching this schema. No markdown, no explanation, no preamble."

### 8.2 · Prompt versioning

Before editing any prompt file:
1. Copy current to `prompts/xxx_v1.txt` (increment version number)
2. Edit `prompts/xxx.txt` (the active version)
3. Never delete old versions — they're your A/B history

### 8.3 · Prompt structure template

Every prompt file should follow this skeleton:

```
You are an expert at [specific role].

## Task
[One paragraph: exactly what to do]

## Input
You will receive [description of user message content].

## Output Schema
Respond with ONLY valid JSON matching this Python TypedDict:

```python
class [TypeName](TypedDict):
    field: type  # description
```

## Rules
1. [Most important constraint]
2. [Second most important]
...

## Examples
Input: [condensed example]
Output: {"field": "value", ...}
```

### 8.4 · What makes prompts good vs bad for this project

**GOOD prompt traits:**
- Includes 1-2 concrete input→output examples (few-shot)
- States constraints as numbered rules, not paragraphs
- Embeds the TypedDict schema verbatim
- Tells the model what to do when data is missing ("set to null and add to confidence_notes")
- References the Abnormal product registry by name

**BAD prompt traits (avoid these):**
- Long narrative paragraphs the model will skim
- Instructions that conflict with each other
- Asking for chain-of-thought AND JSON-only output (pick one; for this project, JSON-only)
- Embedding the entire style guide when only relevant rules are needed
- Not specifying what to do with uncertainty (model will hallucinate to fill gaps)

### 8.5 · Token discipline in user messages (preprocessing → prompt input)

The user message to each Claude call is the preprocessed data. Keep it small:
- **extractor** user message: the full ProcessedData formatted as labeled sections. Target ≤ 1500 tokens.
- **gap_detector** user message: the FactSet as JSON. Target ≤ 300 tokens.
- **comm_generator** user message: FactSet + GapReport as JSON. Target ≤ 500 tokens.
- **quality_checker** user message: CommDraft + FactSet as JSON. Target ≤ 800 tokens.

If preprocessed data exceeds the target, the preprocessing is not aggressive
enough. Fix preprocessing first, never raise max_tokens to compensate.

---

## 9 · Abnormal Status Page Style Guide

**Source of truth:** https://status.abnormalsecurity.com — real incidents
scraped March 2026. These patterns are not invented; they are reverse-
engineered from actual published communications.

### 9.1 · Real examples to match (use these as few-shot examples in prompts)

**Investigating — IES disruption (March 16, 2026):**
> Starting around 22:23 UTC on March 16, 2026, Abnormal began experiencing a
> service disruption impacting Inbound Email Security detection and
> remediation for some US customers. Additionally, inline email processing is
> affected during this time, and malicious emails may not be properly detected
> or remediated. Abnormal's engineering team is actively investigating and
> working to restore full functionality. The next update will be provided
> within 1 hour or when further information is obtained.

**Resolved — IES disruption (March 16, 2026):**
> Starting around 22:23 UTC on March 16, 2026, Abnormal experienced a service
> disruption impacting Inbound Email Security detection and remediation for
> some US customers. During this time, inline email processing was also
> affected, and some emails may not have been properly detected or remediated.
> Abnormal's engineering team actively worked to address the issue, and all
> services were fully restored as of 23:56 UTC. Detection and remediation are
> now operating as expected for US customers. If you experience any further
> issues, please reach out to Abnormal's support team at
> support@abnormalsecurity.com.

**Identified — Threat Log delays (March 12, 2026):**
> Starting at 18:00 UTC on March 12, 2026, Abnormal identified an issue where
> messages flagged as attack, spam, or borderline may experience delays in
> appearing within the Threat Log for Gov customers. Inbound Email Security
> detection and remediation remain fully functional, and all threats continue
> to be identified and acted upon as expected. The impact is limited to a
> delay in Threat Log visibility within the Portal.

**Resolved — Threat Log delays (March 12, 2026):**
> Between 18:00 UTC and 20:40 UTC on March 12, 2026, Abnormal identified an
> issue where messages flagged as attack, spam, or borderline experienced
> delays in appearing within the Threat Log for Gov customers. Inbound Email
> Security detection and remediation remained fully functional throughout the
> incident, and all threats continued to be identified and acted upon as
> expected. Abnormal engineers redeployed the affected services and confirmed
> recovery as of 20:40 UTC. All messages during the incident window were
> queued and have been processed. If you experience any further issues, please
> reach out to Abnormal support at support@abnormalsecurity.com.

**Investigating — Portal access (March 16, 2026):**
> Starting around 14:26 UTC, Abnormal began experiencing an issue with the EU
> Portal being inaccessible and displaying an error. EU customers may be
> unable to access the Abnormal Portal during this time. Email detection and
> remediation services remain fully operational and are not impacted. The
> engineering team is actively working to restore access to the EU Portal.

**Investigating — Portal slowness (Jan 13, 2026):**
> Starting around 15:35 UTC, Abnormal began experiencing issues with the
> Abnormal Portal which is causing slowness and failures when trying to load
> and navigate the portal for US customers. Email remediation and detection
> services remain fully operational during this time. Abnormal's engineering
> team is actively investigating this issue and working toward a resolution.
> Updates will be provided as more information becomes available.

### 9.2 · Sentence structure templates

These are the patterns extracted from real posts. The comm_generator prompt
should include these verbatim as templates.

**Investigating template:**
```
Starting around [HH:MM] UTC on [Day, Month DD, YYYY], Abnormal began
experiencing [a service disruption impacting / an issue with] [Affected
Service] [specific impact description] for [scope]. [One sentence: what
customers cannot do or what risk they face.] [Optional: clarify what IS
still working.] Abnormal's engineering team is actively investigating and
working to [restore full functionality / resolve the issue]. [Next update
sentence OR "Updates will be provided as more information becomes available."]
```

**Identified template:**
```
Starting [around/at] [HH:MM] UTC on [Day, Month DD, YYYY], Abnormal
identified [an issue where / a problem with] [specific description] for
[scope]. [What remains functional.] [Impact scope sentence.]
```

**Monitoring template:**
```
[Service description] [has/have] recovered and [is/are] currently
processing normally. Abnormal's engineering team is [continuing to monitor /
actively working through the backlog]. [Next steps.]
```

**Resolved template:**
```
[Starting around / Between] [HH:MM] UTC [and HH:MM UTC] on [Day, Month DD,
YYYY], Abnormal experienced [description]. During this time, [what was
affected]. Abnormal's engineering team actively worked to address the issue,
and all services were fully restored as of [HH:MM] UTC. [Current state.]
If you experience any further issues, please reach out to Abnormal's support
team at support@abnormalsecurity.com.
```

### 9.3 · Style rules checklist

Encode these in the quality_checker prompt. Each becomes a checklist item.

| # | Rule | ✓ Example | ✗ Example |
|---|---|---|---|
| 1 | Use "Abnormal" not "we/our" | "Abnormal's engineering team" | "our engineering team" |
| 2 | Qualify scope | "some US customers" | "all customers" / "customers" |
| 3 | "Starting around" for start time | "Starting around 22:23 UTC" | "At 22:23 UTC" |
| 4 | All times in UTC | "22:23 UTC" | "3:23 PM PT" |
| 5 | Use exact product registry names | "Inbound Email Security detection" | "email service" |
| 6 | State customer risk plainly | "malicious emails may not be properly detected" | "there may be issues" |
| 7 | No internal team names | — | "the IES pod", "on-call SRE" |
| 8 | No root cause in investigating | — | "due to a misconfigured deploy" |
| 9 | No SLA language | — | "within our 99.9% SLA" |
| 10 | Support email in resolved ONLY | in resolved msg | in investigating msg |
| 11 | Clarify what IS working | "detection and remediation remain fully functional" | (omitted) |
| 12 | Past tense in resolved, present in investigating | "was affected" vs "is affected" | mixing tenses |
| 13 | No hedging language | "may not be properly detected" | "we think there might be" |
| 14 | Single paragraph per status | compact block | multiple paragraphs with headers |

### 9.4 · Product name registry

Use these EXACT strings — never abbreviate, never invent.

```
Inbound Email Security (IES)
Email Productivity (EPR)
Account Takeover Service (ATO)
AI Security Mailbox (AISM)
AI Phishing Coach (AIPC)
Misdirected Email Prevention
Platform
Portal Application
SIEM API
SOAR API
Customer Support Portal
Abnormal Gov
```

If an incident involves something not in this list, use "Abnormal Platform"
and flag it in `GapReport.internal_terms_detected`.

---

## 10 · Data Preprocessing Rules

This is the second-highest-leverage area. Good preprocessing = good extraction.
Bad preprocessing = the model hallucinates or misses facts.

### 10.1 · Slack thread preprocessing

**Input:** Raw Slack JSON export (messages array with timestamps, users, text, reactions, thread replies)

**Target output format:**
```
14:23 @alice: The IES pipeline is throwing 500s in prod
14:25 @bob: Confirmed, deployment went out at 14:15
14:31 @alice: Rolling back now
14:40 @bob: Rollback complete, monitoring
```

**Strip (these waste tokens and confuse extraction):**
- Bot messages (subtype: "bot_message")
- Reactions / emoji-only messages
- Thread metadata (join/leave events)
- Channel topic changes
- Duplicate alert messages (keep first occurrence only)
- File upload notifications
- Slack formatting markup (convert `<@U123>` → `@username` if mapping available, else `@user`)

**Preserve:**
- Timestamps → convert epoch to HH:MM UTC
- @username (anonymize to @user1, @user2 etc. if needed)
- Full message body text
- Thread reply structure (indent or annotate)

**Implementation pattern:**
```python
def clean_slack_thread(messages: list[dict]) -> str:
    lines = []
    seen_alerts = set()
    for msg in sorted(messages, key=lambda m: float(m.get("ts", 0))):
        if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
            continue
        text = msg.get("text", "").strip()
        if not text or len(text) < 3:  # emoji-only
            continue
        if text in seen_alerts:  # dedup alerts
            continue
        seen_alerts.add(text)
        ts = datetime.utcfromtimestamp(float(msg["ts"])).strftime("%H:%M")
        user = msg.get("user", "unknown")
        lines.append(f"{ts} @{user}: {text}")
    return "\n".join(lines)
```

### 10.2 · Log preprocessing

**Do NOT pass raw log blobs to the LLM.** Raw logs can be thousands of lines
and will blow the token budget while adding noise.

**Extract and format:**
- First occurrence of each unique error type
- Error counts per 5-minute window
- Lines containing: ERROR, FATAL, timeout, 5xx, deploy, rollback, restart
- Deployment-related lines (version changes, config changes)

**Target format:**
```
14:15 [DEPLOY] service=ies version=a1b2c3d → e4f5g6h deployer=platform-eng
14:17 [ERROR] service=ies message=pipeline_failure count=47 (14:15-14:20)
14:22 [ERROR] service=ies message=connection_timeout count=12 (14:20-14:25)
14:31 [INFO] service=ies message=rollback_initiated version=e4f5g6h → a1b2c3d
```

### 10.3 · Deployment event preprocessing

**Extract per event:**
- Time (UTC)
- Service name (map to product registry if possible)
- Change description (deploy, rollback, config change, scale event)
- Commit hash (first 7 chars)

**Return as list of dicts matching `ProcessedData["deployment_events"]`:**
```python
[
    {"time": "14:15 UTC", "service": "ies", "change": "deploy a1b2c3d→e4f5g6h"},
    {"time": "14:31 UTC", "service": "ies", "change": "rollback e4f5g6h→a1b2c3d"}
]
```

### 10.4 · Metrics preprocessing

Summarize anomalous metrics into a brief narrative. The model does not need
raw metric values — it needs: what metric, when it spiked/dropped, by how much
relative to baseline.

**Target format:**
```
IES pipeline error rate spiked from 0.1% to 23% at 14:17 UTC.
P99 latency increased from 200ms to 4500ms between 14:15-14:35 UTC.
Error rate returned to baseline (0.2%) by 14:45 UTC.
```

### 10.5 · Building the raw_timeline

After preprocessing each source, merge all events into a single chronological
timeline. This is `ProcessedData["raw_timeline"]` and is the backbone the
extractor uses.

```python
[
    {"time": "14:15", "event": "Deploy e4f5g6h to IES", "source": "deploy_log"},
    {"time": "14:17", "event": "Error spike: pipeline_failure x47", "source": "logs"},
    {"time": "14:23", "event": "@alice: IES throwing 500s in prod", "source": "slack"},
    {"time": "14:25", "event": "@bob: deployment went out at 14:15", "source": "slack"},
    {"time": "14:31", "event": "Rollback initiated", "source": "logs"},
    {"time": "14:31", "event": "@alice: Rolling back now", "source": "slack"},
]
```

---

## 11 · What the AI Generates vs What App Logic Does

**AI generates (structured JSON):**
- Extracted facts with confidence ratings
- Gap list and placeholder suggestions
- All four communication drafts
- Quality checklist (pass/fail + note per item)
- Flagged internal phrases
- Suggested revisions

**App logic does (keep minimal):**
- Load and route raw source files
- Preprocess data (Section 10)
- Call pipeline stages in order
- Render structured output
- Show/hide draft types based on `current_status`

**NEVER implement as app logic:** gap detection, style checking, scope
qualification, placeholder insertion, internal term filtering. These MUST
come from the AI response. The codebase stays thin; quality lives in prompts.

---

## 12 · Streamlit Layout Spec

The UI tells a story: messy data goes in → structured extraction comes out →
gaps are flagged → polished communication appears. Keep it simple.

```
┌─────────────────────────────────────────────┐
│  Abnormal Incident Communications AI        │
│  [sidebar: file upload or sample selector]   │
├─────────────────────────────────────────────┤
│                                             │
│  ── Step 1: Raw Data ──                     │
│  [expandable: show preprocessed timeline]   │
│                                             │
│  ── Step 2: Extracted Facts ──              │
│  [table: field | value | confidence]        │
│                                             │
│  ── Step 3: Data Gaps ──                    │
│  [warning boxes for missing/low-confidence] │
│  [internal terms flagged]                   │
│                                             │
│  ── Step 4: Generated Communications ──     │
│  [tabs: Investigating|Identified|           │
│         Monitoring|Resolved]                │
│  [each tab shows the draft text]            │
│                                             │
│  ── Step 5: Quality Report ──               │
│  [score badge: 85/100]                      │
│  [checklist with ✓/✗ per item]              │
│  [flagged phrases highlighted]              │
│  [suggested revision if score < 80]         │
│                                             │
└─────────────────────────────────────────────┘
```

**Streamlit components to use:**
- `st.sidebar` for data source selection
- `st.expander` for raw/preprocessed data (collapsed by default)
- `st.tabs` for communication drafts
- `st.metric` for quality score
- `st.warning` / `st.error` for gaps
- `st.success` for passed checklist items
- `st.spinner` during Claude calls

**Do NOT use:** custom CSS, JavaScript, external component libraries,
st.components.v1.html. Stick to native Streamlit.

---

## 13 · Error Handling & Robustness

### 13.1 · JSON parsing failures

The most common failure mode. Handle it in `utils/llm.py`:

```python
def call_claude_safe(system_prompt, user_content, max_tokens, temperature=0.2):
    """Call Claude with retry on JSON parse failure."""
    for attempt in range(2):
        try:
            return call_claude(system_prompt, user_content, max_tokens, temperature)
        except json.JSONDecodeError as e:
            if attempt == 0:
                # Retry with stronger JSON instruction appended
                user_content += "\n\nCRITICAL: Your previous response was not valid JSON. Respond with ONLY a JSON object. No markdown fences. No explanation."
                continue
            raise ValueError(f"Claude returned invalid JSON after 2 attempts: {e}")
```

### 13.2 · Missing data sources

Not every incident will have all four data types. The preprocessor must handle
any combination gracefully:

```python
def preprocess(raw_sources: dict) -> ProcessedData:
    return ProcessedData(
        slack_thread=clean_slack(raw_sources.get("slack")) if raw_sources.get("slack") else "No Slack data available.",
        log_summary=clean_logs(raw_sources.get("logs")) if raw_sources.get("logs") else "No log data available.",
        deployment_events=clean_deploys(raw_sources.get("deploys")) if raw_sources.get("deploys") else [],
        metrics_summary=clean_metrics(raw_sources.get("metrics")) if raw_sources.get("metrics") else "No metrics data available.",
        raw_timeline=build_timeline(...)  # merge whatever sources exist
    )
```

### 13.3 · Claude returns extra fields or missing fields

Always validate against TypedDict keys:

```python
def validate_shape(data: dict, expected_keys: set) -> dict:
    """Ensure returned dict has exactly the expected keys."""
    for key in expected_keys:
        if key not in data:
            data[key] = None  # safe default
    # Strip unexpected keys
    return {k: v for k, v in data.items() if k in expected_keys}
```

### 13.4 · API rate limits / timeouts

Wrap API calls with a simple retry. Do not add exponential backoff complexity
for a prototype — a single retry with a 2-second sleep is sufficient.

---

## 14 · Adapting to Data Format Changes

The data in the Dropbox folder may not perfectly match the preprocessing
expectations above. When you encounter the actual data files:

1. **Inspect first.** Open each file, understand its structure.
2. **Adapt the preprocessor.** The preprocessor is the adapter layer — it
   should handle whatever format the data is actually in.
3. **Don't change the TypedDict contracts.** ProcessedData is the stable
   interface between preprocessing and extraction. Map any data format INTO
   ProcessedData, never change ProcessedData to match a data format.
4. **Log what you stripped.** If preprocessing removes >50% of input tokens,
   that's working correctly for noisy Slack data.

---

## 15 · Swapping & Iteration

The architecture is designed for rapid prompt iteration without code changes.

**To swap a prompt:**
1. Copy current `prompts/xxx.txt` → `prompts/xxx_vN.txt`
2. Edit `prompts/xxx.txt`
3. Re-run — only that stage's output changes

**To swap a stage implementation:**
1. Function signature must stay identical
2. Return TypedDict must stay identical
3. Internal logic (chain-of-thought, few-shot, temperature) is free to change

**To add a new pipeline stage:**
1. Define TypedDict in `utils/types.py`
2. Create `pipeline/new_stage.py` with one exported function
3. Wire into `app.py`
4. Update this file's pipeline diagram

**To test a stage in isolation:**
Each stage is importable and callable with a fixture dict — no Streamlit needed.

---

## 16 · Bonus Features (If Time Allows)

These are ordered by demo impact. Only attempt after the core pipeline works
end-to-end with good output quality.

1. **Side-by-side comparison** — Show generated draft next to a real Abnormal
   status page post for the same incident type
2. **Tone selector** — Dropdown: "standard" / "urgent" / "reassuring" that
   adjusts the comm_generator prompt
3. **Executive brief** — Additional Claude call that produces a 3-sentence
   internal summary for leadership
4. **Export** — Download generated communications as plain text or markdown
5. **Multiple incident support** — Let user select from multiple sample incidents

---

## 17 · Working Rules

Follow these at all times. They prevent the most common mistakes.

### Do:
- Show diffs/code, then a one-line summary. No preamble.
- Run the app after every significant change to verify it works.
- Read a file before editing it. Read the current state, don't assume.
- When a prompt isn't producing good output, edit the prompt file FIRST.
  Only change Python logic if the prompt approach can't fix it.
- Keep all Claude calls going through `utils/llm.py`.
- Use `st.spinner` during every Claude call so the user sees progress.

### Don't:
- Don't run `pip install` unless `requirements.txt` changed.
- Don't launch Streamlit unless asked.
- Don't add files or TypedDict fields beyond what a task requires.
- Don't put business logic in `app.py`.
- Don't use `print()` for debugging — use `st.write()` or `logging`.
- Don't raise max_tokens to fix truncated output — fix the prompt or input size.
- Don't add try/except that silently swallows errors — always log or display.

### If confused:
- State your interpretation and proceed.
- Ask only if two interpretations would produce meaningfully different architecture.
- When a task spans multiple files, edit one file completely before moving to the next.

---

## 18 · Evaluation Criteria Mapping

The take-home is evaluated on these criteria. Map effort to match.

| Criterion | Where it lives | Priority |
|---|---|---|
| AI integration quality | Prompts, preprocessing, structured output | **Highest** |
| Output reads like real Abnormal posts | `generate_comms.txt` + style guide (§9) | **Highest** |
| Surfaces uncertainty honestly | `detect_gaps.txt` + GapReport rendering | **High** |
| Technical execution | Pipeline interfaces, type safety, error handling | High |
| Product strategy | PRD document (separate from code) | Medium |
| Appropriate scoping | Thin app.py, modular pipeline | Medium |

**The demo story:** Show raw messy data → structured extraction → gap flags →
final communication that reads like status.abnormalsecurity.com. That arc is
the prototype's argument.

---

## 19 · Quick Reference: Model Call Summary

| Stage | Prompt file | System role | max_tokens | Temp |
|---|---|---|---|---|
| extractor | `prompts/extract_facts.txt` | Incident analyst | 800 | 0.2 |
| gap_detector | `prompts/detect_gaps.txt` | Data quality auditor | 500 | 0.2 |
| comm_generator | `prompts/generate_comms.txt` | Status page writer | 1200 | 0.4 |
| quality_checker | `prompts/quality_check.txt` | Communications editor | 600 | 0.2 |
