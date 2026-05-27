# CSV Export Feature Documentation

## Overview
The RTM Automation Engine now supports CSV export functionality for various reports. This allows you to download comprehensive reports in CSV format for further analysis, sharing, or archival purposes.

## Available CSV Export Endpoints

### 1. Coverage Report Export
**Endpoint:** `GET /api/report/export/coverage`

**Description:** Exports a detailed coverage report showing all requirements with their coverage status and mapped test cases.

**CSV Columns:**
- Requirement ID
- Requirement Title
- Requirement Description
- Coverage Status (Covered/Uncovered)
- Test Case Count
- Mapped Test Cases (semicolon-separated)

**Example:**
```bash
curl http://localhost:8000/api/report/export/coverage -o coverage_report.csv
```

### 2. Risk Analysis Report Export
**Endpoint:** `GET /api/report/export/risk?days_threshold=30`

**Description:** Exports a risk-focused report highlighting uncovered requirements (high risk) and covered requirements (low risk).

**Query Parameters:**
- `days_threshold` (optional, default: 30): Days to consider for recently changed items

**CSV Columns:**
- Requirement ID
- Requirement Title
- Requirement Description
- Risk Level (High/Low)
- Test Case Count

**Example:**
```bash
curl http://localhost:8000/api/report/export/risk?days_threshold=30 -o risk_report.csv
```

### 3. Traceability Matrix Export
**Endpoint:** `GET /api/report/export/traceability`

**Description:** Exports the complete traceability matrix showing all requirement-to-testcase mappings.

**CSV Columns:**
- Mapping ID
- Requirement ID
- Requirement Title
- Test Case ID
- Test Case Name
- Test Case Steps

**Example:**
```bash
curl http://localhost:8000/api/report/export/traceability -o traceability_matrix.csv
```

### 4. Summary Report Export
**Endpoint:** `GET /api/report/export/summary?days_threshold=30`

**Description:** Exports a summary report with key metrics, coverage statistics, and risk analysis.

**Query Parameters:**
- `days_threshold` (optional, default: 30): Days to consider for recently changed items

**CSV Sections:**
- Report metadata and timestamp
- Coverage metrics (total, covered, uncovered, percentage)
- Risk analysis (risk score, uncovered count)
- Top uncovered requirements (high risk items)

**Example:**
```bash
curl http://localhost:8000/api/report/export/summary?days_threshold=30 -o summary_report.csv
```

## Usage Examples

### Using Browser
Simply navigate to any of the endpoints in your browser:
```
http://localhost:8000/api/report/export/coverage
```
The CSV file will be automatically downloaded.

### Using Python
```python
import requests

# Export coverage report
response = requests.get('http://localhost:8000/api/report/export/coverage')
with open('coverage_report.csv', 'wb') as f:
    f.write(response.content)

# Export with parameters
response = requests.get(
    'http://localhost:8000/api/report/export/risk',
    params={'days_threshold': 60}
)
with open('risk_report.csv', 'wb') as f:
    f.write(response.content)
```

### Using PowerShell
```powershell
# Download coverage report
Invoke-WebRequest -Uri "http://localhost:8000/api/report/export/coverage" -OutFile "coverage_report.csv"

# Download risk report with parameters
Invoke-WebRequest -Uri "http://localhost:8000/api/report/export/risk?days_threshold=60" -OutFile "risk_report.csv"
```

## Testing

Run the test suite to verify CSV export functionality:

```bash
pytest tests/test_report.py -v
```

Test coverage includes:
- CSV structure validation
- Data accuracy verification
- Special character handling
- Empty database scenarios
- Edge cases

## Implementation Details

### Report Service
The CSV export functionality is implemented in `app/services/report_service.py`:

- `export_coverage_report_csv()`: Generates coverage report CSV
- `export_risk_report_csv()`: Generates risk analysis CSV
- `export_traceability_matrix_csv()`: Generates traceability matrix CSV
- `export_summary_report_csv()`: Generates summary report CSV

### API Routes
CSV export endpoints are defined in `app/routes/report_routes.py` using FastAPI's `StreamingResponse` for efficient file downloads.

## File Format

All CSV exports use:
- UTF-8 encoding
- Comma (`,`) as delimiter
- Double quotes (`"`) for field encapsulation
- Standard CSV escaping for special characters

## Error Handling

All CSV export endpoints include:
- Database error handling
- Logging of export operations
- Proper HTTP status codes
- Content-Disposition headers for automatic downloads

## Performance Considerations

For large datasets:
- Coverage and risk reports process all requirements
- Traceability matrix processes all mappings
- Consider database query optimization for very large datasets
- CSV generation uses in-memory buffers (StringIO)

## Future Enhancements

Potential improvements:
- Excel (XLSX) export support
- PDF report generation
- Custom column selection
- Date range filtering
- Scheduled report generation
- Email delivery of reports
