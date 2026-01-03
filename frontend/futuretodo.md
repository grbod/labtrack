# Future TODO

## Bulk Import - Manual Entry Issues

**Page clarification needed**: User mentions "import product" button and "shift" navigation - likely referring to CreateSample page Multi-SKU Composite table, NOT ImportResults page.

### Issue 1: Shift navigation requires Enter to start typing
- When pressing Shift to navigate between cells in manual entry mode, focus shifts correctly
- BUT user has to press Enter before they can start typing
- **Expected**: Should be able to start typing immediately after Shift navigation

**Likely cause**: Tab/Shift+Tab navigating to a wrapper element (e.g., combobox button) rather than directly to the input. Need to check if focus is landing on the correct element.

**Potential fix**: Ensure the input element receives focus directly, not a container. May need to use `ref` to programmatically focus the input text field.

### Issue 2: Import fails and clears data
- When clicking "Import Product", even with correct data, it won't import
- Additionally, it clears all entered data, preventing user from fixing issues
- **Expected**:
  - Should import valid data
  - On error, should preserve data so user can correct it

**Likely causes to investigate**:
1. Form validation failing silently (check Zod schema matching backend expectations)
2. `useFieldArray` remove/append behavior causing re-renders that lose state
3. Form `reset()` being called inadvertently on error
4. API returning 422 (check enum case or required fields mismatch)

**Key fix**: Never clear form data on error - only clear on successful submission
