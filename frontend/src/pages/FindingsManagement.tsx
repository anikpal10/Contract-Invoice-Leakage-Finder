import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { Finding, ReconciliationCase } from '../types';
import { renderMoney } from '../utils/currency';
import {
  AlertTriangle,
  Search,
  Filter,
  ArrowRight,
  TrendingDown,
  Building2,
  CheckCircle2,
  XCircle,
  HelpCircle
} from 'lucide-react';

export const FindingsManagement: React.FC = () => {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchInitial();
  }, []);

  const fetchInitial = async () => {
    try {
      setLoading(true);
      const casesRes = await apiClient.get('/cases/');
      setCases(casesRes.data);
      if (casesRes.data.length > 0) {
        setSelectedCaseId(casesRes.data[0].id);
        const fRes = await apiClient.get(`/cases/${casesRes.data[0].id}/findings`);
        setFindings(fRes.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCaseChange = async (cId: string) => {
    setSelectedCaseId(cId);
    try {
      setLoading(true);
      const fRes = await apiClient.get(`/cases/${cId}/findings`);
      setFindings(fRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredFindings = findings.filter((f) => {
    const matchesSearch =
      f.invoice_reference.toLowerCase().includes(search.toLowerCase()) ||
      f.supplier_name.toLowerCase().includes(search.toLowerCase()) ||
      (f.item_description && f.item_description.toLowerCase().includes(search.toLowerCase()));

    const matchesCategory = categoryFilter === 'ALL' || f.finding_category === categoryFilter;
    const matchesSeverity = severityFilter === 'ALL' || f.severity === severityFilter;
    const matchesStatus = statusFilter === 'ALL' || f.review_status === statusFilter;

    return matchesSearch && matchesCategory && matchesSeverity && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Findings & Exceptions Register</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Search, filter, and audit individual price variances, quantity overages, and duplicate invoices
          </p>
        </div>

        <select
          value={selectedCaseId}
          onChange={(e) => handleCaseChange(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.case_reference} - {c.title}
            </option>
          ))}
        </select>
      </div>

      {/* Filters Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search invoice ref, supplier, or item description..."
            className="w-full pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-2.5 py-2 border border-slate-300 rounded-lg text-xs text-slate-700 bg-white"
          >
            <option value="ALL">All Categories</option>
            <option value="CONTRACT_PRICE_MISMATCH">Contract Price</option>
            <option value="PO_PRICE_MISMATCH">PO Price</option>
            <option value="QUANTITY_OVER_PO">Qty Over PO</option>
            <option value="QUANTITY_OVER_GRN">Qty Over GRN</option>
            <option value="DUPLICATE_INVOICE">Duplicate Invoice</option>
            <option value="INCORRECT_LINE_TOTAL">Line Math</option>
            <option value="INCORRECT_INVOICE_TOTAL">Invoice Total</option>
            <option value="MISSING_CREDIT_OR_AMENDMENT">Missing Credit</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-2.5 py-2 border border-slate-300 rounded-lg text-xs text-slate-700 bg-white"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-2 border border-slate-300 rounded-lg text-xs text-slate-700 bg-white"
          >
            <option value="ALL">All Statuses</option>
            <option value="NEW">New (Awaiting Review)</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="REJECTED">Rejected</option>
            <option value="NEEDS_MORE_INFO">Needs Info</option>
          </select>
        </div>
      </div>

      {/* Findings Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Invoice / Line</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Supplier</th>
                <th className="py-3 px-4 text-right">Expected</th>
                <th className="py-3 px-4 text-right">Invoiced</th>
                <th className="py-3 px-4 text-right">Variance</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">Loading findings...</td>
                </tr>
              ) : filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">No matching findings found.</td>
                </tr>
              ) : (
                filteredFindings.map((f) => (
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
                    <td className="py-3 px-4 text-right font-mono">{renderMoney(Number(f.expected_amount), f.currency)}</td>
                    <td className="py-3 px-4 text-right font-mono">{renderMoney(Number(f.invoiced_amount), f.currency)}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-rose-600">
                      +{renderMoney(Number(f.potential_difference), f.currency)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${f.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' :
                          f.severity === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                            f.severity === 'MEDIUM' ? 'bg-amber-100 text-amber-800' :
                              'bg-slate-100 text-slate-700'
                        }`}>
                        {f.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${f.review_status === 'CONFIRMED' ? 'bg-emerald-100 text-emerald-800' :
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
