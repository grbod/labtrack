/**
 * React hooks for audit trail functionality
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAuditTrail,
  getAnnotations,
  addAnnotationComment,
  addAnnotationAttachment,
  downloadAttachment,
  exportAuditCsv,
  exportAuditPdf,
  type AuditLogFilters,
  type ExportMetadata,
} from "../api/audit";

/**
 * Query key factory for audit queries
 */
export const auditKeys = {
  all: ["audit"] as const,
  trail: (tableName: string, recordId: number) =>
    [...auditKeys.all, "trail", tableName, recordId] as const,
  annotations: (auditId: number) =>
    [...auditKeys.all, "annotations", auditId] as const,
};

/**
 * Hook to fetch audit trail for a record
 */
export function useAuditTrail(
  tableName: string,
  recordId: number,
  enabled = true
) {
  return useQuery({
    queryKey: auditKeys.trail(tableName, recordId),
    queryFn: () => getAuditTrail(tableName, recordId),
    enabled: enabled && !!tableName && recordId > 0,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to fetch annotations for an audit entry
 */
export function useAnnotations(auditId: number, enabled = true) {
  return useQuery({
    queryKey: auditKeys.annotations(auditId),
    queryFn: () => getAnnotations(auditId),
    enabled: enabled && auditId > 0,
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook to add a comment annotation
 */
export function useAddCommentAnnotation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ auditId, comment }: { auditId: number; comment: string }) =>
      addAnnotationComment(auditId, comment),
    onSuccess: (_, { auditId }) => {
      // Invalidate annotations for this audit entry
      queryClient.invalidateQueries({
        queryKey: auditKeys.annotations(auditId),
      });
      // Also invalidate the trail to update annotation counts
      queryClient.invalidateQueries({
        queryKey: auditKeys.all,
      });
    },
  });
}

/**
 * Hook to add an attachment annotation
 */
export function useAddAttachmentAnnotation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      auditId,
      file,
      comment,
    }: {
      auditId: number;
      file: File;
      comment?: string;
    }) => addAnnotationAttachment(auditId, file, comment),
    onSuccess: (_, { auditId }) => {
      // Invalidate annotations for this audit entry
      queryClient.invalidateQueries({
        queryKey: auditKeys.annotations(auditId),
      });
      // Also invalidate the trail to update annotation counts
      queryClient.invalidateQueries({
        queryKey: auditKeys.all,
      });
    },
  });
}

/**
 * Hook to download an attachment
 */
export function useDownloadAttachment() {
  return useMutation({
    mutationFn: ({
      auditId,
      annotationId,
      filename,
    }: {
      auditId: number;
      annotationId: number;
      filename: string;
    }) => downloadAttachment(auditId, annotationId, filename),
  });
}

/**
 * Hook to export audit logs as CSV
 */
export function useExportAuditCsv() {
  return useMutation({
    mutationFn: ({
      filters,
      metadata,
    }: {
      filters?: AuditLogFilters;
      metadata?: ExportMetadata;
    }) => exportAuditCsv(filters, metadata),
  });
}

/**
 * Hook to export audit logs as PDF
 */
export function useExportAuditPdf() {
  return useMutation({
    mutationFn: ({
      filters,
      metadata,
    }: {
      filters?: AuditLogFilters;
      metadata?: ExportMetadata;
    }) => exportAuditPdf(filters, metadata),
  });
}
