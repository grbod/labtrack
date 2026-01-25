/**
 * Audit trail API client
 */

import { api } from "./client";

// Types
export type AuditAction =
  | "insert"
  | "update"
  | "delete"
  | "approve"
  | "reject"
  | "validation_failed";

export interface FieldChange {
  field: string;
  old_value: unknown;
  new_value: unknown;
  display_old: string | null;
  display_new: string | null;
}

export interface AuditEntryDisplay {
  id: number;
  action: AuditAction;
  action_display: string;
  timestamp: string;
  timestamp_display: string;
  username: string;
  changes: FieldChange[];
  reason: string | null;
  is_bulk_operation: boolean;
  bulk_summary: string | null;
  annotation_count: number;
}

export interface AuditTrailResponse {
  table_name: string;
  record_id: number;
  entries: AuditEntryDisplay[];
  total: number;
}

export interface AuditAnnotation {
  id: number;
  audit_log_id: number;
  user_id: number;
  username: string | null;
  comment: string | null;
  attachment_filename: string | null;
  attachment_size: number | null;
  attachment_hash: string | null;
  created_at: string;
}

export interface AuditAnnotationListResponse {
  items: AuditAnnotation[];
  total: number;
}

export interface AuditLogFilters {
  table_name?: string;
  record_id?: number;
  action?: AuditAction;
  user_id?: number;
  date_from?: string;
  date_to?: string;
}

/** Metadata for export filename generation */
export interface ExportMetadata {
  brand?: string;
  productName?: string;
  lotNumber?: string;
}

/** View mode for audit trail display */
export type AuditViewMode = "summary" | "detailed";

/** Consolidated row for summary view */
export interface ConsolidatedRow {
  id: string; // unique key for React
  auditIds: number[]; // all audit IDs included in this consolidated row
  primaryAuditId: number; // main audit ID for annotations
  timestamp: Date;
  timestampDisplay: string;
  username: string;
  action: string;
  actionDisplay: string;
  field: string; // field name or description (e.g., "E. coli (6 fields)", "Status")
  oldValue: string; // old value or "—" for creates
  newValue: string; // new value
  reason: string | null;
  annotationCount: number; // total across all consolidated entries
  consolidatedCount: number; // number of entries consolidated (1 if not consolidated)
}

// API functions

/**
 * Get audit trail for a specific record
 */
export async function getAuditTrail(
  tableName: string,
  recordId: number
): Promise<AuditTrailResponse> {
  const response = await api.get<AuditTrailResponse>(
    `/audit/${tableName}/${recordId}/trail`
  );
  return response.data;
}

/**
 * Get annotations for an audit log entry
 */
export async function getAnnotations(
  auditId: number
): Promise<AuditAnnotationListResponse> {
  const response = await api.get<AuditAnnotationListResponse>(
    `/audit/${auditId}/annotations`
  );
  return response.data;
}

/**
 * Add a comment to an audit log entry
 */
export async function addAnnotationComment(
  auditId: number,
  comment: string
): Promise<AuditAnnotation> {
  const params = new URLSearchParams();
  params.append("comment", comment);

  const response = await api.post<AuditAnnotation>(
    `/audit/${auditId}/annotations?${params.toString()}`
  );
  return response.data;
}

/**
 * Add an attachment to an audit log entry
 */
export async function addAnnotationAttachment(
  auditId: number,
  file: File,
  comment?: string
): Promise<AuditAnnotation> {
  const formData = new FormData();
  formData.append("file", file);
  if (comment) {
    formData.append("comment", comment);
  }

  const response = await api.post<AuditAnnotation>(
    `/audit/${auditId}/annotations`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
  return response.data;
}

/**
 * Download an attachment
 */
export async function downloadAttachment(
  auditId: number,
  annotationId: number,
  filename: string
): Promise<void> {
  const response = await api.get(
    `/audit/${auditId}/annotations/${annotationId}/download`,
    {
      responseType: "blob",
    }
  );

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Sanitize string for filename (remove spaces and special characters)
 */
function sanitizeForFilename(s: string): string {
  return s.replace(/\s+/g, "").replace(/[^a-zA-Z0-9-_]/g, "");
}

/**
 * Export audit logs as CSV
 */
export async function exportAuditCsv(
  filters?: AuditLogFilters,
  metadata?: ExportMetadata
): Promise<void> {
  const params = new URLSearchParams();
  if (filters?.table_name) params.append("table_name", filters.table_name);
  if (filters?.record_id) params.append("record_id", String(filters.record_id));
  if (filters?.action) params.append("action", filters.action);
  if (filters?.user_id) params.append("user_id", String(filters.user_id));
  if (filters?.date_from) params.append("date_from", filters.date_from);
  if (filters?.date_to) params.append("date_to", filters.date_to);

  const response = await api.get(`/audit/export/csv?${params.toString()}`, {
    responseType: "blob",
  });

  // Generate filename from metadata if available
  const filename =
    metadata?.brand && metadata?.productName && metadata?.lotNumber
      ? `${sanitizeForFilename(metadata.brand)}-${sanitizeForFilename(metadata.productName)}-${sanitizeForFilename(metadata.lotNumber)}.csv`
      : `audit_export_${new Date().toISOString().slice(0, 10)}.csv`;

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Export audit logs as PDF
 */
export async function exportAuditPdf(
  filters?: AuditLogFilters,
  metadata?: ExportMetadata
): Promise<void> {
  const params = new URLSearchParams();
  if (filters?.table_name) params.append("table_name", filters.table_name);
  if (filters?.record_id) params.append("record_id", String(filters.record_id));
  if (filters?.action) params.append("action", filters.action);
  if (filters?.user_id) params.append("user_id", String(filters.user_id));
  if (filters?.date_from) params.append("date_from", filters.date_from);
  if (filters?.date_to) params.append("date_to", filters.date_to);

  const response = await api.get(`/audit/export/pdf?${params.toString()}`, {
    responseType: "blob",
  });

  // Generate filename from metadata if available
  const filename =
    metadata?.brand && metadata?.productName && metadata?.lotNumber
      ? `${sanitizeForFilename(metadata.brand)}-${sanitizeForFilename(metadata.productName)}-${sanitizeForFilename(metadata.lotNumber)}.pdf`
      : `audit_export_${new Date().toISOString().slice(0, 10)}.pdf`;

  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
