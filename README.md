# Incident Response

A pipeline for analyzing production incidents using AI to extract structured insights from multiple data sources.

## Quick Start

### 1. Set up Environment
```bash
# Copy the environment template
cp .env.example .env

# Add your Anthropic API key to .env file
echo "ANTHROPIC_API_KEY=your_api_key_here" >> .env

# Install dependencies
pip install python-dotenv anthropic
```

### 2. Run the First Prompt
```bash
# Navigate to the iterative prompts directory
cd iterative_prompts

# Implement the pipeline based on 1.base_case_incident_detection.md
# Create pipeline_v1.py following the specifications
```

### 3. Pipeline Implementation
The first prompt (`1.base_case_incident_detection.md`) specifies building a Python script `pipeline_v1.py` that:

- Reads 5 incident data files from the `data/` directory
- Sends all data to Anthropic's Claude API for structured analysis
- Validates the output against expected results

**Expected Files in `data/`:**
- `incident_context.txt` (Slack thread + engineer notes)
- `cloudwatch_logs.json` (application logs)
- `prometheus_metrics.json` (system metrics)
- `pagerduty_incident.json` (alert lifecycle)
- `github_deployments.json` (deployment history)

## Project Structure
```
incident_response/
├── data/                          # Incident data files
├── iterative_prompts/             # Prompt specifications
│   └── 1.base_case_incident_detection.md
├── .env.example                   # Environment template
├── .env                          # Your API keys (gitignored)
└── pipeline_v1.py                # Implementation to be created
```

## Next Steps
1. Implement `pipeline_v1.py` based on the specifications in `iterative_prompts/1.base_case_incident_detection.md`
2. Test the pipeline with the provided data files
3. Validate the output matches the expected results
