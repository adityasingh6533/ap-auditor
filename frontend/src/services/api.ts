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
  matched_invoice?: {
    invoice_id: string;
    vendor_name: string;
    amount: number;
    category: string;
    status: string;
    processed_at?: string;
  } | null;
}

export interface AuditLogEntry {
  log_id: number;
  invoice_id: string;
  action: string;
  performed_by: string;
  reason: string;
  timestamp: string;
  integrity_hash?: string;
}

export interface AuditVerifyResponse {
  status: string;
  total_records_checked: number;
  verified_clean: number;
  tampered_count: number;
  tampered_records: Array<{
    log_id: number;
    invoice_id: string;
    action: string;
    stored_hash: string;
    expected_hash: string;
  }>;
  message: string;
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

export const verifyAuditLogs = async (): Promise<AuditVerifyResponse> => {
  const { data } = await api.get<AuditVerifyResponse>('/api/audit-logs/verify');
  return data;
};

// ── Reports ────────────────────────────────────────────────────────────────

export const downloadReport = async (format: 'pdf' | 'csv' = 'pdf'): Promise<void> => {
  const response = await api.get(`/api/reports/export`, {
    params: { format },
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `ap_exception_report.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export interface ChatStatusResponse {
  provider: string;
  model: string;
  api_key_configured: boolean;
  is_placeholder: boolean;
  key_source: string;
  key_preview: string;
  tier1_rules_engine: string;
  tier2_llm_engine: string;
  connection_test?: string;
  gemini_ready: boolean;
  instruction?: string;
}

export const fetchChatStatus = async (): Promise<ChatStatusResponse> => {
  const { data } = await api.get<ChatStatusResponse>('/api/chat/status');
  return data;
};

export interface PolicyCategoryRule {

  limit: number;
  po_required: boolean;
}

export interface ApprovalLadderRole {
  role: string;
  max_amount: number | null;
}

export interface DuplicateMatchingConfig {
  fuzzy_similarity_threshold: number;
  amount_tolerance_percent: number;
  date_window_days: number;
}

export interface PolicyConfig {
  categories: Record<string, PolicyCategoryRule>;
  approval_ladder: ApprovalLadderRole[];
  duplicate_matching: DuplicateMatchingConfig;
  po_tolerance_percent: number;
  confidence_threshold_auto_flag: number;
}

export const fetchPolicyConfig = async (): Promise<PolicyConfig> => {
  const { data } = await api.get<PolicyConfig>('/api/config');
  return data;
};

export const updatePolicyConfig = async (config: PolicyConfig): Promise<{ message: string; config: PolicyConfig }> => {
  const { data } = await api.put<{ message: string; config: PolicyConfig }>('/api/config', config);
  return data;
};



