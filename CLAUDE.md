# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

LabTrack is a lab testing and COA management system that replaces the legacy Excel-based workflow with a comprehensive web application. The system handles lab sample tracking, PDF parsing, test result management, approval workflows, and automated COA generation.

## Architecture

### Technology Stack
- **Backend**: Python 3.10+ with FastAPI, SQLAlchemy ORM, Pydantic settings
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Database**: SQLite (upgradeable to PostgreSQL)
- **AI Integration**: PydanticAI with Google Gemini (mock provider available)
- **PDF Processing**: PyPDF2, python-docx for generation
- **Authentication**: JWT-based with role-based access control

### Project Structure
```
labtrack/
├── backend/
│   ├── app/
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── services/    # Business logic layer
│   │   ├── api/         # FastAPI endpoints
│   │   ├── utils/       # Helper utilities
│   │   ├── database.py  # Database configuration
│   │   └── config.py    # Application settings
│   └── tests/           # Pytest test suite
├── frontend/            # React + Vite frontend
└── templates/           # Document templates
```

## Key Features

### 1. Sample Management
- Create lots with auto-generated reference numbers (YYMMDD-XXX)
- Support for standard lots, parent lots with sublots, and multi-SKU composites
- Product catalog with standardized naming

### 2. PDF Processing
- Drag-and-drop PDF upload
- AI-powered extraction (currently mock, ready for real AI)
- Manual review queue for low-confidence extractions
- Folder watching for automatic processing

### 3. Approval Workflow
- Three-stage approval: Draft → Reviewed → Approved
- Role-based permissions (Admin, QC Manager, Lab Tech, Read-Only)
- Bulk approval operations
- Complete audit trail

### 4. COA Generation
- Generate from approved test results
- Multiple template support
- Export as Word documents
- Batch generation capabilities

## Commands

### Running the Application
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8009

# Frontend
cd frontend
npm install
npm run dev

# Run backend tests
cd backend && python -m pytest tests/ -v

# Run frontend build
cd frontend && npm run build
```

### Default Login Credentials
- **Admin**: username: `admin`, password: `admin123`
- **QC Manager**: username: `qcmanager`, password: `qc123`
- **Lab Tech**: username: `labtech`, password: `lab123`

## Service Layer Pattern

All services inherit from `BaseService` and follow this pattern:
```python
# Services don't take database in constructor
service = ServiceName()

# Database session is passed as first parameter to methods
result = service.method_name(db, other_params...)
```

## Common Issues & Solutions

### Issue: Service method calls missing database parameter
**Solution**: Always pass `db` as the first parameter to service methods

### Issue: Excel export errors
**Solution**: Use BytesIO buffer:
```python
import io
buffer = io.BytesIO()
df.to_excel(buffer, index=False)
excel_data = buffer.getvalue()
```

### Issue: Status transition errors
**Solution**: Follow proper status transitions:
- TestResult: Draft → Reviewed → Approved
- Lot: Pending → Tested → Approved → Released

### Issue: Authentication not working
**Solution**: Ensure UserService is used for authentication, not hardcoded values

## UI Terminology

### Sample Tracker Page
The "Sample Tracker" page displays all submitted samples/lots with their workflow status.

**Status Labels (display text → backend enum):**
| Display Label | Backend Value | Description |
|---------------|---------------|-------------|
| Awaiting Results | `pending` | Sample submitted, no test results yet |
| Partial Results | `partial_results` | Some results received, more expected |
| Under QC Review | `under_review` | All results in, awaiting QC approval |
| Approved | `approved` | QC approved, ready for COA generation |
| Released | `released` | COA generated and published |
| Rejected | `rejected` | QC rejected, can be retried |

## Database Models

### Core Models
- **User**: Authentication and roles
- **Product**: Standardized product catalog
- **Lot**: Production lots with parent/sublot relationships
- **TestResult**: Lab test results with approval status
- **ParsingQueue**: PDF parsing queue and status
- **AuditLog**: Complete audit trail

### Enums
- **UserRole**: ADMIN, QC_MANAGER, LAB_TECH, READ_ONLY
- **LotType**: STANDARD, PARENT_LOT, SUBLOT, MULTI_SKU_COMPOSITE
- **LotStatus**: PENDING, TESTED, APPROVED, RELEASED, REJECTED
- **TestResultStatus**: DRAFT, REVIEWED, APPROVED

## Testing

Run tests with coverage:
```bash
pytest tests/ -v --cov=src --cov-report=html
```

## Development Guidelines

1. **Always use database transactions** - The base service handles this automatically
2. **Follow the service pattern** - Don't access models directly from UI
3. **Add audit trails** - Use BaseService for automatic audit logging
4. **Validate user permissions** - Check roles before sensitive operations
5. **Handle errors gracefully** - Show user-friendly messages in the UI

## Future Enhancements

1. **Real AI Integration**: Replace MockAIProvider with OpenAI/Anthropic
2. **Email Notifications**: Implement approval notifications
3. **Advanced Reporting**: Add trend analysis and KPI dashboards
4. **API Integration**: RESTful API for external systems
5. **Multi-tenancy**: Support for multiple companies/divisions