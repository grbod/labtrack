# Product Requirements Document: LabTrack

## 1. Executive Summary

### Current State
The existing COA (Certificate of Analysis) creation system relies on a cumbersome Excel-based workflow with several critical issues:
- Massive Excel file containing all historical data
- Buggy "ToPrint" column mechanism for job queuing
- Manual handling of sublots with no proper relationship tracking
- Inconsistent product naming and formatting
- No automation of lab result processing

### Vision
Transform the COA generation process into an automated, AI-powered system where users simply drop lab PDFs into a folder and receive professionally formatted COAs with standardized product information and proper lot relationship handling.

## 2. User Requirements

### 2.1 Core Workflow
1. **Drop PDF → Generate COA**: Users drop lab PDF into watched folder
2. **Automatic Parsing**: AI extracts test results using reference numbers
3. **Standardized Output**: COAs generated with consistent product naming
4. **No Manual Data Entry**: Eliminate Excel-based data management

### 2.2 Key Problems to Solve
- **Sublot Confusion**: Current system treats every row as separate lot
- **Product Inconsistency**: "Premium protein shake" vs other variations
- **Manual Process**: Too many manual steps and opportunities for error
- **Buggy Status Tracking**: ToPrint/Success column is unreliable

## 3. System Architecture

### 3.1 Database Schema

```sql
-- Standardized product catalog
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    brand TEXT NOT NULL,
    product_name TEXT NOT NULL,
    flavor TEXT,
    size TEXT,
    display_name TEXT NOT NULL, -- Standardized display name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main lots table (includes parent lots and composites)
CREATE TABLE lots (
    lot_id INTEGER PRIMARY KEY,
    lot_number TEXT UNIQUE NOT NULL,
    lot_type TEXT CHECK (lot_type IN ('standard', 'parent_lot', 'multi_sku_composite')),
    reference_number TEXT UNIQUE NOT NULL, -- For lab communication
    mfg_date DATE,
    exp_date DATE,
    status TEXT CHECK (status IN ('pending', 'tested', 'approved', 'released')),
    generate_coa BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sublots for production tracking
CREATE TABLE sublots (
    sublot_id INTEGER PRIMARY KEY,
    parent_lot_id INTEGER NOT NULL,
    sublot_number TEXT UNIQUE NOT NULL, -- e.g., "ABC123-1"
    production_date DATE,
    quantity_lbs DECIMAL(10,2),
    FOREIGN KEY (parent_lot_id) REFERENCES lots(lot_id)
);

-- Link lots to products (many-to-many for composites)
CREATE TABLE lot_products (
    lot_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    percentage DECIMAL(5,2), -- For multi-SKU composites
    PRIMARY KEY (lot_id, product_id),
    FOREIGN KEY (lot_id) REFERENCES lots(lot_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Test results from lab
CREATE TABLE test_results (
    result_id INTEGER PRIMARY KEY,
    lot_id INTEGER NOT NULL, -- Always links to parent/main lot
    test_type TEXT NOT NULL,
    result_value TEXT,
    unit TEXT,
    test_date DATE,
    pdf_source TEXT, -- Filename of source PDF
    confidence_score DECIMAL(3,2), -- AI confidence 0.00-1.00
    status TEXT CHECK (status IN ('draft', 'reviewed', 'approved')) DEFAULT 'draft',
    approved_by TEXT,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lot_id) REFERENCES lots(lot_id)
);

-- User management
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT CHECK (role IN ('admin', 'qc_manager', 'lab_tech', 'read_only')),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Manual review queue for failed PDF parsing
CREATE TABLE parsing_queue (
    queue_id INTEGER PRIMARY KEY,
    pdf_filename TEXT NOT NULL,
    reference_number TEXT,
    error_message TEXT,
    status TEXT CHECK (status IN ('pending', 'processing', 'resolved', 'failed')),
    assigned_to TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Audit log for tracking all changes
CREATE TABLE audit_log (
    log_id INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    action TEXT CHECK (action IN ('insert', 'update', 'delete', 'approve', 'reject')),
    old_values TEXT, -- JSON
    new_values TEXT, -- JSON
    user_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- COA generation history
CREATE TABLE coa_history (
    coa_id INTEGER PRIMARY KEY,
    lot_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_by TEXT,
    FOREIGN KEY (lot_id) REFERENCES lots(lot_id)
);
```

### 3.2 System Components

1. **Product Management Module**
   - CRUD operations for standardized product catalog
   - Validation of product naming conventions
   - Bulk import/export capabilities

2. **Sample Management Module**
   - Create samples with auto-generated reference numbers
   - Handle parent-sublot relationships
   - Track sample lifecycle and status

3. **PDF Parser Service**
   - Watch designated folder for new PDFs
   - AI-powered extraction of test results
   - Match results to samples via reference number
   - Handle multiple PDF formats from different labs

