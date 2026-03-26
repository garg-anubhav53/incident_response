# Comprehensive Logging Guide

This document details all logging added to `app.py` to help diagnose issues where the app shows a loading state then returns to the homepage.

## 🎯 **Purpose**
To provide complete visibility into every step of the application flow, from startup through processing to results rendering.

## 📍 **Log Output Locations**
1. **Console**: Visible when running `streamlit run app.py`
2. **File**: `app_debug.log` in the current directory (automatically created)

## 🔧 **Logging Configuration**
```python
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
```

## 📋 **Complete Logging Coverage**

### **1. Application Startup**
**Location**: Lines 23-26
- App startup detection
- Python version
- Streamlit version  
- Current working directory
- API key presence check

### **2. Session State Management**
**Location**: Lines 910-920 (main function)
- Session state initialization for all variables
- Current values tracking
- Step transitions

### **3. File Processing**
**Location**: Lines 1055-1070 (load_sample_data)
- Sample data directory existence check
- File counting and naming
- Content loading success/failure

**Location**: Lines 991-994 (main function)
- File upload detection
- File content storage in session state
- Uploaded file tracking

### **4. File Type Detection**
**Location**: Lines 387-421 (detect_file_type)
- Input filename and content logging
- Detection logic for each file type
- Final detected type

### **5. Data Processing Functions**

#### **Prometheus Processing**
**Location**: Lines 424-462 (_parse_prometheus)
- Input data structure analysis
- Format detection (metrics vs query API)
- Individual metric processing
- Error handling

**Location**: Lines 465-473 (_is_anomalous)
- Anomaly detection calculations
- Baseline comparisons

**Location**: Lines 476-518 (summarize_metrics)
- JSON parsing attempts
- Metric summarization
- Anomaly counting

### **6. Message Building**
**Location**: Lines 521-558 (build_user_message)
- Input files tracking
- Section building for each file type
- Deployment flag integration
- Final message construction

### **7. Deployment Correlation**
**Location**: Lines 562-571 (correlate_deployments)
- Input file detection
- Onset time calculation from PagerDuty
- Prometheus anomaly detection
- Deployment window analysis
- Individual deployment flagging
- Relevance scoring

### **8. LLM Pipeline Functions**

#### **JSON Parsing**
**Location**: Lines 309-338 (parse_llm_json)
- Input text analysis
- Markdown fence removal
- JSON parsing attempts
- Error details on failure

#### **Claude API Calls**
**Location**: Lines 341-383 (call_claude)
- API request parameters
- Attempt tracking (2 attempts max)
- Response reception logging
- JSON parsing results
- Error type and details

#### **Pipeline Execution**
**Location**: Lines 575-594 (run_extraction)
- File type detection logging
- Message building tracking
- API call execution

**Location**: Lines 597-606 (run_generation)
- Input validation
- Generation execution

### **9. Persistence Functions**

#### **Inference Log Saving**
**Location**: Lines 610-630 (save_inference_log)
- Directory creation
- File naming with timestamp
- Content structure validation
- File write success/failure

#### **Inference Log Loading**
**Location**: Lines 633-648 (load_inference_logs)
- Directory existence check
- File sorting by date
- Individual file loading
- Error handling per file

### **10. Validation Functions**
**Location**: Lines 652-705 (validate_communications)
- Input structure validation
- Communication counting
- Field validation for each stage
- Warning generation
- Missing field tracking

### **11. UI Rendering Functions**

#### **Status Page**
**Location**: Lines 816-867 (render_status_page)
- Input validation
- Severity assessment
- Communication rendering
- HTML construction
- Error handling

#### **Structured Analysis**
**Location**: Lines 870-912 (render_structured_analysis)
- Data extraction logging
- Timeline processing
- Confidence score rendering
- Data gap tracking

#### **Pattern Analysis**
**Location**: Lines 915-976 (render_pattern_analysis)
- Pattern data validation
- Inference log processing
- Historical data loading
- Individual entry rendering

#### **Validation Display**
**Location**: Lines 979-1011 (render_validation)
- Warning categorization
- High/medium severity handling
- Expander state management

#### **Deployment Alerts**
**Location**: Lines 1014-1051 (render_deployment_alerts)
- Flag categorization
- Alert rendering
- Expander management

### **12. Main Application Flow**

#### **Step Management**
**Location**: Lines 901-1003 (main function - upload step)
- Progress tracking
- User interaction logging
- File upload handling
- Button click tracking

**Location**: Lines 1006-1068 (main function - processing step)
- File content validation
- Progress bar updates
- Pipeline step execution
- Error handling and recovery

**Location**: Lines 1071-1107 (main function - results step)
- Result validation
- Rendering coordination
- Reset functionality

## 🚨 **Critical Failure Points Logged**

### **Session State Issues**
- Missing session state variables
- Incorrect step transitions
- File content loss between steps

### **API Failures**
- API key missing/invalid
- Network connectivity issues
- JSON parsing failures
- Rate limiting

### **File Processing**
- Invalid file formats
- Corrupted JSON data
- Missing required fields
- Encoding issues

### **Pipeline Failures**
- Extraction failures
- Generation failures
- Validation failures
- Rendering errors

### **UI Issues**
- Component rendering failures
- State management errors
- User interaction failures

## 🔍 **Debugging Workflow**

1. **Start the app**: `streamlit run app.py`
2. **Watch console output** for real-time logging
3. **Check `app_debug.log`** for detailed trace
4. **Look for "FAILED"** markers in logs
5. **Follow the sequence** from startup to failure point

## 📊 **Log Levels Used**

- **INFO**: Normal flow, state changes, successful operations
- **DEBUG**: Detailed processing, variable values, intermediate steps
- **WARNING**: Non-critical issues, missing optional data
- **ERROR**: Failures, exceptions, critical issues

## 🔄 **Log Patterns**

Each function follows this pattern:
```
=== FUNCTION_NAME STARTED ===
[Detailed logging of inputs and processing]
=== FUNCTION_NAME COMPLETED ===
```

Or on failure:
```
=== FUNCTION_NAME FAILED ===
```

## 🛠 **How to Revert Logging**

If needed to remove logging:

1. **Remove logging imports** (lines 8-20)
2. **Remove logger calls** from each function
3. **Restore original function signatures**
4. **Remove exception handling** added for logging

Each logging addition is clearly marked and can be independently removed without affecting core functionality.

## 📝 **Example Log Output**

```
2024-03-26 09:50:00,123 - INFO - main:901 - === MAIN FUNCTION STARTED ===
2024-03-26 09:50:00,124 - INFO - main:910 - Initializing session state...
2024-03-26 09:50:00,125 - INFO - main:917 - Initialized session state step = upload
2024-03-26 09:50:00,126 - INFO - main:940 - Current step: upload (index 0)
2024-03-26 09:50:00,127 - INFO - main:952 - === STEP 1: UPLOAD ===
2024-03-26 09:50:05,000 - INFO - main:974 - User clicked 'Load Sample Data'
2024-03-26 09:50:05,001 - INFO - load_sample_data:1056 - === Loading Sample Data ===
2024-03-26 09:50:05,002 - INFO - load_sample_data:1062 - Loaded 5 sample files: [...]
2024-03-26 09:50:05,003 - INFO - main:1001 - User clicked 'Analyze Incident' - moving to processing step
2024-03-26 09:50:05,004 - INFO - main:1007 - === STEP 2: PROCESSING ===
2024-03-26 09:50:05,005 - INFO - correlate_deployments:563 - === Deployment Correlation Started ===
...
```

This comprehensive logging ensures you can exactly identify where and why the app fails during execution.
