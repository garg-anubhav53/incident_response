# Streamlit Incident Communications Generator

## Overview

This Streamlit app provides a web interface for the AI-powered incident communications pipeline. It allows users to upload raw incident data files and generates professional status page communications that match Abnormal Security's style.

## Features

- **File Upload**: Upload incident data files (JSON/TXT) via drag-and-drop
- **AI Analysis**: Extract structured incident facts using Claude AI
- **Communication Generation**: Generate customer-facing status page updates
- **Status Page Display**: View results in Abnormal-style status page format
- **Structured Analysis**: Expandable section showing detailed incident analysis

## Usage

### Prerequisites

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env to add your ANTHROPIC_API_KEY
```

### Running the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

### Using the Interface

1. **Upload Files**: In the sidebar, upload incident data files:
   - `incident_context.txt` - Slack threads and notes
   - `cloudwatch_logs.json` - Application logs
   - `prometheus_metrics.json` - System metrics
   - `pagerduty_incident.json` - Alert data
   - `github_deployments.json` - Deployment history

2. **Analyze**: Click "🔍 Analyze Incident" to run the pipeline

3. **View Results**: See generated status page communications and detailed analysis

## File Support

The app accepts any combination of the 5 supported file types. Not all files are required - the pipeline works with whatever data is provided and identifies gaps in the analysis.

## Output

- **Status Page View**: Professional communications matching Abnormal's style
- **Structured Analysis**: Detailed incident facts, timeline, confidence scores
- **Data Gaps**: Identified missing information and uncertainties

## Technical Details

- **Pipeline**: Two-stage AI process (extraction → generation)
- **Model**: Claude Sonnet 4.5
- **Styling**: Matches Abnormal's actual status page design
- **Error Handling**: Graceful handling of missing files and API errors

## Architecture

- `app.py` - Main Streamlit application
- Reuses existing system prompts from `pipeline_v2.py` and `generate_comms.py`
- Session state management for result persistence
- Responsive design for mobile and desktop

## Testing

Run the test script to verify functionality:

```bash
python test_app.py
```

This tests the core pipeline functions without the Streamlit UI.
