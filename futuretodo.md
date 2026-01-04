# Future Todo - Implementation Status

## All Items Complete

### 1. Auto-generate Display Name in Products - DONE
- Add/Edit Product form auto-generates display name
- Bulk Import now also auto-generates display_name on submit
- Format: `Brand - Product Name - Flavor - Size (VX)`
- Live preview shows as user types
- Version field (optional) added
- Shared utility in `frontend/src/lib/product-utils.ts`

### 2. Fix Bulk Import Validation Error Bug - DONE
- Empty placeholder rows no longer show validation errors
- Validation only triggers after row is touched (on blur)

### 3. Move Lab Test Types Above Products in Menu - DONE
- Configuration menu reordered

### 4. Flask Icon Tooltip Showing Test Names - DONE
- Hover tooltip on flask icon shows test names
- Truncates at 5 with "...and X more"
- Required tests shown with asterisk

### 5. Remove "Import Results" from Menu - DONE
- Removed from sidebar menu
- Route and page file deleted

### 6. Rename "RECENTLY COMPLETED" to Include Time Window - DONE
- Column shows "Recently Completed (Xd)"
- Time window admin-configurable in Settings
- Default: 7 days

### 7. Update Sample Tracker Card Format - DONE
- Cards show: Product display_name (or lot type fallback), Ref #, Lot #, test progress, days counter
- Multi-product lots show first product + "+X more"
- Completed cards show "Completed: Xd ago"
- Active cards show "In stage: Xd" with color-coded urgency
- Backend updated to include products in lot list response

---

## Implementation Details

### Bulk Import Changes
- `frontend/src/lib/bulk-import/validators.ts` - Removed display_name, added version field
- `frontend/src/components/bulk-import/ProductBulkImport.tsx` - New template format, auto-generates display_name on submit, version column added, display_name preview column

### Kanban Product Info Changes
- `backend/app/schemas/lot.py` - Added ProductSummary, LotWithProductSummaryResponse
- `backend/app/api/v1/endpoints/lots.py` - Eager loading of products, includes product info in list response
- `frontend/src/types/index.ts` - Added ProductSummary, products field on Lot
- `frontend/src/components/domain/KanbanBoard.tsx` - Displays product display_name on cards
