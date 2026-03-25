# AI-Native Incident Communications Pipeline

## Solution
Three-stage AI pipeline that processes raw technical data and automates customer communications:

```
Raw Technical Data → AI Analysis → Customer Communications
```

## Architecture

### Stage 1: Multi-Source Data Processing
- **Dynamic File Detection**: Automatically categorizes incident data regardless of naming conventions
- **Data Sources**: PagerDuty incidents, CloudWatch logs, Prometheus metrics, GitHub deployments, Slack threads
- **Timeline Correlation**: Aligns timestamps across all sources to build complete incident timeline
- **Signal Synthesis**: Combines technical signals to derive customer impact (not pre-computed in data)

### Stage 2: AI-Powered Analysis
- **Customer Impact Derivation**: Analyzes technical signals to determine affected functionality and severity
- **Root Cause Identification**: Distinguishes confirmed vs. hypothesized causes with source attribution
- **Impact Assessment**: Classifies severity (degraded performance vs. outage) and scope
- **Confidence Scoring**: Provides risk assessment for automated decisions

### Stage 3: Communication Generation
- **Status Page Formatting**: Generates investigating → identified → monitoring → resolved updates
- **Technical Translation**: Converts "database connection pool exhausted" to "API performance degradation"
- **Internal Detail Filtering**: Excludes engineer names, internal infrastructure, technical metrics
- **Brand Compliance**: Ensures professional, empathetic tone matching Abnormal's standards

## Key Features

### Intelligent Signal Processing
- Cross-references deployment times, metric anomalies, and alert patterns
- Handles missing data fields gracefully
- Converts UTC timestamps to Pacific Time for customer presentation
- Identifies affected vs. unaffected functionality from technical signals

### Customer-Focused Communications
- Professional tone without technical jargon
- Clear incident scope and customer impact
- Proper timeline and next-update expectations
- Follows status page structure (title, status, message, summary)

### Quality Assurance
- Validates message structure and content
- Ensures consistent brand voice across incidents
- Provides audit trail for compliance
- Supports human-in-the-loop review

## Architecture & Technical Design

### System Architecture
Modular, file-based architecture with clear separation between data processing, analysis, and communication generation:

```
Data Files → Pipeline Scripts → Structured Outputs
     ↓              ↓              ↓
Raw Incident → Python Scripts → JSON/CSV Files
```

### File Organization
```
incident_response/
├── pipeline_v2.py              # Main analysis pipeline
├── generate_comms.py           # Communication generation
├── data/                       # Original incident data
├── test_data_*/                # Additional test scenarios
├── output/                     # Analysis results (JSON + CSV)
├── communications/             # Generated customer messages
└── iterative_prompts/          # Development specifications
```

### Technical Design Decisions

#### File-Based Data Processing
- **Input**: Raw incident data files in JSON/text format
- **Processing**: Python scripts read and categorize files dynamically
- **Output**: Structured JSON for analysis, JSON for communications, CSV for consolidated data

#### Dynamic File Detection
- **Approach**: Content-based file categorization rather than filename patterns
- **Benefit**: Handles varying naming conventions and file organization
- **Implementation**: Pattern matching on file content (PagerDuty fields, CloudWatch structure, etc.)

#### Separation of Concerns
- **pipeline_v2.py**: Handles data ingestion, AI analysis, and validation
- **generate_comms.py**: Focuses solely on communication generation
- **Integration**: Automatic triggering via subprocess calls

#### Configuration Management
- **Environment Variables**: API keys loaded via .env files
- **Flexible Paths**: Command-line arguments for custom data folders
- **Output Organization**: Timestamped and categorized file naming

#### Data Flow Architecture
1. **Ingestion**: Dynamic file detection and categorization
2. **Processing**: Timeline correlation and signal synthesis
3. **Analysis**: AI-powered incident analysis with confidence scoring
4. **Generation**: Customer communication creation with validation
5. **Output**: Structured files for different downstream consumers

#### Error Handling & Validation
- **Graceful Degradation**: Missing files handled with warnings
- **Input Validation**: JSON schema validation for structured data
- **Output Validation**: Communication quality checks and compliance validation
- **Audit Trail**: Source attribution and confidence tracking

#### Scalability Design
- **Modular Scripts**: Each component can be run independently
- **Batch Processing**: Multiple incidents processed in single run
- **Flexible Output**: Supports different output formats for various use cases
- **Extensible**: New data sources can be added without core changes

## Key Decisions Made

### AI-First Approach
Used Claude AI for both incident analysis and communication generation to handle diverse incident types without rigid rule-based systems.

### Modular Pipeline Architecture
Separated data processing, analysis, and communication generation into distinct stages for independent testing and maintenance.

### Source Attribution & Confidence Scoring
Implemented traceability for enterprise requirements with confidence levels to prioritize incidents needing human review.

### Human-in-the-Loop Design
Maintained oversight capability for critical incidents while automating routine communications.


