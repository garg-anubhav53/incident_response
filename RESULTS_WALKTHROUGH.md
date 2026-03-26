# Results Page Walkthrough: Incident Analysis Output

This document explains what information the incident analysis system exposes to users and why each component matters for incident response.

## Context: Sample Incident Analysis

The system analyzed an incident involving **API latency degradation** in the `api-gateway` service. The root cause was a deployment that changed HTTP client timeout from 10s to 30s, causing database connection pool exhaustion.

## What the System Extracts

### 1. **Incident Timeline & Impact**
- **What**: Precise timestamps for incident onset, detection, acknowledgment, mitigation, and resolution
- **Why**: Critical for understanding incident duration and response time metrics
- **Example**: Onset at 14:20 UTC (metrics show latency spike), detection at 14:23 UTC (PagerDuty alert), resolution at 16:45 UTC

### 2. **Root Cause Analysis**
- **What**: Specific deployment changes that triggered the incident, with causal mechanism
- **Why**: Enables targeted fixes and prevents recurrence
- **Example**: PR #12345 deployed at 14:15 UTC changed HTTP timeout from 10s to 30s, causing connections to be held 3x longer and exhausting the database connection pool

### 3. **Customer Impact Classification**
- **What**: Severity assessment (degraded_performance/partial_outage/full_outage) and affected functionality
- **Why**: Helps communicate actual customer experience vs internal metrics
- **Example**: "degraded_performance" - API worked but with high latency, most requests succeeded

### 4. **Security Function Impact**
- **What**: Whether email threat detection or automated remediation were impaired
- **Why**: Critical for security products to know if customer protection was compromised
- **Example**: "fully_operational" - detection and remediation systems continued working normally

### 5. **Evidence Trail**
- **What**: Raw data excerpts supporting each conclusion (log lines, metric values, Slack messages)
- **Why**: Enables verification and audit of AI reasoning
- **Example**: CloudWatch log: "Connection timeout to database after 30000ms, pool size 50/50"

## How Results Are Organized

### Zone 1: Pre-Flight Context
**Deployments Near Incident Onset**
- Shows GitHub deployments within 60 minutes before/after incident
- Flags HIGH relevance for same service as alert
- Example: HIGH relevance deployment to api-gateway at 14:15 UTC (5 minutes before onset)

### Zone 2: Status Page Draft
**AI-Generated Customer Communications**
- Chronological status updates (investigating → identified → monitoring → resolved)
- Each stage includes: technical summary, customer impact, next steps
- Word count validation for readability
- Example: "Investigating" stage explains latency issue, "Resolved" stage confirms rollback

### Zone 3: Quality Checks
**Automated Validation**
- Required field verification (customer impact, unaffected services)
- Consistency checks between incident pattern and security impact
- Example: Validates that "what's not affected" is explicitly stated for security products

### Zone 4: IC Verification
**Evidence-Based Claims Verification**
- 5 key questions with raw evidence citations
- Incident commander must verify each claim
- Example: "What caused it?" cites deployment timing and engineer confirmation

### Zone 5: Analyst View
**Pattern Classification & Inference Log**
- Incident pattern (deployment_induced, infrastructure_cascade, etc.)
- Chain of reasoning for each factual claim
- Example: "deployment_induced" pattern due to same-service deployment correlation

### Zone 6: Raw Extraction Data
**Complete Structured JSON**
- Full AI output for integration with other tools
- All extracted relationships and confidence scores
- Example: Complete timeline with all source citations

## Why This Information Matters

### For Incident Commanders
- **Rapid Assessment**: Timeline and impact classification enable quick severity determination
- **Root Cause**: Specific deployment identification prevents speculation and enables targeted fixes
- **Communication**: Pre-drafted status updates save time during high-pressure incidents

### For Security Operations
- **Protection Status**: Clear indication of whether threat detection was compromised
- **Customer Impact**: Distinguishes between internal issues vs customer exposure
- **Evidence Trail**: Audit trail for post-incident reviews and compliance

### For Engineering Teams
- **Prevention**: Deployment correlation identifies risky changes
- **Detection**: Anomaly patterns show what monitoring should alert on
- **Response**: Timeline metrics reveal process improvement opportunities

## Information Categories Exposed

### Temporal Data
- **Incident lifecycle timestamps** (onset, detection, resolution)
- **Deployment timing** relative to incident onset
- **Recovery duration** metrics

### Causal Data
- **Specific code changes** that triggered issues
- **Failure mechanisms** (how the change caused impact)
- **Rollback effectiveness** confirmation

### Impact Data
- **Customer experience classification** (degraded vs outage)
- **Security function status** (detection/remediation operational)
- **Service scope** (what was affected vs unaffected)

### Evidence Data
- **Raw log excerpts** with timestamps
- **Metric values** with baseline comparisons
- **Human communications** (Slack messages, engineer statements)

### Communication Data
- **Status update drafts** for each incident stage
- **Technical summaries** for internal teams
- **Customer-facing explanations** of impact

## How This Solves Problems

### Problem: Incident Information Overload
**Solution**: Structured extraction organizes scattered data (logs, metrics, chat) into coherent timeline and causality

### Problem: Unclear Customer Impact
**Solution**: Explicit classification of customer experience vs internal metrics, with security function status

### Problem: Slow Communication During Incidents
**Solution**: Pre-drafted status updates that are technically accurate and customer-appropriate

### Problem: Difficulty Identifying Root Cause
**Solution**: Deployment correlation and evidence linking reduces speculation and enables targeted fixes

### Problem: Lack of Audit Trail
**Solution**: Raw evidence citations for every claim enable verification and post-incident review

This structured approach transforms raw incident data into actionable intelligence that supports rapid decision-making, accurate communication, and effective prevention.
