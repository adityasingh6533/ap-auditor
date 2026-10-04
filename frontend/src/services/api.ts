/**
 * API service layer for AP Auditor frontend.
 * Wraps all backend FastAPI endpoints with typed axios calls.
 */

import axios from 'axios';

const BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
});

// ── Types ──────────────────────────────────────────────────────────────────

export interface ChatResponse {
  reply: string;
  intent: string;
  data: Record<string, unknown> | null;
}

export interface StatsResponse {
  total_processed: number;
  auto_pass_count: number;
  flagged_count: number;
  needs_review_count: number;
  breakdown: Record<string, number>;
}

export interface InvoiceException {
  invoice_id: string;
  vendor_name: string;
  amount: number;
  category: string;
  status: string;
  confidence_score: number;
  triggered_checks: string;
  reason_text: string;
  matched_reference: string | null;
  processed_at: string;
}

export interface AuditLogEntry {
  log_id: number;
  invoice_id: string;
  action: string;
  performed_by: string;
  reason: string;
  timestamp: string;
}

export interface UploadSummary {
  total: number;
  auto_pass_count: number;
  flagged_count: number;
  needs_review_count: number;
}

// ── Chat ───────────────────────────────────────────────────────────────────

export const sendChatMessage = async (message: string): Promise<ChatResponse> => {
  const { data } = await api.post<ChatResponse>('/api/chat', { message });
  return data;
};

// ── Upload ─────────────────────────────────────────────────────────────────

export const uploadInvoiceCSV = async (file: File): Promise<UploadSummary> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<UploadSummary>('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

// ── Stats ──────────────────────────────────────────────────────────────────

export const fetchStats = async (): Promise<StatsResponse> => {
  const { data } = await api.get<StatsResponse>('/api/stats');
  return data;
};

// ── Exceptions ─────────────────────────────────────────────────────────────

export const fetchExceptions = async (limit = 50): Promise<InvoiceException[]> => {
  const { data } = await api.get<InvoiceException[]>('/api/exceptions', {
    params: { limit },
  });
  return data;
};

// ── Review decision ────────────────────────────────────────────────────────

export const submitDecision = async (
  invoiceId: string,
  decision: 'approve' | 'reject',
  reviewer = 'Dashboard User'
): Promise<{ success: boolean; invoice_id: string; status: string }> => {
  const { data } = await api.post(`/api/review/${invoiceId}/decision`, {
    decision,
    reviewer,
  });
  return data;
};

// ── Audit Logs ─────────────────────────────────────────────────────────────

export const fetchAuditLogs = async (limit = 50): Promise<AuditLogEntry[]> => {
  const { data } = await api.get<AuditLogEntry[]>('/api/audit-logs', {
    params: { limit },
  });
  return data;
};
