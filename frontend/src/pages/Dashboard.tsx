import React, { useEffect, useState, useCallback, useRef } from 'react';
import { RefreshCw, CheckCircle, AlertTriangle, Clock, ChevronRight, Download, Upload, RotateCcw, Sparkles } from 'lucide-react';
import { fetchStats, fetchExceptions, submitDecision, downloadReport, resetDataset, loadDemoDataset, uploadInvoiceCSV, StatsResponse, InvoiceException } from '../services/api';
import { DuplicateComparisonCard } from '../components/DuplicateComparisonCard';

// ── Stat Card ──────────────────────────────────────────────────────────────

const StatCard: React.FC<{
  label: string;
  value: number;
  total: number;
  colorClass: string;
  icon: React.ReactNode;
}> = ({ label, value, total, colorClass, icon }) => {
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0';
  return (
    <div className="bg-industrial-surface border border-industrial-border p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-industrial-text-muted tracking-widest uppercase">{label}</span>
        <span className={`${colorClass} opacity-80`}>{icon}</span>
      </div>
      <div className={`text-4xl font-mono font-bold ${colorClass}`}>{value.toLocaleString()}</div>
      <div className="text-xs text-industrial-text-dim">{pct}% of {total.toLocaleString()} processed</div>
      <div className="h-1 bg-industrial-graphite">
        <div className={`h-1 ${colorClass.replace('text-', 'bg-').replace('nominal-bright', 'nominal')} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
};

// ── Status badge ───────────────────────────────────────────────────────────

const StatusTag: React.FC<{ status: string }> = ({ status }) => {
  const map: Record<string, string> = {
    NEEDS_HUMAN_REVIEW: 'text-warning bg-warning/10 border-warning/30',
    FLAGGED_AUTO:       'text-error bg-error/10 border-error/30',
    HUMAN_APPROVED:     'text-nominal-bright bg-nominal/10 border-nominal/30',
    HUMAN_REJECTED:     'text-error bg-error/10 border-error/30',
    AUTO_PASS:          'text-nominal-bright bg-nominal/10 border-nominal/30',
  };
  return (
    <span className={`px-2 py-0.5 text-[10px] font-semibold tracking-widest uppercase border whitespace-nowrap ${map[status] ?? 'text-industrial-text-muted border-industrial-border'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
};

// ── Main Page ──────────────────────────────────────────────────────────────

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [exceptions, setExceptions] = useState<InvoiceException[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [successToast, setSuccessToast] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    setError(null);
    try {
      const [s, e] = await Promise.all([fetchStats(), fetchExceptions(100)]);
      setStats(s);
      setExceptions(e);
    } catch {
      setError('Failed to connect to backend at http://localhost:8000. Make sure uvicorn is running.');
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Auto-poll every 8 seconds so uploads from Chat or other tabs update live
    const interval = setInterval(() => {
      load(true);
    }, 8000);
    return () => clearInterval(interval);
  }, [load]);

  const handleDecision = useCallback(async (invoiceId: string, decision: 'approve' | 'reject') => {
    setActionLoading(invoiceId);
    try {
      await submitDecision(invoiceId, decision, 'Dashboard User');
      setExceptions((prev) => prev.filter((e) => e.invoice_id !== invoiceId));
      load(true);
    } catch {
      // silently ignore
    } finally {
      setActionLoading(null);
    }
  }, [load]);

  const handleExport = async (format: 'pdf' | 'csv' = 'pdf') => {
    setExporting(true);
    try {
      await downloadReport(format);
    } catch (err) {
      alert('Failed to download audit report. Please verify backend service.');
    } finally {
      setExporting(false);
    }
  };

  const handleResetToZero = async () => {
    if (!window.confirm('Reset database to 0 invoices? All previous data will be cleared.')) return;
    setResetting(true);
    try {
      await resetDataset();
      setSuccessToast('Dataset reset to 0 invoices. Clean workspace ready for upload.');
      setTimeout(() => setSuccessToast(null), 5000);
      await load();
    } catch {
      alert('Failed to reset dataset.');
    } finally {
      setResetting(false);
    }
  };

  const handleLoadDemo = async () => {
    setResetting(true);
    try {
      const summary = await loadDemoDataset();
      setSuccessToast(`Demo dataset loaded with ${summary.total.toLocaleString()} invoices.`);
      setTimeout(() => setSuccessToast(null), 5000);
      await load();
    } catch {
      alert('Failed to load demo dataset.');
    } finally {
      setResetting(false);
    }
  };

  const handleUploadFromDashboard = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setUploading(true);
    try {
      const summary = await uploadInvoiceCSV(file, true);
      setSuccessToast(`Uploaded & audited ${summary.total.toLocaleString()} invoices from ${file.name}.`);
      setTimeout(() => setSuccessToast(null), 5000);
      await load();
    } catch (err: any) {
      alert(`Upload failed: ${err?.response?.data?.detail || err?.message || 'Check CSV'}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleUploadFromDashboard}
      />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-industrial-text tracking-tight">Audit Dashboard</h1>
            {stats && (
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-mono bg-nominal/10 text-nominal-bright border border-nominal/30">
                <span className="w-1.5 h-1.5 rounded-full bg-nominal-bright animate-pulse" />
                Live: {stats.total_processed.toLocaleString()} Invoices Audited
              </span>
            )}
          </div>
          <p className="text-sm text-industrial-text-muted mt-1">Real-time compliance overview from the AP rules engine</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-accent bg-accent/10 text-accent hover:bg-accent/20 text-xs font-medium transition-colors disabled:opacity-50"
            title="Upload CSV to replace active dataset"
          >
            <Upload size={13} className={uploading ? 'animate-bounce' : ''} />
            {uploading ? 'Auditing...' : 'Upload Dataset'}
          </button>
          <button
            onClick={handleResetToZero}
            disabled={resetting}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-industrial-border text-industrial-text-muted hover:border-error/40 hover:text-error text-xs transition-colors disabled:opacity-50"
            title="Purge all records and reset dashboard to 0"
          >
            <RotateCcw size={13} className={resetting ? 'animate-spin' : ''} />
            {resetting ? 'Resetting...' : 'Reset to 0'}
          </button>
          <button
            onClick={handleLoadDemo}
            disabled={resetting}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-industrial-border text-industrial-text-muted hover:border-accent/40 hover:text-accent text-xs transition-colors disabled:opacity-50"
            title="Load default 3,000 demo benchmark dataset"
          >
            <RotateCcw size={13} />
            Load Demo (3k)
          </button>
          <button
            onClick={() => handleExport('pdf')}
            disabled={exporting}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-industrial-border bg-industrial-surface text-industrial-text text-xs hover:border-accent/40 transition-colors disabled:opacity-50"
            title="Download executive PDF exception summary"
          >
            <Download size={13} className={exporting ? 'animate-bounce' : ''} />
            {exporting ? 'Exporting...' : 'Export PDF'}
          </button>
          <button
            onClick={() => load()}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-industrial-border text-xs text-industrial-text-muted hover:border-accent/50 hover:text-accent transition-colors"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {successToast && (
        <div className="border border-nominal/40 bg-nominal/10 text-nominal-bright text-xs px-4 py-2.5 flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Sparkles size={14} />
            {successToast}
          </span>
          <button onClick={() => setSuccessToast(null)} className="text-industrial-text-muted hover:text-industrial-text">✕</button>
        </div>
      )}

      {error && (
        <div className="border border-error/40 bg-error/10 text-error text-sm px-4 py-3">
          {error}
        </div>
      )}

      {/* Zero invoices empty state banner */}
      {stats && stats.total_processed === 0 && (
        <div className="border border-industrial-border bg-industrial-surface p-6 text-center space-y-3">
          <div className="text-industrial-text font-semibold text-sm">System Ready — Database is at 0 Invoices</div>
          <p className="text-xs text-industrial-text-muted max-w-md mx-auto">
            Upload your CSV dataset via the Chat Copilot or click "Upload Dataset" above. Only your uploaded dataset will be audited and displayed.
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-2 bg-accent text-white text-xs font-medium hover:bg-accent/90 transition-colors flex items-center gap-1.5"
            >
              <Upload size={13} />
              <span>Upload CSV Dataset</span>
            </button>
            <button
              onClick={handleLoadDemo}
              className="px-4 py-2 border border-industrial-border text-industrial-text-muted text-xs hover:border-accent/40 hover:text-accent transition-colors flex items-center gap-1.5"
            >
              <RotateCcw size={13} />
              <span>Load 3,000 Demo Dataset</span>
            </button>
          </div>
        </div>
      )}

      {/* Stat Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatCard
            label="Auto-Passed"
            value={stats.auto_pass_count}
            total={stats.total_processed}
            colorClass="text-nominal-bright"
            icon={<CheckCircle size={18} />}
          />
          <StatCard
            label="Flagged"
            value={stats.flagged_count}
            total={stats.total_processed}
            colorClass="text-warning"
            icon={<AlertTriangle size={18} />}
          />
          <StatCard
            label="Needs Human Review"
            value={stats.needs_review_count}
            total={stats.total_processed}
            colorClass="text-error"
            icon={<Clock size={18} />}
          />
        </div>
      )}

      {/* Exception breakdown */}
      {stats && Object.keys(stats.breakdown).length > 0 && (
        <div className="bg-industrial-surface border border-industrial-border p-5">
          <h2 className="text-xs text-industrial-text-muted tracking-widest uppercase mb-4">Exception Breakdown</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {Object.entries(stats.breakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([rule, count]) => (
                <div key={rule} className="flex items-center justify-between py-2 border-b border-industrial-border">
                  <span className="text-xs text-industrial-text font-mono">{rule}</span>
                  <span className="text-sm font-mono font-bold text-warning">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Exception table */}
      <div className="bg-industrial-surface border border-industrial-border">
        <div className="flex items-center justify-between px-5 py-3 border-b border-industrial-border">
          <h2 className="text-sm font-semibold text-industrial-text tracking-wide">
            Exception Queue
            {exceptions.length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-[10px] bg-warning/10 text-warning border border-warning/30 font-mono">
                {exceptions.length}
              </span>
            )}
          </h2>
          <ChevronRight size={14} className="text-industrial-text-dim" />
        </div>

        {loading ? (
          <div className="px-5 py-12 text-center text-industrial-text-muted text-sm">Loading exceptions…</div>
        ) : exceptions.length === 0 ? (
          <div className="px-5 py-12 text-center text-industrial-text-muted text-sm">
            No exceptions awaiting review. 🎉
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-industrial-border">
                  {['Invoice ID', 'Vendor', 'Amount (₹)', 'Triggered', 'Reason', 'Status', 'Actions'].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-[10px] text-industrial-text-muted tracking-widest uppercase font-normal whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {exceptions.map((exc, i) => {
                  const isDup = exc.triggered_checks.includes('DUPLICATE');
                  const isExpanded = expandedId === exc.invoice_id;

                  return (
                    <React.Fragment key={exc.invoice_id}>
                      <tr className={`border-b border-industrial-border/50 hover:bg-industrial-graphite/50 transition-colors ${i % 2 === 1 ? 'bg-industrial-bg/50' : ''}`}>
                        <td className="px-4 py-3 font-mono text-accent text-xs">{exc.invoice_id}</td>
                        <td className="px-4 py-3 text-industrial-text text-xs max-w-[140px] truncate">{exc.vendor_name}</td>
                        <td className="px-4 py-3 font-mono text-industrial-text text-xs">
                          {exc.amount?.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-[10px] px-2 py-0.5 border font-mono whitespace-nowrap ${
                            isDup
                              ? 'text-warning bg-warning/15 border-warning/40 font-bold'
                              : 'text-warning bg-warning/10 border-warning/30'
                          }`}>
                            {exc.triggered_checks}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-industrial-text-muted text-xs max-w-[220px]">
                          <div className="flex flex-col gap-1">
                            <span className="block truncate" title={exc.reason_text}>{exc.reason_text}</span>
                            {isDup && (
                              <button
                                onClick={() => setExpandedId(isExpanded ? null : exc.invoice_id)}
                                className="text-[10px] text-accent hover:underline flex items-center gap-1 font-semibold text-left font-mono"
                              >
                                {isExpanded ? '▲ Hide Side-by-Side' : '⚡ View Side-by-Side'}
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3"><StatusTag status={exc.status} /></td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleDecision(exc.invoice_id, 'approve')}
                              disabled={actionLoading === exc.invoice_id}
                              className="px-3 py-1 text-[11px] bg-nominal/20 text-nominal-bright border border-nominal/40 hover:bg-nominal/30 disabled:opacity-40 transition-colors"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleDecision(exc.invoice_id, 'reject')}
                              disabled={actionLoading === exc.invoice_id}
                              className="px-3 py-1 text-[11px] bg-error/10 text-error border border-error/40 hover:bg-error/20 disabled:opacity-40 transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Side-by-side Evidence Card Sub-row */}
                      {isDup && isExpanded && (
                        <tr className="border-b border-industrial-border bg-industrial-graphite/30">
                          <td colSpan={7} className="px-6 py-3">
                            <DuplicateComparisonCard flaggedInvoice={exc} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
