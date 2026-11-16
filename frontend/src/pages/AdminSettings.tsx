import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { RuleConfig } from '../types';
import {
  Sliders,
  History,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Clock,
  Save,
  RotateCcw
} from 'lucide-react';

export const AdminSettings: React.FC = () => {
  const [config, setConfig] = useState<RuleConfig | null>(null);
  const [history, setHistory] = useState<RuleConfig[]>([]);
  const [priceTolPct, setPriceTolPct] = useState('0.00');
  const [priceTolAbs, setPriceTolAbs] = useState('0.00');
  const [qtyTolPct, setQtyTolPct] = useState('0.00');
  const [duplicateDays, setDuplicateDays] = useState(90);
  const [fuzzyThreshold, setFuzzyThreshold] = useState(85);
  const [highThreshold, setHighThreshold] = useState('500.00');
  const [critThreshold, setCritThreshold] = useState('2500.00');
  const [requireGrn, setRequireGrn] = useState(true);
  const [changeReason, setChangeReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    try {
      setLoading(true);
      const [currRes, histRes] = await Promise.all([
        apiClient.get('/admin/rule-config'),
        apiClient.get('/admin/rule-config/history'),
      ]);
      const c: RuleConfig = currRes.data;
      setConfig(c);
      setHistory(histRes.data);

      setPriceTolPct(String(c.price_variance_tolerance_pct));
      setPriceTolAbs(String(c.price_variance_tolerance_abs));
      setQtyTolPct(String(c.quantity_variance_tolerance_pct));
      setDuplicateDays(c.duplicate_window_days);
      setFuzzyThreshold(c.fuzzy_match_threshold);
      setHighThreshold(String(c.high_severity_threshold));
      setCritThreshold(String(c.critical_severity_threshold));
      setRequireGrn(c.require_grn_for_goods);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);

    try {
      const res = await apiClient.put('/admin/rule-config', {
        price_variance_tolerance_pct: Number(priceTolPct),
        price_variance_tolerance_abs: Number(priceTolAbs),
        quantity_variance_tolerance_pct: Number(qtyTolPct),
        duplicate_window_days: duplicateDays,
        fuzzy_match_threshold: fuzzyThreshold,
        high_severity_threshold: Number(highThreshold),
        critical_severity_threshold: Number(critThreshold),
        require_grn_for_goods: requireGrn,
        change_reason: changeReason || 'Audit tolerance update'
      });
      setMessage(`Successfully saved new version ${res.data.version} of rule configuration!`);
      setChangeReason('');
      fetchConfigs();
    } catch (err: any) {
      setMessage(err.response?.data?.detail || 'Failed to update rule configuration');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Admin Rule & Tolerance Configuration</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Versioned audit rules, allowable price and quantity variance thresholds, and duplicate detection windows
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Configuration Form */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm p-6 md:p-8 space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Active Rule Settings</h3>
              <p className="text-[11px] text-slate-500">
                Currently running on version: <b className="text-sky-600 font-mono">v{config?.version}</b>
              </p>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded-full">
              Live Configuration
            </span>
          </div>

          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Price Variance Tolerance (%)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={priceTolPct}
                  onChange={(e) => setPriceTolPct(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">e.g. 0.50% allowable variance</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Price Absolute Tolerance (£)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={priceTolAbs}
                  onChange={(e) => setPriceTolAbs(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">e.g. £1.00 rounding allowance</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Quantity Variance Tolerance (%)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={qtyTolPct}
                  onChange={(e) => setQtyTolPct(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">Allowable quantity overbill %</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Duplicate Window (Days)
                </label>
                <input
                  type="number"
                  required
                  value={duplicateDays}
                  onChange={(e) => setDuplicateDays(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">Lookback window for duplicates</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Supplier Fuzzy Match (%)
                </label>
                <input
                  type="number"
                  min="50"
                  max="100"
                  required
                  value={fuzzyThreshold}
                  onChange={(e) => setFuzzyThreshold(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">Minimum RapidFuzz token score</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  High Severity Threshold (£)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={highThreshold}
                  onChange={(e) => setHighThreshold(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">Variances &gt; £500 become HIGH</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Critical Severity Threshold (£)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={critThreshold}
                  onChange={(e) => setCritThreshold(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <span className="text-[10px] text-slate-500">Variances &gt; £2500 become CRITICAL</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Version Change Reason / Audit Note
              </label>
              <input
                type="text"
                required
                value={changeReason}
                onChange={(e) => setChangeReason(e.target.value)}
                placeholder="e.g. Updated tolerances approved by Finance Director for Q4 2026"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              <span className="text-[10px] text-slate-500">Every change creates an immutable new version</span>
            </div>

            {message && (
              <div className="p-3.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-800 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>{message}</span>
              </div>
            )}

            <div className="pt-3 flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-md transition-all disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving...' : 'Deploy New Rule Version'}
              </button>
            </div>
          </form>
        </div>

        {/* Version History List */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center gap-2">
            <History className="w-4 h-4 text-slate-500" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Rule Version History ({history.length})
            </h3>
          </div>

          <div className="p-4 divide-y divide-slate-100 flex-1 overflow-y-auto space-y-3">
            {history.map((h) => (
              <div key={h.id} className="pt-3 first:pt-0 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-slate-900 font-mono">
                    Version {h.version}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                    h.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'
                  }`}>
                    {h.is_active ? 'Active' : 'Archived'}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 italic">
                  "{h.change_reason || 'Initial creation'}"
                </p>
                <div className="text-[10px] text-slate-400">
                  Price Tol: {h.price_variance_tolerance_pct}% / £{h.price_variance_tolerance_abs} • Created: {new Date(h.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

