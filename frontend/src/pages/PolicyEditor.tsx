import React, { useState, useEffect, useCallback } from 'react';
import {
  Sliders,
  Save,
  RotateCcw,
  Plus,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Code,
  ShieldAlert,
  Building,
  Users,
  Copy,
  Check
} from 'lucide-react';
import {
  fetchPolicyConfig,
  updatePolicyConfig,
  PolicyConfig,
} from '../services/api';

const DEFAULT_CONFIG: PolicyConfig = {
  categories: {
    "Office Supplies": { limit: 25000, po_required: false },
    "IT Equipment": { limit: 500000, po_required: true },
    "Travel": { limit: 60000, po_required: false },
    "Catering": { limit: 40000, po_required: false },
    "Logistics": { limit: 150000, po_required: true },
    "Professional Services": { limit: 1000000, po_required: true },
    "Facilities": { limit: 300000, po_required: true },
    "Marketing": { limit: 200000, po_required: false },
  },
  approval_ladder: [
    { role: "Team Manager", max_amount: 10000 },
    { role: "Department Head", max_amount: 100000 },
    { role: "Finance Controller", max_amount: 1000000 },
    { role: "CFO", max_amount: null },
  ],
  duplicate_matching: {
    fuzzy_similarity_threshold: 0.9,
    amount_tolerance_percent: 1,
    date_window_days: 7,
  },
  po_tolerance_percent: 5,
  confidence_threshold_auto_flag: 0.8,
};

