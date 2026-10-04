import React from 'react';
import { Copy, AlertTriangle, CheckCircle2, ArrowRightLeft } from 'lucide-react';
import { InvoiceException } from '../services/api';

interface DuplicateComparisonCardProps {
  flaggedInvoice: InvoiceException;
}

export const DuplicateComparisonCard: React.FC<DuplicateComparisonCardProps> = ({
  flaggedInvoice,
}) => {
  const isDuplicate =
    flaggedInvoice.triggered_checks.includes('DUPLICATE') ||
    flaggedInvoice.triggered_checks.includes('EXACT_DUPLICATE') ||
    flaggedInvoice.triggered_checks.includes('FUZZY_DUPLICATE');

  if (!isDuplicate) {
    return (
      <div className="text-xs text-industrial-text-muted leading-relaxed">
        {flaggedInvoice.reason_text}
      </div>
    );
  }

  // Parse details from reason text and matched_invoice
  const matched = flaggedInvoice.matched_invoice;
  const reason = flaggedInvoice.reason_text || '';
  const isExact = flaggedInvoice.triggered_checks.includes('EXACT_DUPLICATE');

  // Parse fallback matched vendor and amount from reason if not in matched_invoice
  let matchedVendor = matched?.vendor_name || '';
  let matchedAmount = matched?.amount ? Number(matched.amount) : null;
  let matchedCategory = matched?.category || flaggedInvoice.category;
  let matchedId = flaggedInvoice.matched_reference || matched?.invoice_id || 'Reference Record';
  let daysApart = '—';
  let similarityStr = isExact ? '100%' : 'Fuzzy Match';

  // Extract from reason if needed: e.g. "same vendor ('XYZ')", "vendor similarity 94% ('ABC' vs 'XYZ')"
  const simMatch = reason.match(/vendor similarity (\d+)%/i);
  if (simMatch) {
    similarityStr = `${simMatch[1]}%`;
  }
  const daysMatch = reason.match(/(\d+)\s+day\(s\)\s+apart/i);
  if (daysMatch) {
    daysApart = `${daysMatch[1]} days apart`;
  }

  const fuzzyVendorMatch = reason.match(/'([^']+)'\s+vs\s+'([^']+)'/i);
  if (fuzzyVendorMatch) {
    matchedVendor = matchedVendor || fuzzyVendorMatch[2];
  } else {
    const exactVendorMatch = reason.match(/same vendor \('([^']+)'\)/i);
    if (exactVendorMatch) {
      matchedVendor = matchedVendor || exactVendorMatch[1];
    }
  }

  const amtDiffMatch = reason.match(/₹([\d,.]+)\s+vs\s+₹([\d,.]+)/i);
  if (amtDiffMatch) {
    const parsedAmt = parseFloat(amtDiffMatch[2].replace(/,/g, ''));
    if (!isNaN(parsedAmt)) matchedAmount = parsedAmt;
  } else {
    if (isExact && matchedAmount === null) {
      matchedAmount = flaggedInvoice.amount;
    }
  }

  if (!matchedVendor) {
    matchedVendor = flaggedInvoice.vendor_name;
  }

  // Field match calculations
  const vendorMatches = flaggedInvoice.vendor_name.trim().toLowerCase() === matchedVendor.trim().toLowerCase();
  const amountDiff = matchedAmount !== null ? Math.abs(flaggedInvoice.amount - matchedAmount) : 0;
  const amountMatches = amountDiff < 0.01;
  const categoryMatches = flaggedInvoice.category.trim().toLowerCase() === matchedCategory.trim().toLowerCase();

  return (
    <div className="bg-industrial-bg border border-industrial-border p-4 my-2 text-xs font-mono space-y-3">
      {/* Banner */}
      <div className="flex items-center justify-between border-b border-industrial-border pb-2">
        <div className="flex items-center gap-2 text-warning font-semibold tracking-wider uppercase text-[11px]">
          <AlertTriangle size={14} />
          <span>
            {isExact ? 'Exact Duplicate Evidence Comparison' : 'Fuzzy Duplicate Evidence Comparison'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 bg-warning/10 text-warning border border-warning/30">
            {similarityStr} Vendor Similarity
          </span>
          {daysApart !== '—' && (
            <span className="text-[10px] px-2 py-0.5 bg-industrial-graphite text-industrial-text-muted border border-industrial-border">
              {daysApart}
            </span>
          )}
        </div>
      </div>

      {/* Side-by-Side Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left Column: Flagged Invoice */}
        <div className="bg-industrial-surface border border-industrial-border p-3 space-y-2">
          <div className="flex items-center justify-between text-accent font-bold border-b border-industrial-border pb-1.5">
            <span className="flex items-center gap-1.5">
              <Copy size={12} />
              Current Flagged Invoice
            </span>
            <span className="text-industrial-text">{flaggedInvoice.invoice_id}</span>
          </div>

          <div className="space-y-1.5 pt-1">
            <div className="flex justify-between items-center">
              <span className="text-industrial-text-dim text-[11px]">Vendor:</span>
              <span
                className={`px-2 py-0.5 text-[11px] truncate max-w-[200px] ${
                  vendorMatches
                    ? 'bg-nominal/10 text-nominal-bright border border-nominal/30'
                    : 'bg-warning/10 text-warning border border-warning/30'
                }`}
                title={flaggedInvoice.vendor_name}
              >
                {flaggedInvoice.vendor_name}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-industrial-text-dim text-[11px]">Amount:</span>
              <span
                className={`px-2 py-0.5 text-[11px] font-bold ${
                  amountMatches
                    ? 'bg-nominal/10 text-nominal-bright border border-nominal/30'
                    : 'bg-warning/10 text-warning border border-warning/30'
                }`}
              >
                ₹{flaggedInvoice.amount?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-industrial-text-dim text-[11px]">Category:</span>
              <span
                className={`px-2 py-0.5 text-[11px] ${
                  categoryMatches
                    ? 'bg-nominal/10 text-nominal-bright border border-nominal/30'
                    : 'bg-warning/10 text-warning border border-warning/30'
                }`}
              >
                {flaggedInvoice.category}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Matched Reference Invoice */}
        <div className="bg-industrial-surface border border-industrial-border p-3 space-y-2">
          <div className="flex items-center justify-between text-nominal-bright font-bold border-b border-industrial-border pb-1.5">
            <span className="flex items-center gap-1.5">
              <ArrowRightLeft size={12} />
              Matched Prior Record
            </span>
            <span className="text-industrial-text">{matchedId}</span>
          </div>

          <div className="space-y-1.5 pt-1">
            <div className="flex justify-between items-center">
              <span className="text-industrial-text-dim text-[11px]">Vendor:</span>
              <span
                className={`px-2 py-0.5 text-[11px] truncate max-w-[200px] ${
                  vendorMatches
                    ? 'bg-nominal/10 text-nominal-bright border border-nominal/30'
                    : 'bg-warning/10 text-warning border border-warning/30'
                }`}
                title={matchedVendor}
              >
                {matchedVendor}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-industrial-text-dim text-[11px]">Amount:</span>
              <span
                className={`px-2 py-0.5 text-[11px] font-bold ${
                  amountMatches
                    ? 'bg-nominal/10 text-nominal-bright border border-nominal/30'
                    : 'bg-warning/10 text-warning border border-warning/30'
                }`}
              >
                {matchedAmount !== null
                  ? `₹${matchedAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                  : '—'}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-industrial-text-dim text-[11px]">Category:</span>
              <span
                className={`px-2 py-0.5 text-[11px] ${
                  categoryMatches
                    ? 'bg-nominal/10 text-nominal-bright border border-nominal/30'
                    : 'bg-warning/10 text-warning border border-warning/30'
                }`}
              >
                {matchedCategory}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Audit Explanation Banner */}
      <div className="bg-industrial-graphite/40 border border-industrial-border/60 p-2.5 text-[11px] text-industrial-text-muted leading-relaxed flex items-start gap-2">
        <CheckCircle2 size={13} className="text-nominal-bright flex-shrink-0 mt-0.5" />
        <div>
          <span className="text-industrial-text font-semibold">Audit Finding: </span>
          {reason}
        </div>
      </div>
    </div>
  );
};