4. **COA Generator Service**
   - Template-based generation
   - Automatic triggering on test result completion
   - Consistent formatting and branding
   - PDF and DOCX output formats

5. **Web Interface (React + FastAPI)**
   - User-friendly dashboard
   - Product and sample management
   - PDF parsing queue monitoring
   - COA generation and preview

6. **CLI Interface**
   - Automation and scripting
   - Batch operations
   - System administration

## 4. Functional Requirements

### 4.1 Sample Creation
- **Unique Reference Generation**: System generates unique reference numbers
- **Product Association**: Link samples to standardized products
- **Lot Type Selection**: Specify standard, parent lot, or composite
- **Sublot Management**: Create sublots under parent with proper relationships

### 4.2 PDF Processing
- **Folder Monitoring**: Watch for new PDFs in designated folder
- **AI Extraction**: Use GPT-4/Claude to extract:
  - Reference number
  - Test results (microbiological, heavy metals, etc.)
  - Test dates
  - Lab identification
- **Error Handling**: Queue failed extractions for manual review
- **Result Validation**: Verify extracted data meets expected formats

### 4.3 COA Generation Rules
- **Parent Lots Only**: Generate COAs only for lots where `generate_coa = TRUE`
- **Sublot Aggregation**: Parent lot COAs include composite test results
- **Multi-SKU Composites**: Show component products and percentages
- **Standardized Format**: Use consistent product display names

### 4.4 Error Handling & Recovery

#### PDF Parsing Failures
- **Automatic Retry**: System attempts parsing 3 times with different AI prompts
- **Confidence Scoring**: Each extracted field gets a confidence score (0.0-1.0)
- **Low Confidence Alert**: Fields below 0.7 confidence flagged for review
- **Manual Review Queue**: Failed PDFs move to manual queue with:
  - Original PDF preview
  - AI's attempted extraction
  - Error messages
  - Manual data entry form
  - Ability to reassign to another user

#### Duplicate Detection
- **Reference Number Check**: Prevent duplicate reference numbers
- **PDF Hash Check**: Detect if same PDF uploaded twice
- **Lot Number + Date Check**: Secondary matching for legacy PDFs
- **Override Option**: QC Manager can force processing with justification

#### Missing Data Handling
- **Required Fields**: Cannot generate COA without:
  - All microbiological results (or explicit "Not Tested")
  - Product identification
  - Lot number and dates
- **Partial Results**: Store what's available, flag as incomplete
- **Follow-up System**: Track pending test results

#### Recovery Procedures
- **Reprocess Button**: Retry parsing with updated AI model
- **Bulk Reprocessing**: Handle multiple failed PDFs at once
- **Import from Excel**: Fallback option for manual data entry
- **API Override**: Direct data entry via API for integration

### 4.5 Approval Workflow

#### Test Result Lifecycle
1. **Draft Status** (Initial state)
   - AI-parsed or manually entered results
   - Editable by lab techs
   - Not visible for COA generation

2. **Reviewed Status**
   - Lab tech marks as complete
   - QC Manager notified
   - Still editable with audit trail

3. **Approved Status**
   - QC Manager reviews and approves
   - Locked from editing
   - Available for COA generation
   - Timestamp and approver recorded

#### Approval Rules
- **Role-Based Permissions**:
  - Lab Tech: Create, edit draft/reviewed results
  - QC Manager: All lab tech permissions + approve/reject
  - Admin: Override any status, manage users
  - Read-only: View only

- **Approval Requirements**:
  - All test results must be approved before COA generation
  - Composite lots need all component results approved
  - Re-approval required if any result is edited post-approval

#### Rejection Handling
- **Reject with Reason**: QC Manager must provide rejection reason
- **Notification**: Lab tech notified of rejection
- **Revision History**: Track all changes between submissions
- **Re-submission**: Easy path to correct and resubmit

#### Audit Trail
- **Complete History**: Every change logged with:
  - Who made the change
  - When it occurred
  - What changed (before/after values)
  - Why (for rejections/overrides)
- **Regulatory Compliance**: 21 CFR Part 11 compliant
- **Immutable Log**: Cannot be edited or deleted
- **Export Function**: Generate audit reports for inspections

### 4.6 Workflow Examples

#### Large Batch Production (Sublot Scenario)
1. Create parent lot "ABC123" for 10,000 lbs order
2. System creates 5 sublots (ABC123-1 through ABC123-5) for 2,000 lb batches
3. Lab takes samples from each sublot, creates composite
4. Lab PDF arrives with parent lot reference number
5. System parses results, assigns to parent lot
6. COA generated for parent lot only

#### Multi-SKU Composite
1. Create composite lot "COMP456" with unique reference
2. Link multiple products with blend percentages
3. Lab tests the composite blend
4. System parses composite test results
5. COA shows all component products

## 5. Technical Requirements

