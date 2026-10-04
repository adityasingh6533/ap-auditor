import React, { useEffect, useState, useCallback } from 'react';
import { RefreshCw, CheckCircle, AlertTriangle, Clock, ChevronRight, Download } from 'lucide-react';
import { fetchStats, fetchExceptions, submitDecision, downloadReport, StatsResponse, InvoiceException } from '../services/api';
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
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, e] = await Promise.all([fetchStats(), fetchExceptions(100)]);
      setStats(s);
      setExceptions(e);
    } catch {
      setError('Failed to connect to backend at http://localhost:8000. Make sure uvicorn is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDecision = useCallback(async (invoiceId: string, decision: 'approve' | 'reject') => {
    setActionLoading(invoiceId);
    try {
      await submitDecision(invoiceId, decision, 'Dashboard User');
      setExceptions((prev) => prev.filter((e) => e.invoice_id !== invoiceId));
    } catch {
      // silently ignore — in a production system we'd show a toast
    } finally {
      setActionLoading(null);
    }
  }, []);

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

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-industrial-text tracking-tight">Audit Dashboard</h1>
          <p className="text-sm text-industrial-text-muted mt-1">Real-time compliance overview from the AP rules engine</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => handleExport('pdf')}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-2 border border-accent/40 bg-accent/10 text-sm font-medium text-accent hover:bg-accent/20 transition-colors disabled:opacity-50"
            title="Download executive PDF exception summary"
          >
            <Download size={14} className={exporting ? 'animate-bounce' : ''} />
            {exporting ? 'Exporting...' : 'Export Report (PDF)'}
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 border border-industrial-border text-sm text-industrial-text-muted hover:border-accent/50 hover:text-accent transition-colors"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-error/40 bg-error/10 text-error text-sm px-4 py-3">
          {error}
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
