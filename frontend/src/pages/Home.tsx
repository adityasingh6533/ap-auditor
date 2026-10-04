import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Paperclip, Bot, User, AlertTriangle, CheckCircle, Clock, BarChart2, Cpu, Sparkles } from 'lucide-react';
import { sendChatMessage, uploadInvoiceCSV, ChatResponse, InvoiceException, fetchChatStatus, ChatStatusResponse } from '../services/api';


// ── Types ──────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  intent?: string;
  data?: Record<string, unknown> | null;
  timestamp: Date;
}

// ── Inline data renderers ──────────────────────────────────────────────────

const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const map: Record<string, string> = {
    NEEDS_HUMAN_REVIEW: 'bg-warning/10 text-warning border-warning/40',
    FLAGGED_AUTO:       'bg-error/10 text-error border-error/40',
    AUTO_PASS:          'bg-nominal/20 text-nominal-bright border-nominal/40',
    HUMAN_APPROVED:     'bg-nominal/20 text-nominal-bright border-nominal/40',
    HUMAN_REJECTED:     'bg-error/10 text-error border-error/40',
  };
  const cls = map[status] ?? 'bg-industrial-graphite text-industrial-text-muted border-industrial-border';
  return (
    <span className={`px-2 py-0.5 text-[10px] font-semibold tracking-widest uppercase border ${cls}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
};

const ExceptionCards: React.FC<{ exceptions: InvoiceException[] }> = ({ exceptions }) => (
  <div className="mt-3 space-y-2">
    {exceptions.map((exc) => (
      <div key={exc.invoice_id} className="bg-industrial-surface border border-industrial-border p-3 text-sm">
        <div className="flex items-center justify-between mb-1">
          <span className="font-mono text-accent font-semibold">{exc.invoice_id}</span>
          <StatusPill status={exc.status} />
        </div>
        <div className="text-industrial-text-muted text-xs mb-1">{exc.vendor_name}</div>
        <div className="flex gap-4 text-xs text-industrial-text-muted">
          <span>₹{exc.amount?.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
          <span className="text-warning">{exc.triggered_checks}</span>
        </div>
        {exc.reason_text && (
          <div className="mt-2 text-xs text-industrial-text-muted border-t border-industrial-border pt-2 leading-relaxed">
            {exc.reason_text}
          </div>
        )}
      </div>
    ))}
  </div>
);

const StatsBlock: React.FC<{ stats: { total_processed: number; auto_pass_count: number; flagged_count: number; needs_review_count: number; breakdown?: Record<string, number> } }> = ({ stats }) => (
  <div className="mt-3 grid grid-cols-3 gap-2">
    {[
      { label: 'Auto-Passed', value: stats.auto_pass_count, color: 'text-nominal-bright' },
      { label: 'Flagged', value: stats.flagged_count, color: 'text-warning' },
      { label: 'Needs Review', value: stats.needs_review_count, color: 'text-error' },
    ].map((s) => (
      <div key={s.label} className="bg-industrial-surface border border-industrial-border p-3 text-center">
        <div className={`text-2xl font-bold font-mono ${s.color}`}>{s.value.toLocaleString()}</div>
        <div className="text-[10px] text-industrial-text-muted tracking-wider uppercase mt-1">{s.label}</div>
      </div>
    ))}
  </div>
);

const InvoiceDetail: React.FC<{ invoice: Record<string, unknown> }> = ({ invoice }) => (
  <div className="mt-3 bg-industrial-surface border border-accent/30 p-3 text-sm space-y-1">
    <div className="flex justify-between items-start">
      <span className="font-mono text-accent font-semibold">{invoice.invoice_id as string}</span>
      <StatusPill status={invoice.status as string} />
    </div>
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-industrial-text-muted mt-2">
      <span>Vendor</span><span className="text-industrial-text">{invoice.vendor_name as string}</span>
      <span>Amount</span><span className="text-industrial-text">₹{(invoice.amount as number)?.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
      <span>Category</span><span className="text-industrial-text">{invoice.category as string}</span>
      <span>Triggered</span><span className="text-warning">{invoice.triggered_checks as string || '—'}</span>
      <span>Confidence</span><span className="text-industrial-text">{((invoice.confidence_score as number) * 100).toFixed(1)}%</span>
    </div>
    {(invoice.reason_text as string) && (
      <div className="mt-2 text-xs text-industrial-text-muted border-t border-industrial-border pt-2 leading-relaxed">
        {invoice.reason_text as string}
      </div>
    )}
  </div>
);

const DataRenderer: React.FC<{ intent: string; data: Record<string, unknown> }> = ({ intent, data }) => {
  if ((intent === 'SHOW_STATS' || intent === 'CHECK_STATUS') && data.stats) {
    return <StatsBlock stats={data.stats as any} />;
  }
  if (intent === 'SHOW_FLAGGED' && Array.isArray(data.exceptions)) {
    return <ExceptionCards exceptions={data.exceptions as InvoiceException[]} />;
  }
  if (intent === 'EXPLAIN_INVOICE' && data.invoice) {
    return <InvoiceDetail invoice={data.invoice as Record<string, unknown>} />;
  }
  return null;
};

// ── Upload summary card ────────────────────────────────────────────────────

const UploadSummaryCard: React.FC<{ summary: { total: number; auto_pass_count: number; flagged_count: number; needs_review_count: number } }> = ({ summary }) => (
  <div className="mt-3 border border-accent/30 bg-industrial-surface p-3 text-sm">
    <div className="text-xs text-industrial-text-muted mb-2 tracking-wider uppercase">Upload Complete — {summary.total} invoices processed</div>
    <div className="grid grid-cols-3 gap-2">
      {[
        { label: 'Passed', value: summary.auto_pass_count, color: 'text-nominal-bright' },
        { label: 'Flagged', value: summary.flagged_count, color: 'text-warning' },
        { label: 'Review', value: summary.needs_review_count, color: 'text-error' },
      ].map((s) => (
        <div key={s.label} className="text-center bg-industrial-graphite p-2">
          <div className={`text-xl font-mono font-bold ${s.color}`}>{s.value}</div>
          <div className="text-[10px] text-industrial-text-muted uppercase tracking-wider">{s.label}</div>
        </div>
      ))}
    </div>
  </div>
);

// ── Message Bubble ─────────────────────────────────────────────────────────

const MessageBubble: React.FC<{ msg: Message }> = ({ msg }) => {
  const isUser = msg.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 flex items-center justify-center border ${
        isUser
          ? 'bg-accent/20 border-accent/50 text-accent'
          : 'bg-industrial-surface border-industrial-border text-industrial-text-muted'
      }`}>
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-accent text-white'
            : 'bg-industrial-surface border border-industrial-border text-industrial-text'
        }`}>
          <pre className="whitespace-pre-wrap font-sans">{msg.text}</pre>
        </div>

        {/* Inline structured data */}
        {!isUser && msg.intent && msg.data && (
          <div className="w-full max-w-lg">
            <DataRenderer intent={msg.intent} data={msg.data} />
          </div>
        )}

        <span className="text-[10px] text-industrial-text-dim mt-1 px-1">
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
};

// ── Typing indicator ───────────────────────────────────────────────────────

const TypingIndicator: React.FC = () => (
  <div className="flex gap-3">
    <div className="w-8 h-8 flex items-center justify-center bg-industrial-surface border border-industrial-border text-industrial-text-muted flex-shrink-0">
      <Bot size={14} />
    </div>
    <div className="bg-industrial-surface border border-industrial-border px-4 py-3 flex items-center gap-1.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse"
          style={{ animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  </div>
);

// ── Suggested prompts ──────────────────────────────────────────────────────

const SUGGESTIONS = [
  { icon: BarChart2, label: 'Summary', prompt: 'give me a summary' },
  { icon: AlertTriangle, label: 'Flagged invoices', prompt: 'show me flagged invoices' },
  { icon: CheckCircle, label: 'Explain INV-3918', prompt: 'why was INV-3918 flagged' },
  { icon: Clock, label: 'Audit logs', prompt: 'how many duplicates were found' },
];

// ── Main Page ──────────────────────────────────────────────────────────────

const Home: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Hello! I\'m your AP Auditor Copilot. I can help you review invoices, check exceptions, approve or reject flagged items, and summarise your audit metrics.\n\nTry asking: "show me flagged invoices" or "give me a summary".',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatStatus, setChatStatus] = useState<ChatStatusResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await fetchChatStatus();
      setChatStatus(s);
    } catch {
      // Backend may be starting
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const addMessage = useCallback((role: 'user' | 'assistant', text: string, extras?: Partial<Message>) => {
    const msg: Message = {
      id: `${Date.now()}-${Math.random()}`,
      role,
      text,
      timestamp: new Date(),
      ...extras,
    };
    setMessages((prev) => [...prev, msg]);
  }, []);

  const handleSend = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput('');
    addMessage('user', msg);
    setLoading(true);
    try {
      const res: ChatResponse = await sendChatMessage(msg);
      addMessage('assistant', res.reply, { intent: res.intent, data: res.data });
      refreshStatus();
    } catch {
      addMessage('assistant', 'Sorry, I couldn\'t reach the AP Auditor backend. Please make sure the server is running on http://localhost:8000.');
    } finally {
      setLoading(false);
    }
  }, [input, loading, addMessage, refreshStatus]);

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    addMessage('user', `📎 Uploading: ${file.name}`);
    setLoading(true);
    try {
      const summary = await uploadInvoiceCSV(file);
      const text = `File processed successfully. ${summary.total} invoices analysed.`;
      const msg: Message = {
        id: `${Date.now()}`,
        role: 'assistant',
        text,
        timestamp: new Date(),
        intent: '__UPLOAD__',
        data: summary as unknown as Record<string, unknown>,
      };
      setMessages((prev) => [...prev, msg]);
    } catch {
      addMessage('assistant', 'Upload failed. Please check the file is a valid CSV.');
    } finally {
      setLoading(false);
    }
  }, [addMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Engine Status Top Bar */}
      <div className="px-4 py-2 border-b border-industrial-border bg-industrial-surface/80 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-accent" />
          <span className="font-semibold text-industrial-text">AP Auditor Copilot</span>
        </div>
        <div className="flex items-center gap-3">
          {chatStatus ? (
            chatStatus.api_key_configured && chatStatus.gemini_ready ? (
              <span className="flex items-center gap-1.5 px-2 py-0.5 border border-nominal-bright/40 bg-nominal/10 text-nominal-bright rounded-none text-[11px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-nominal-bright animate-pulse" />
                <Sparkles size={11} />
                Gemini 2.0 Flash (Tier 2 Active)
              </span>
            ) : (
              <span
                title="Paste your Gemini key into backend/.env to enable conversational AI"
                className="flex items-center gap-1.5 px-2 py-0.5 border border-warning/40 bg-warning/10 text-warning rounded-none text-[11px] font-mono cursor-help"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                <Cpu size={11} />
                Tier 1 Rules Engine Active • Gemini Key Pending in backend/.env
              </span>
            )
          ) : (
            <span className="text-[11px] font-mono text-industrial-text-muted">Connecting...</span>
          )}
        </div>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 min-h-0">
        {messages.map((msg) => {
          if (msg.intent === '__UPLOAD__' && msg.data) {
            return (
              <div key={msg.id} className="flex gap-3">
                <div className="w-8 h-8 flex items-center justify-center bg-industrial-surface border border-industrial-border text-industrial-text-muted flex-shrink-0">
                  <Bot size={14} />
                </div>
                <div className="flex flex-col">
                  <div className="px-4 py-3 text-sm bg-industrial-surface border border-industrial-border text-industrial-text">
                    {msg.text}
                  </div>
                  <UploadSummaryCard summary={msg.data as any} />
                  <span className="text-[10px] text-industrial-text-dim mt-1 px-1">
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            );
          }
          return <MessageBubble key={msg.id} msg={msg} />;
        })}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Suggestion chips — only show when just the welcome message */}
      {messages.length === 1 && (
        <div className="px-4 pb-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map(({ icon: Icon, label, prompt }) => (
            <button
              key={label}
              onClick={() => handleSend(prompt)}
              className="flex items-center gap-2 px-3 py-1.5 text-xs text-industrial-text-muted border border-industrial-border bg-industrial-surface hover:border-accent/50 hover:text-accent transition-colors"
            >
              <Icon size={12} />
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="px-4 pb-4 pt-2 border-t border-industrial-border bg-industrial-bg">
        <div className="flex items-end gap-2 bg-industrial-surface border border-industrial-border p-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask about invoices, exceptions, approvals…"
            className="flex-1 resize-none bg-transparent text-sm text-industrial-text placeholder-industrial-text-dim outline-none py-1.5 px-2 max-h-32 overflow-y-auto"
            style={{ lineHeight: '1.5' }}
          />
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Upload CSV"
            className="p-2 text-industrial-text-muted hover:text-accent transition-colors flex-shrink-0"
          >
            <Paperclip size={16} />
          </button>
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="p-2 bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-[10px] text-industrial-text-dim mt-1.5 px-2">
          Press Enter to send · Shift+Enter for new line · Attach a CSV with <Paperclip className="inline" size={9} />
        </p>
      </div>
    </div>
  );
};

export default Home;