### 5.1 Technology Stack
- **Language**: Python 3.10+
- **Database**: SQLite (upgradeable to PostgreSQL)
- **AI Service**: OpenAI API or Anthropic Claude API
- **PDF Processing**: PyPDF2, pdfplumber
- **COA Generation**: python-docx, ReportLab
- **File Watching**: watchdog
- **Web Framework**: FastAPI (backend) + React/Vite (frontend)
- **CLI**: Click framework
- **Testing**: pytest

### 5.2 Integration Requirements
- **Lab Communication**: Reference numbers printed on sample labels
- **File System**: Network accessible folders for PDF drop
- **API**: RESTful API for future integrations
- **Export**: Data export to Excel for regulatory compliance

### 5.3 Performance Requirements
- PDF parsing: < 30 seconds per document
- COA generation: < 10 seconds per document
- Support for 100+ COAs per day
- Database queries: < 100ms response time
- Web app: < 2 second page loads

## 6. User Interface

### 6.1 Web Interface

#### Dashboard Page
- Overview statistics (pending samples, completed COAs, etc.)
- Recent activity feed
- Quick actions (create sample, generate COA)

#### Product Management Page
- Searchable product catalog
- Add/Edit/Delete products
- Bulk import from Excel
- Standardized naming validation

#### Sample Management Page
- Create new samples with auto-generated reference numbers
- Parent lot creation with sublot management
- Multi-SKU composite setup
- Sample status tracking

#### PDF Processing Page
- Upload PDFs manually or monitor drop folder
- View parsing queue and status
- Confidence scores for each extracted field
- Manual review/correction of parsed data
- Reprocess failed extractions
- Duplicate detection alerts

#### Manual Review Queue Page
- List of failed PDF parsing attempts
- Side-by-side view: PDF preview + extraction form
- Confidence highlighting (red/yellow/green)
- Manual data entry with validation
- Reassign to different user
- Add notes for complex cases

#### Approval Dashboard Page
- Pending approvals queue
- Filter by: status, date, product, urgency
- Bulk approval actions
- Rejection with mandatory reason
- View complete test history
- Audit trail for each lot

#### COA Generation Page
- Only show lots with approved results
- Preview COA before finalizing
- Batch generation capabilities
- Download individual or bulk COAs
- Re-approval required for regeneration

#### Reports & Analytics Page
- COA generation history
- Product usage statistics
- Error/issue tracking
- Export capabilities

### 6.2 CLI Commands (for automation)
```bash
# Product management
labtrack product add --brand "Truvani" --name "Organic Whey Protein" --flavor "Vanilla"
labtrack product list
labtrack product update <id> --display-name "Organic Whey Protein Powder"

# Sample creation
labtrack sample create --product <id> --type parent_lot --quantity 10000
labtrack sample create-sublots --parent <lot_number> --count 5 --quantity 2000

# Manual operations
labtrack parse-pdf <filename>
labtrack generate-coa --lot <lot_number>
labtrack status --pending

# Reporting
labtrack report --from 2024-01-01 --to 2024-12-31
```

## 7. Success Metrics

### 7.1 Automation Metrics
- **Manual Data Entry**: Reduce by 95%
- **Processing Time**: From 15 minutes to < 1 minute per COA
- **Error Rate**: Reduce COA errors by 90%

### 7.2 Quality Metrics
- **Product Consistency**: 100% standardized naming
- **Sublot Handling**: Zero confusion on parent-child relationships
- **Traceability**: Complete audit trail for all COAs

### 7.3 User Experience Metrics
- **Training Time**: < 1 hour for new users
- **User Satisfaction**: > 90% approval rating
- **System Adoption**: 100% within 30 days

## 8. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- Database setup and schema implementation
- Product catalog with standardized entries
- Basic app structure

### Phase 2: Sample Management (Weeks 3-4)
- Sample creation with reference numbers
- Parent-sublot relationship handling
- Status tracking system
- UI for sample management

### Phase 3: PDF Integration (Weeks 5-6)
- PDF watching service
- AI integration for parsing
- Result storage and validation
- UI for PDF processing queue

### Phase 4: COA Generation (Weeks 7-8)
- Template development
- Automated generation logic
- Output folder management
- UI for COA preview/generation

### Phase 5: Polish & Testing (Weeks 9-10)
- Error handling and edge cases
- Performance optimization
- User documentation
- UI refinements

## 9. Risks and Mitigation

### 9.1 Technical Risks
- **AI Parsing Accuracy**: Mitigate with validation rules and manual review queue
- **PDF Format Variations**: Build library of test cases from different labs
- **Data Migration**: Provide tools to import historical data

### 9.2 Business Risks
- **User Adoption**: Modern web interface with familiar patterns
- **Regulatory Compliance**: Ensure audit trails meet requirements
- **Lab Integration**: Work closely with labs on reference number implementation

## 10. Future Enhancements

- Mobile-responsive interface
- Email notifications for COA completion
- Integration with ERP/inventory systems
- Customer portal for COA access
- Advanced analytics and trending
- Blockchain integration for authenticity
- Multi-language support