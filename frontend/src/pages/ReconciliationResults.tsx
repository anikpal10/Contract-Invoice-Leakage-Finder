import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ReconciliationCase, Finding } from '../types';
import {
  Sparkles,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  Download,
  Filter,
  CheckSquare
} from 'lucide-react';

export const ReconciliationResults: React.FC = () => {
  const [searchParams] = useSearchParams();
  const caseIdFromQuery = searchParams.get('caseId') || '';
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdFromQuery);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCases();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      fetchFindings(selectedCaseId);
    }
  }, [selectedCaseId]);

  const fetchCases = async () => {
    try {
      const res = await apiClient.get('/cases/');
      setCases(res.data);
      if (!selectedCaseId && res.data.length > 0) {
        setSelectedCaseId(res.data[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchFindings = async (cId: string) => {
    try {
      setLoading(true);
      const res = await apiClient.get(`/cases/${cId}/findings`);
      setFindings(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const totalPotential = findings.reduce((acc, f) => acc + Number(f.potential_difference), 0);
  const confirmedTotal = findings
    .filter((f) => f.review_status === 'CONFIRMED')
    .reduce((acc, f) => acc + Number(f.potential_difference), 0);

  // Category breakdown
  const categorySummary = findings.reduce((acc: Record<string, { count: number; total: number }>, f) => {
    if (!acc[f.finding_category]) {
      acc[f.finding_category] = { count: 0, total: 0 };
    }
    acc[f.finding_category].count += 1;
    acc[f.finding_category].total += Number(f.potential_difference);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Reconciliation Results & Findings</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Deterministic price, quantity, arithmetic, and duplicate invoice analysis
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/reports"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-sm transition-all"
          >
            <Download className="w-4 h-4 text-slate-500" />
            Export Audit Report
          </Link>
          <Link
            to="/review"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition-all"
          >
            <CheckSquare className="w-4 h-4" />
            Review Queue
          </Link>
        </div>
      </div>

      {/* Case Selector */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
        <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
          Inspecting Reconciliation Case:
        </label>
        <select
          value={selectedCaseId}
          onChange={(e) => setSelectedCaseId(e.target.value)}
          className="w-80 px-3 py-1.5 border border-slate-300 rounded-lg text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.case_reference} - {c.title}
            </option>
          ))}
        </select>
      </div>

      {/* Summary KPI Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <div className="bg-white p-5 rounded-xl border border-rose-200 shadow-sm">
          <div className="flex items-center justify-between text-rose-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Potential Leakage Identified</span>
            <TrendingDown className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-rose-700">
            £{totalPotential.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Total identified differences awaiting review</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-emerald-200 shadow-sm">
          <div className="flex items-center justify-between text-emerald-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Confirmed Recoveries</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">
            £{confirmedTotal.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Confirmed by authorized reviewer</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Exception Items</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{findings.length}</div>
          <div className="text-[11px] text-slate-500 mt-1">Discrete line-item exceptions</div>
        </div>
      </div>

      {/* Category Breakdown Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(categorySummary).map(([cat, data]) => (
          <div key={cat} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <div className="text-xs font-bold text-slate-700 truncate">{cat.replace(/_/g, ' ')}</div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-lg font-bold text-slate-900">£{data.total.toFixed(2)}</span>
              <span className="text-xs text-slate-500 font-medium">{data.count} items</span>
            </div>
          </div>
        ))}
      </div>

      {/* Detailed Findings Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900">Identified Financial Exceptions</h3>
          <span className="text-xs text-slate-500">Showing {findings.length} findings</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Invoice Ref / Line</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Supplier</th>
                <th className="py-3 px-4 text-right">Expected</th>
                <th className="py-3 px-4 text-right">Invoiced</th>
                <th className="py-3 px-4 text-right">Variance</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Review Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">Loading findings...</td>
                </tr>
              ) : findings.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">No findings detected for this case.</td>
                </tr>
              ) : (
                findings.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                      {f.invoice_reference} {f.line_number ? `(L${f.line_number})` : ''}
                    </td>
                    <td className="py-3 px-4">
                      <span className="bg-slate-100 text-slate-700 font-medium px-2 py-0.5 rounded text-[11px]">
                        {f.finding_category.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-600 truncate max-w-[150px]">{f.supplier_name}</td>
                    <td className="py-3 px-4 text-right font-mono">£{Number(f.expected_amount).toFixed(2)}</td>
                    <td className="py-3 px-4 text-right font-mono">£{Number(f.invoiced_amount).toFixed(2)}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-rose-600">
                      +£{Number(f.potential_difference).toFixed(2)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        f.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' :
                        f.severity === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                        f.severity === 'MEDIUM' ? 'bg-amber-100 text-amber-800' :
                        'bg-slate-100 text-slate-700'
                      }`}>
                        {f.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        f.review_status === 'CONFIRMED' ? 'bg-emerald-100 text-emerald-800' :
                        f.review_status === 'REJECTED' ? 'bg-slate-200 text-slate-700' :
                        f.review_status === 'NEEDS_MORE_INFO' ? 'bg-purple-100 text-purple-800' :
                        'bg-sky-100 text-sky-800'
                      }`}>
                        {f.review_status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/findings/${f.id}`}
                        className="text-sky-600 hover:text-sky-800 font-semibold text-xs inline-flex items-center gap-1"
                      >
                        Inspect <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