const PolicyEditor: React.FC = () => {
  const [config, setConfig] = useState<PolicyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [copied, setCopied] = useState(false);

  // New category inline form state
  const [newCatName, setNewCatName] = useState('');
  const [newCatLimit, setNewCatLimit] = useState(50000);
  const [newCatPoReq, setNewCatPoReq] = useState(false);
  const [showAddCat, setShowAddCat] = useState(false);

  // New approval role inline form state
  const [newRoleName, setNewRoleName] = useState('');
  const [newRoleMax, setNewRoleMax] = useState<number | null>(250000);
  const [newRoleNoLimit, setNewRoleNoLimit] = useState(false);
  const [showAddRole, setShowAddRole] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setSaveError(null);
    try {
      const data = await fetchPolicyConfig();
      setConfig(data);
    } catch {
      setSaveError('Failed to fetch policy configuration from backend. Using local defaults.');
      setConfig(DEFAULT_CONFIG);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setSaveSuccess(null);
    setSaveError(null);
    try {
      const res = await updatePolicyConfig(config);
      setSaveSuccess(res.message || 'Policy rules successfully updated and reloaded in memory!');
      setTimeout(() => setSaveSuccess(null), 5000);
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Failed to save configuration.';
      setSaveError(detail);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (window.confirm('Reset all policy rules to system standard defaults?')) {
      setConfig(JSON.parse(JSON.stringify(DEFAULT_CONFIG)));
      setSaveSuccess('Reset to system defaults. Click "Save Changes" to apply.');
    }
  };

  // Category handlers
  const handleCategoryLimitChange = (cat: string, limitVal: number) => {
    if (!config) return;
    setConfig({
      ...config,
      categories: {
        ...config.categories,
        [cat]: { ...config.categories[cat], limit: Math.max(0, limitVal) },
      },
    });
  };

  const handleCategoryPoToggle = (cat: string) => {
    if (!config) return;
    setConfig({
      ...config,
      categories: {
        ...config.categories,
        [cat]: { ...config.categories[cat], po_required: !config.categories[cat].po_required },
      },
    });
  };

  const handleDeleteCategory = (cat: string) => {
    if (!config) return;
    const nextCats = { ...config.categories };
    delete nextCats[cat];
    setConfig({ ...config, categories: nextCats });
  };

  const handleAddCategory = () => {
    const trimmed = newCatName.trim();
    if (!trimmed || !config) return;
    if (config.categories[trimmed]) {
      alert(`Category "${trimmed}" already exists.`);
      return;
    }
    setConfig({
      ...config,
      categories: {
        ...config.categories,
        [trimmed]: { limit: Number(newCatLimit) || 0, po_required: newCatPoReq },
      },
    });
    setNewCatName('');
    setNewCatLimit(50000);
    setNewCatPoReq(false);
    setShowAddCat(false);
  };

  // Approval Ladder handlers
  const handleLadderAmountChange = (index: number, val: number | null) => {
    if (!config) return;
    const nextLadder = [...config.approval_ladder];
    nextLadder[index] = { ...nextLadder[index], max_amount: val !== null ? Math.max(0, val) : null };
    setConfig({ ...config, approval_ladder: nextLadder });
  };

  const handleDeleteRole = (index: number) => {
    if (!config) return;
    const nextLadder = config.approval_ladder.filter((_, i) => i !== index);
    setConfig({ ...config, approval_ladder: nextLadder });
  };

  const handleAddRole = () => {
    const trimmed = newRoleName.trim();
    if (!trimmed || !config) return;
    const nextLadder = [
      ...config.approval_ladder,
      { role: trimmed, max_amount: newRoleNoLimit ? null : Number(newRoleMax) || 0 },
    ];
    setConfig({ ...config, approval_ladder: nextLadder });
    setNewRoleName('');
    setNewRoleMax(250000);
    setNewRoleNoLimit(false);
    setShowAddRole(false);
  };

  // Tolerances handlers
  const handleDupConfigChange = (key: keyof PolicyConfig['duplicate_matching'], value: number) => {
    if (!config) return;
    setConfig({
      ...config,
      duplicate_matching: {
        ...config.duplicate_matching,
        [key]: value,
      },
    });
  };

  const copyJson = () => {
    if (!config) return;
    navigator.clipboard.writeText(JSON.stringify(config, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-16 text-center text-industrial-text-muted text-sm font-mono">
        Loading policy configuration from backend...
      </div>
    );
  }

  if (!config) return null;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Top Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-industrial-border">
        <div>
          <div className="flex items-center gap-2">
            <Sliders size={20} className="text-accent" />
            <h1 className="text-2xl font-bold tracking-tight text-industrial-text">Policy & Rules Configuration</h1>
          </div>
          <p className="text-xs text-industrial-text-muted mt-1">
            Visual editor for <code className="text-accent font-mono">policy_config.json</code>. Changes apply immediately in memory without server restart.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowJsonModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-industrial-border bg-industrial-surface text-xs text-industrial-text-muted hover:text-industrial-text hover:border-accent/40 transition-colors font-mono"
            title="Inspect raw JSON"
          >
            <Code size={14} />
            Raw JSON
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-industrial-border bg-industrial-surface text-xs text-industrial-text-muted hover:text-industrial-text hover:border-warning/40 transition-colors"
            title="Reset to default policies"
          >
            <RotateCcw size={14} />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2 bg-accent text-white text-xs font-semibold hover:bg-accent/90 transition-colors shadow-sm disabled:opacity-50"
          >
            <Save size={14} />
            {saving ? 'Saving Rules…' : 'Save & Apply Policies'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {saveSuccess && (
        <div className="p-3 border border-nominal-bright/40 bg-nominal/10 text-nominal-bright flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} />
            <span>{saveSuccess}</span>
          </div>
          <button onClick={() => setSaveSuccess(null)} className="text-nominal-bright/60 hover:text-nominal-bright">✕</button>
        </div>
      )}

      {saveError && (
        <div className="p-3 border border-error/40 bg-error/10 text-error flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>{saveError}</span>
          </div>
          <button onClick={() => setSaveError(null)} className="text-error/60 hover:text-error">✕</button>
        </div>
      )}

      {/* SECTION 1: Category Spend Limits & PO Mandates */}
      <section className="bg-industrial-surface border border-industrial-border p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-industrial-text flex items-center gap-2">
              <Building size={16} className="text-accent" />
              Category Spend Limits &amp; PO Requirements
            </h2>
            <p className="text-xs text-industrial-text-muted mt-0.5">
              Invoices exceeding a category limit trigger <code className="text-warning font-mono">OVER_LIMIT</code>. Missing POs trigger <code className="text-warning font-mono">MISSING_PO</code>.
            </p>
          </div>
          <button
            onClick={() => setShowAddCat(!showAddCat)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent border border-accent/40 bg-accent/10 hover:bg-accent/20 transition-colors font-mono"
          >
            <Plus size={13} />
            {showAddCat ? 'Cancel' : 'Add Category'}
          </button>
        </div>

        {/* Add Category Drawer */}
        {showAddCat && (
          <div className="p-4 bg-industrial-graphite/40 border border-accent/30 flex flex-wrap items-end gap-3 text-xs">
            <div className="flex-1 min-w-[180px]">
              <label className="block text-industrial-text-muted mb-1 uppercase tracking-wider text-[10px]">Category Name</label>
              <input
                type="text"
                placeholder="e.g. Cloud Hosting"
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                className="w-full bg-industrial-surface border border-industrial-border px-3 py-1.5 text-industrial-text focus:outline-none focus:border-accent"
              />
            </div>
            <div className="w-40">
              <label className="block text-industrial-text-muted mb-1 uppercase tracking-wider text-[10px]">Spend Limit (₹)</label>
              <input
                type="number"
                min="0"
                step="5000"
                value={newCatLimit}
                onChange={(e) => setNewCatLimit(Number(e.target.value))}
                className="w-full bg-industrial-surface border border-industrial-border px-3 py-1.5 font-mono text-industrial-text focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input
                type="checkbox"
                id="poReqCheckbox"
                checked={newCatPoReq}
                onChange={(e) => setNewCatPoReq(e.target.checked)}
                className="accent-accent cursor-pointer"
              />
              <label htmlFor="poReqCheckbox" className="text-industrial-text cursor-pointer">PO Required</label>
            </div>
            <button
              onClick={handleAddCategory}
              className="px-4 py-1.5 bg-accent text-white font-medium hover:bg-accent/90 transition-colors"
            >
              Add
            </button>
          </div>
        )}

        {/* Category Grid Table */}
        <div className="overflow-x-auto border border-industrial-border">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="bg-industrial-graphite/60 border-b border-industrial-border text-industrial-text-muted text-[10px] tracking-wider uppercase font-mono">
                <th className="py-2.5 px-4">Category</th>
                <th className="py-2.5 px-4">Spend Limit (₹)</th>
                <th className="py-2.5 px-4">PO Requirement</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-industrial-border">
              {Object.entries(config.categories).map(([catName, rule]) => (
                <tr key={catName} className="hover:bg-industrial-graphite/20 transition-colors">
                  <td className="py-2.5 px-4 font-medium text-industrial-text">
                    {catName}
                  </td>
                  <td className="py-2.5 px-4">
                    <div className="flex items-center gap-1.5 w-44">
                      <span className="text-industrial-text-dim font-mono">₹</span>
                      <input
                        type="number"
                        min="0"
                        step="5000"
                        value={rule.limit}
                        onChange={(e) => handleCategoryLimitChange(catName, Number(e.target.value))}
                        className="w-full bg-industrial-surface border border-industrial-border px-2 py-1 font-mono text-xs text-industrial-text focus:outline-none focus:border-accent"
                      />
                    </div>
                  </td>
                  <td className="py-2.5 px-4">
                    <button
                      type="button"
                      onClick={() => handleCategoryPoToggle(catName)}
                      className={`px-2.5 py-1 text-[11px] font-mono border transition-colors ${
                        rule.po_required
                          ? 'border-warning/50 bg-warning/15 text-warning font-semibold'
                          : 'border-industrial-border bg-industrial-surface text-industrial-text-muted hover:text-industrial-text'
                      }`}
                    >
                      {rule.po_required ? '✓ PO MANDATORY' : '— PO OPTIONAL'}
                    </button>
                  </td>
                  <td className="py-2.5 px-4 text-right">
                    <button
                      type="button"
                      onClick={() => handleDeleteCategory(catName)}
                      className="text-industrial-text-dim hover:text-error transition-colors p-1"
                      title="Remove category"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* SECTION 2: Approval Authority Ladder */}
      <section className="bg-industrial-surface border border-industrial-border p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-industrial-text flex items-center gap-2">
              <Users size={16} className="text-accent" />
              Approval Authority Hierarchy
            </h2>
            <p className="text-xs text-industrial-text-muted mt-0.5">
              Invoices signed off by approvers exceeding their threshold trigger <code className="text-warning font-mono">APPROVAL_MISMATCH</code>.
            </p>
          </div>
          <button
            onClick={() => setShowAddRole(!showAddRole)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent border border-accent/40 bg-accent/10 hover:bg-accent/20 transition-colors font-mono"
          >
            <Plus size={13} />
            {showAddRole ? 'Cancel' : 'Add Role'}
          </button>
        </div>

        {/* Add Role Drawer */}
        {showAddRole && (
          <div className="p-4 bg-industrial-graphite/40 border border-accent/30 flex flex-wrap items-end gap-3 text-xs">
            <div className="flex-1 min-w-[180px]">
              <label className="block text-industrial-text-muted mb-1 uppercase tracking-wider text-[10px]">Role / Designation</label>
              <input
                type="text"
                placeholder="e.g. Senior Director"
                value={newRoleName}
                onChange={(e) => setNewRoleName(e.target.value)}
                className="w-full bg-industrial-surface border border-industrial-border px-3 py-1.5 text-industrial-text focus:outline-none focus:border-accent"
              />
            </div>
            <div className="w-48">
              <label className="block text-industrial-text-muted mb-1 uppercase tracking-wider text-[10px]">Max Approval Limit (₹)</label>
              <input
                type="number"
                min="0"
                step="10000"
                disabled={newRoleNoLimit}
                value={newRoleNoLimit ? '' : (newRoleMax ?? '')}
                onChange={(e) => setNewRoleMax(Number(e.target.value))}
                placeholder={newRoleNoLimit ? 'No Limit (Unlimited)' : '250000'}
                className="w-full bg-industrial-surface border border-industrial-border px-3 py-1.5 font-mono text-industrial-text disabled:opacity-40 focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input
                type="checkbox"
                id="unlimitedCheckbox"
                checked={newRoleNoLimit}
                onChange={(e) => setNewRoleNoLimit(e.target.checked)}
                className="accent-accent cursor-pointer"
              />
              <label htmlFor="unlimitedCheckbox" className="text-industrial-text cursor-pointer">Unlimited (No Ceiling)</label>
            </div>
            <button
              onClick={handleAddRole}
              className="px-4 py-1.5 bg-accent text-white font-medium hover:bg-accent/90 transition-colors"
            >
              Add
            </button>
          </div>
        )}

        {/* Ladder Steps List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {config.approval_ladder.map((ladderItem, index) => {
            const isUnlimited = ladderItem.max_amount === null;

            return (
              <div
                key={ladderItem.role + index}
                className="p-3.5 border border-industrial-border bg-industrial-graphite/20 flex items-center justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-accent/20 text-accent flex items-center justify-center font-mono text-[10px] font-bold">
                      {index + 1}
                    </span>
                    <span className="font-semibold text-xs text-industrial-text">{ladderItem.role}</span>
                  </div>
                  <div className="text-[11px] font-mono text-industrial-text-muted pl-7">
                    Authority: {isUnlimited ? (
                      <span className="text-nominal-bright font-semibold">Unlimited (Top Authority)</span>
                    ) : (
                      <span className="text-accent font-semibold">Up to ₹{ladderItem.max_amount?.toLocaleString('en-IN')}</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {!isUnlimited ? (
                    <div className="flex items-center gap-1 w-32">
                      <span className="text-industrial-text-dim text-[11px] font-mono">₹</span>
                      <input
                        type="number"
                        min="0"
                        step="10000"
                        value={ladderItem.max_amount ?? ''}
                        onChange={(e) => handleLadderAmountChange(index, Number(e.target.value))}
                        className="w-full bg-industrial-surface border border-industrial-border px-2 py-0.5 font-mono text-xs text-industrial-text focus:outline-none focus:border-accent"
                      />
                    </div>
                  ) : (
                    <span className="text-[10px] font-mono text-industrial-text-dim px-2 py-1 bg-industrial-surface border border-industrial-border">
                      CEO / CFO
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => handleDeleteRole(index)}
                    className="text-industrial-text-dim hover:text-error transition-colors p-1"
                    title="Remove role"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* SECTION 3: Duplicate Matching Engine Tolerances */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-industrial-surface border border-industrial-border p-6 space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-industrial-text flex items-center gap-2">
              <ShieldAlert size={16} className="text-accent" />
              Duplicate Anomaly Tolerances
            </h2>
            <p className="text-xs text-industrial-text-muted mt-0.5">
              Governs exact and near-match duplicate invoice detection.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            {/* Fuzzy Similarity Threshold */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-industrial-text">
                <span>Vendor Fuzzy Similarity Cutoff</span>
                <span className="font-mono text-accent font-bold">
                  {(config.duplicate_matching.fuzzy_similarity_threshold * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                value={config.duplicate_matching.fuzzy_similarity_threshold}
                onChange={(e) =>
                  handleDupConfigChange('fuzzy_similarity_threshold', Number(e.target.value))
                }
                className="w-full accent-accent cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-industrial-text-dim font-mono">
                <span>50% (Loose)</span>
                <span>90% (Standard)</span>
                <span>100% (Exact Only)</span>
              </div>
            </div>

            {/* Amount Tolerance Percent */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-industrial-text">
                <span>Amount Difference Tolerance</span>
                <span className="font-mono text-accent font-bold">
                  ±{config.duplicate_matching.amount_tolerance_percent}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={config.duplicate_matching.amount_tolerance_percent}
                onChange={(e) =>
                  handleDupConfigChange('amount_tolerance_percent', Number(e.target.value))
                }
                className="w-full accent-accent cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-industrial-text-dim font-mono">
                <span>0% (Strict Exact)</span>
                <span>1% (Standard)</span>
                <span>10% (Wide)</span>
              </div>
            </div>

            {/* Date Window Days */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-industrial-text">
                <span>Duplicate Search Date Window</span>
                <span className="font-mono text-accent font-bold">
                  {config.duplicate_matching.date_window_days} Days
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="90"
                step="1"
                value={config.duplicate_matching.date_window_days}
                onChange={(e) =>
                  handleDupConfigChange('date_window_days', Number(e.target.value))
                }
                className="w-full accent-accent cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-industrial-text-dim font-mono">
                <span>1 Day</span>
                <span>7 Days (Default)</span>
                <span>90 Days (Quarter)</span>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 4: PO & Confidence Score Tolerances */}
        <section className="bg-industrial-surface border border-industrial-border p-6 space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-industrial-text flex items-center gap-2">
              <Sliders size={16} className="text-accent" />
              General Audit Tolerances
            </h2>
            <p className="text-xs text-industrial-text-muted mt-0.5">
              Thresholds for PO variances and automatic risk classification.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            {/* PO Tolerance Percent */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-industrial-text">
                <span>PO Amount Mismatch Tolerance</span>
                <span className="font-mono text-accent font-bold">
                  ±{config.po_tolerance_percent}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="20"
                step="1"
                value={config.po_tolerance_percent}
                onChange={(e) => setConfig({ ...config, po_tolerance_percent: Number(e.target.value) })}
                className="w-full accent-accent cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-industrial-text-dim font-mono">
                <span>0% (Zero Variance)</span>
                <span>5% (Default)</span>
                <span>20% (High Variance)</span>
              </div>
              <p className="text-[11px] text-industrial-text-dim leading-relaxed">
                Invoices differing from PO amount by more than this threshold trigger <code className="text-warning font-mono">PO_AMOUNT_MISMATCH</code>.
              </p>
            </div>

            {/* Confidence Threshold Auto-Flag */}
            <div className="space-y-1.5 pt-2">
              <div className="flex justify-between text-industrial-text">
                <span>Auto-Flagging Confidence Threshold</span>
                <span className="font-mono text-accent font-bold">
                  {(config.confidence_threshold_auto_flag * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="1.0"
                step="0.05"
                value={config.confidence_threshold_auto_flag}
                onChange={(e) =>
                  setConfig({ ...config, confidence_threshold_auto_flag: Number(e.target.value) })
                }
                className="w-full accent-accent cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-industrial-text-dim font-mono">
                <span>50%</span>
                <span>80% (Default)</span>
                <span>100%</span>
              </div>
              <p className="text-[11px] text-industrial-text-dim leading-relaxed">
                Violations evaluated above this confidence level are marked for high-priority auditor inspection.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* Raw JSON Modal */}
      {showJsonModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-industrial-surface border border-industrial-border w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">
            <div className="px-5 py-3 border-b border-industrial-border flex items-center justify-between">
              <span className="text-xs font-mono text-industrial-text font-semibold flex items-center gap-2">
                <Code size={14} className="text-accent" />
                backend/data/policy_config.json
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyJson}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs font-mono text-industrial-text-muted hover:text-accent border border-industrial-border hover:border-accent transition-colors"
                >
                  {copied ? <Check size={12} className="text-nominal-bright" /> : <Copy size={12} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                <button
                  onClick={() => setShowJsonModal(false)}
                  className="text-industrial-text-dim hover:text-industrial-text text-sm font-mono px-2"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="p-4 overflow-y-auto flex-1 bg-industrial-graphite/40">
              <pre className="text-xs font-mono text-industrial-text leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(config, null, 2)}
              </pre>
            </div>
            <div className="px-5 py-3 border-t border-industrial-border flex justify-end">
              <button
                onClick={() => setShowJsonModal(false)}
                className="px-4 py-1.5 bg-industrial-surface border border-industrial-border text-xs text-industrial-text hover:border-accent transition-colors font-mono"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PolicyEditor;
