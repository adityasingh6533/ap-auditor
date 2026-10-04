import React, { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Search, ShieldCheck, CheckCircle2, AlertOctagon } from 'lucide-react';
import { fetchAuditLogs, verifyAuditLogs, AuditLogEntry, AuditVerifyResponse } from '../services/api';

const ACTION_STYLES: Record<string, string> = {
  AUTO_PASS:          'text-nominal-bright bg-nominal/10 border-nominal/30',
  FLAGGED_AUTO:       'text-warning bg-warning/10 border-warning/30',
  NEEDS_HUMAN_REVIEW: 'text-warning bg-warning/10 border-warning/30',
  HUMAN_APPROVED:     'text-nominal-bright bg-nominal/10 border-nominal/30',
  HUMAN_REJECTED:     'text-error bg-error/10 border-error/30',
};

const ActionBadge: React.FC<{ action: string }> = ({ action }) => (
  <span className={`px-2 py-0.5 text-[10px] font-semibold tracking-widest uppercase border whitespace-nowrap font-mono ${ACTION_STYLES[action] ?? 'text-industrial-text-muted border-industrial-border'}`}>
    {action.replace(/_/g, ' ')}
  </span>
);

const AuditLog: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [filtered, setFiltered] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [verifyResult, setVerifyResult] = useState<AuditVerifyResponse | null>(null);
  const [verifying, setVerifying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLogs(200);
      setLogs(data);
      setFiltered(data);
    } catch {
      setError('Failed to load audit logs from http://localhost:8000. Make sure the server is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await verifyAuditLogs();
      setVerifyResult(res);
    } catch {
      setError('Integrity verification check failed to execute.');
    } finally {
      setVerifying(false);
    }
  };

  useEffect(() => {
    const q = search.toLowerCase();
    if (!q) {
      setFiltered(logs);
    } else {
      setFiltered(logs.filter((l) =>
        l.invoice_id.toLowerCase().includes(q) ||
        l.action.toLowerCase().includes(q) ||
        l.performed_by.toLowerCase().includes(q) ||
        l.reason.toLowerCase().includes(q) ||
        (l.integrity_hash && l.integrity_hash.toLowerCase().includes(q))
      ));
    }
  }, [search, logs]);

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
      });
    } catch {
      return ts;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-industrial-text tracking-tight">Audit Log</h1>
          <p className="text-sm text-industrial-text-muted mt-1">
            Cryptographically sealed, append-only audit trail
            {logs.length > 0 && <span className="ml-2 text-industrial-text-dim">({logs.length} entries)</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="flex items-center gap-2 px-4 py-2 border border-nominal/40 bg-nominal/10 text-sm font-medium text-nominal-bright hover:bg-nominal/20 transition-colors disabled:opacity-50"
            title="Recompute and verify SHA-256 signatures for all database rows"
          >
            <ShieldCheck size={15} className={verifying ? 'animate-pulse' : ''} />
            {verifying ? 'Checking Hashes…' : 'Verify Integrity'}
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

      {/* Cryptographic Verification Status Banner */}
      {verifyResult && (
        <div className={`border p-4 flex items-center justify-between text-sm ${
          verifyResult.status === 'ALL_CLEAN'
            ? 'border-nominal/40 bg-nominal/10 text-nominal-bright'
            : 'border-error/40 bg-error/10 text-error'
        }`}>
          <div className="flex items-center gap-3">
            {verifyResult.status === 'ALL_CLEAN' ? (
              <CheckCircle2 size={20} className="text-nominal-bright flex-shrink-0" />
            ) : (
              <AlertOctagon size={20} className="text-error flex-shrink-0" />
            )}
            <div>
              <div className="font-semibold tracking-wide">
                {verifyResult.status === 'ALL_CLEAN'
                  ? `IMMUTABILITY CONFIRMED: ALL ${verifyResult.total_records_checked.toLocaleString()} RECORDS VERIFIED`
                  : `TAMPERING DETECTED: ${verifyResult.tampered_count} RECORD(S) CORRUPTED`}
              </div>
              <div className="text-xs opacity-90 mt-0.5">{verifyResult.message}</div>
            </div>
          </div>
          <button
            onClick={() => setVerifyResult(null)}
            className="text-xs underline opacity-70 hover:opacity-100"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="border border-error/40 bg-error/10 text-error text-sm px-4 py-3">
          {error}
        </div>
      )}

      {/* Search */}
      <div className="flex items-center gap-2 bg-industrial-surface border border-industrial-border px-3 py-2">
        <Search size={14} className="text-industrial-text-muted flex-shrink-0" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by invoice ID, action, operator, reason, or hash…"
          className="flex-1 bg-transparent text-sm text-industrial-text placeholder-industrial-text-dim outline-none"
        />
      </div>

      {/* Table */}
      <div className="bg-industrial-surface border border-industrial-border">
        {loading ? (
          <div className="px-5 py-12 text-center text-industrial-text-muted text-sm">Loading audit trail…</div>
        ) : filtered.length === 0 ? (
          <div className="px-5 py-12 text-center text-industrial-text-muted text-sm">No matching log entries found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-industrial-border">
                  {['Log ID', 'Timestamp', 'Invoice ID', 'Action', 'Performed By', 'Reason', 'SHA-256 Fingerprint'].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-[10px] text-industrial-text-muted tracking-widest uppercase font-normal whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((log, i) => (
                  <tr
                    key={log.log_id}
                    className={`border-b border-industrial-border/50 hover:bg-industrial-graphite/40 transition-colors ${i % 2 === 1 ? 'bg-industrial-bg/30' : ''}`}
                  >
                    <td className="px-4 py-3 font-mono text-industrial-text-dim text-xs">#{log.log_id}</td>
                    <td className="px-4 py-3 text-industrial-text-muted text-xs whitespace-nowrap font-mono">
                      {formatTime(log.timestamp)}
                    </td>
                    <td className="px-4 py-3 font-mono text-accent text-xs">{log.invoice_id}</td>
                    <td className="px-4 py-3"><ActionBadge action={log.action} /></td>
                    <td className="px-4 py-3 text-industrial-text-muted text-xs">{log.performed_by}</td>
                    <td className="px-4 py-3 text-industrial-text-muted text-xs max-w-[260px]">
                      <span className="block truncate" title={log.reason}>{log.reason || '—'}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-industrial-text-dim">
                      {log.integrity_hash ? (
                        <span className="text-nominal-bright/80 bg-nominal/10 px-1.5 py-0.5 border border-nominal/20" title={log.integrity_hash}>
                          {log.integrity_hash.slice(0, 10)}…{log.integrity_hash.slice(-6)}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditLog;
