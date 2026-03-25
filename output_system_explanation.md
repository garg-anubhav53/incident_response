# Pipeline v2 Output System Explanation

## Overview
Pipeline v2 generates two types of output files for each incident analysis: structured JSON files and a consolidated CSV file. This dual-output approach serves different downstream purposes while maintaining data integrity.

## Output Directory Structure
```
output/
├── data_analysis.json          # Original incident analysis
├── test_data_portal_analysis.json    # Portal auth failure test
├── test_data_thirdparty_analysis.json # Third-party dependency test
└── incidents.csv               # Consolidated data from all incidents
```

## Output Formats

### 1. Structured JSON Files
**Purpose**: Complete, rich incident analysis for detailed review and downstream processing

**Filename Pattern**: `{source_dir}_analysis.json`
- `data_analysis.json` for original incident
- `test_data_portal_analysis.json` for portal test
- `test_data_thirdparty_analysis.json` for third-party test

**Content**: Complete JSON response from Claude API with all fields:
```json
{
  "incident_summary": "One sentence summary",
  "affected_service": "Primary service",
  "affected_products": ["Product names"],
  "severity": "SEV-2",
  "timeline": {
    "cause_time_utc": "2025-01-15T14:15:00Z",
    "onset_time_utc": "2025-01-15T14:16:00Z",
    "detection_time_utc": "2025-01-15T14:20:00Z",
    "acknowledged_time_utc": "2025-01-15T14:25:00Z",
    "mitigation_time_utc": "2025-01-15T14:30:00Z",
    "recovery_time_utc": "2025-01-15T14:35:00Z",
    "resolved_time_utc": "2025-01-15T14:40:00Z"
  },
  "root_cause": {
    "summary": "Confirmed root cause",
    "status": "confirmed | hypothesized | unknown",
    "trigger": "Specific event or null",
    "mechanism": "How trigger caused impact"
  },
  "customer_impact": {
    "description": "Customer experience description",
    "severity_assessment": "degraded_performance | partial_outage | full_outage",
    "affected_functionality": ["List of affected features"],
    "unaffected_functionality": ["List of working features"]
  },
  "resolution": {
    "action_taken": "What fixed it",
    "confirmed_by": "Evidence of recovery"
  },
  "confidence_scores": {
    "root_cause": "high | medium | low",
    "scope": "high | medium | low", 
    "timeline": "high | medium | low",
    "customer_impact": "high | medium | low"
  },
  "source_attribution": {
    "root_cause": ["Source files supporting conclusion"],
    "timeline": ["Source files for timestamps"],
    "customer_impact": ["Source files for impact assessment"]
  },
  "data_gaps": ["Missing information"],
  "internal_details_to_exclude": ["Internal names to hide"]
}
```

### 2. Consolidated CSV File
**Purpose**: Flat, tabular format for easy data analysis, reporting, and integration with communication drafting tools

**Filename**: `incidents.csv`

**Design Principles**:
- **One row per incident**: All incidents consolidated into single file
- **Semicolon-joined lists**: Lists flattened to readable CSV cells
- **Consistent columns**: Same schema across all test cases
- **Append-only mode**: New runs add rows without overwriting

**CSV Columns**:
```csv
source_dir,incident_summary,affected_service,affected_products,severity,cause_time_utc,onset_time_utc,detection_time_utc,mitigation_time_utc,recovery_time_utc,resolved_time_utc,root_cause_summary,root_cause_status,root_cause_trigger,customer_impact_description,severity_assessment,affected_functionality,unaffected_functionality,resolution_action,resolution_confirmed_by,confidence_root_cause,confidence_scope,confidence_timeline,confidence_customer_impact,data_gaps,internal_details_to_exclude
```

**Sample Row**:
```csv
data,API gateway experienced HTTP client timeouts affecting customer requests,api-gateway,unknown,SEV-2,2025-01-15T14:15:00Z,2025-01-15T14:16:00Z,2025-01-15T14:20:00Z,2025-01-15T14:30:00Z,2025-01-15T14:35:00Z,2025-01-15T14:40:00Z,HTTP client timeout configuration change,confirmed,PR #12345,Customers experienced slow API responses with intermittent errors,degraded_performance,API endpoints; Authentication; Data processing,Email processing; Background jobs,Rolled back HTTP client timeout configuration,Metrics returned to baseline,high,medium,high,medium,regional scope; which product features; customer count,rds-prod-main; alice.engineer; bob.sre; john.dev
```

## List Handling in CSV

### Semicolon Joining Strategy
Lists are converted to readable CSV cells using semicolons as separators:

```python
def _join(value) -> str:
    """Flatten a list to a semicolon-joined string; pass scalars through."""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return "" if value is None else str(value)
```

**Examples**:
- `["API endpoints", "Authentication", "Data processing"]` → `"API endpoints; Authentication; Data processing"`
- `["rds-prod-main", "alice.engineer", "bob.sre"]` → `"rds-prod-main; alice.engineer; bob.sre"`
- `null` → `""` (empty string)

### Benefits of Semicolon Joining
1. **Readability**: Lists remain human-readable in spreadsheet applications
2. **Splitability**: Downstream tools can easily split on `; ` to recover original lists
3. **CSV Compatibility**: Avoids comma conflicts with CSV structure
4. **Consistency**: Uniform handling across all list fields

## File Management

### Output Directory Creation
```python
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
```

### CSV File Management
```python
# Clear previous CSV on each run for clean output
csv_path = OUTPUT_DIR / "incidents.csv"
if csv_path.exists():
    csv_path.unlink()

# Write header only if file doesn't exist
write_header = not csv_path.exists()
```

### JSON File Naming
```python
slug = source_dir.replace("/", "_").strip("_")
json_path = OUTPUT_DIR / f"{slug}_analysis.json"
```

**Naming Examples**:
- `data/` → `data_analysis.json`
- `test_data_portal/` → `test_data_portal_analysis.json`
- `test_data_thirdparty/` → `test_data_thirdparty_analysis.json`

## Downstream Usage

### Communication Drafter Integration
The CSV format is specifically designed for a "communication drafter" pipeline step that:
1. **Loads CSV rows**: Reads incident data in tabular format
2. **Generates customer communications**: Uses structured fields for templates
3. **References JSON for context**: Loads full JSON files when rich details needed

### Data Analysis Benefits
- **Cross-incident comparison**: All incidents in one table for easy analysis
- **Trend identification**: CSV format enables spreadsheet filtering and pivot tables
- **Metrics calculation**: Easy to compute statistics across multiple incidents

### Audit Trail
- **JSON preservation**: Complete analysis preserved for audit and review
- **CSV consolidation**: Quick overview of all processed incidents
- **Source tracking**: `source_dir` column maintains traceability

## Output Process Flow

1. **Pipeline Execution**: Each test case runs through analysis
2. **JSON Generation**: Complete analysis written to `{source}_analysis.json`
3. **CSV Append**: Key fields extracted and appended to `incidents.csv`
4. **Console Output**: File paths printed for user reference
5. **Summary Report**: Final output directory location displayed

## Error Handling
- **Directory creation**: `exist_ok=True` prevents errors on reruns
- **CSV header management**: Conditional header writing prevents duplicates
- **File path safety**: Slug generation ensures valid filenames
- **Encoding**: UTF-8 encoding ensures special characters preserved

This dual-output system provides both detailed analysis capabilities and streamlined data processing for downstream automation.
