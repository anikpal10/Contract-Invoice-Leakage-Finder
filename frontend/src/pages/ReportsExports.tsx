import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { ReconciliationCase, ExportRecord } from '../types';
import {
  FileText,
  Download,
  FileSpreadsheet,
  CheckCircle2,
  Calendar,
  Building2,
  Clock,
  Sparkles,
  FileCode,
  Layers,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Eye,
  Check,
  X,
  Trash2
} from 'lucide-react';

interface DossierData {
  case: {
    id: string;
    case_reference: string;
    title: string;
    supplier_name: string | null;
    currency: string;
    status: string;
    created_at: string | null;
  };
  stats: {
    total_documents: number;
    total_findings: number;
    total_potential_leakage: number;
    confirmed_leakage: number;
    pending_leakage: number;
    confirmed_count: number;
    pending_count: number;
    rejected_count: number;
    currency: string;
  };
  documents: Array<{
    id: string;
    original_filename: string;
    category: string;
    file_type: string;
    file_size_bytes: number;
    sha256_hash: string;
    processing_status: string;
    created_at: string | null;
  }>;
  findings: Array<{
    id: string;
    invoice_reference: string;
    line_number: number | null;
    supplier_name: string;
    finding_category: string;
    item_code: string | null;
    item_description: string | null;
    expected_amount: number;
    invoiced_amount: number;
    potential_difference: number;
    currency: string;
    severity: string;
    review_status: string;
    calculation_explanation: string;
    created_at: string | null;
  }>;
  line_items: Array<{
    invoice_number: string;
    line_number: number | null;
    item_code: string | null;
    description: string;
    quantity: number;
    unit_price: number;
    line_total: number;
    currency: string;
  }>;
}

export const ReportsExports: React.FC = () => {
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [includeRejected, setIncludeRejected] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);
  const [recentExports, setRecentExports] = useState<ExportRecord[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [dossier, setDossier] = useState<DossierData | null>(null);
  const [loadingDossier, setLoadingDossier] = useState(false);
  const [activeDossierTab, setActiveDossierTab] = useState<'OVERVIEW' | 'FINDINGS' | 'ITEMS' | 'DOCS'>('OVERVIEW');

  useEffect(() => {
    fetchCases();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      fetchExportsHistory(selectedCaseId);
      fetchFullDossier(selectedCaseId);
    }
  }, [selectedCaseId]);

  const fetchCases = async () => {
    try {
      const res = await apiClient.get('/cases/');
      setCases(res.data);
      if (res.data.length > 0) {
        setSelectedCaseId(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to load cases:', err);
    }
  };

  const fetchExportsHistory = async (caseId: string) => {
    try {
      const res = await apiClient.get(`/cases/${caseId}/exports`);
      setRecentExports(res.data);
    } catch (err) {
      console.error('Failed to load export history:', err);
    }
  };

  const fetchFullDossier = async (caseId: string) => {
    setLoadingDossier(true);
    try {
      const res = await apiClient.get(`/cases/${caseId}/full-dossier`);
      setDossier(res.data);
    } catch (err) {
      console.error('Failed to load full dossier:', err);
    } finally {
      setLoadingDossier(false);
    }
  };

  const handleDeleteExport = async (exportId: string, filename: string) => {
    if (!selectedCaseId) return;
    if (!window.confirm(`Are you sure you want to delete report "${filename}"?`)) return;
    try {
      await apiClient.delete(`/cases/${selectedCaseId}/exports/${exportId}`);
      fetchExportsHistory(selectedCaseId);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete report');
    }
  };

  const handleClearExportHistory = async () => {
    if (!selectedCaseId) return;
    if (!window.confirm('Are you sure you want to clear all report export files for this batch?')) return;
    try {
      await apiClient.delete(`/cases/${selectedCaseId}/exports`);
      fetchExportsHistory(selectedCaseId);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to clear export history');
    }
  };

  const handleDeleteDocFromReport = async (docId: string, filename: string) => {
    if (!selectedCaseId) return;
    if (!window.confirm(`Are you sure you want to delete and clear "${filename}"?`)) return;
    try {
      await apiClient.delete(`/cases/${selectedCaseId}/documents/${docId}`);
      fetchFullDossier(selectedCaseId);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  const downloadFileBlob = async (downloadUrl: string, fileName: string) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(downloadUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
      // Fallback with token in query param
      const token = localStorage.getItem('token');
      const tokenUrl = token ? `${downloadUrl}?token=${token}` : downloadUrl;
      window.open(tokenUrl, '_blank');
    }
  };

  const handleExport = async (format: 'PDF' | 'EXCEL' | 'CSV' | 'JSON') => {
    if (!selectedCaseId) return;
    setExporting(format);
    setMessage(null);

    try {
      const res = await apiClient.post(`/cases/${selectedCaseId}/exports`, {
        format,
        include_rejected: includeRejected,
      });
      const exportRec: ExportRecord = res.data;
      setRecentExports((prev) => [exportRec, ...prev]);
      setMessage(`Generated and downloaded ${format} report: ${exportRec.file_name}`);

      // Auto trigger download via secure blob download
      if (exportRec.download_url) {
        await downloadFileBlob(exportRec.download_url, exportRec.file_name);
      }
    } catch (err: any) {
      setMessage(err.response?.data?.detail || `Failed to generate ${format} report`);
    } finally {
      setExporting(null);
    }
  };

  const getCurrencySymbol = (code?: string) => {
    const c = (code || dossier?.stats?.currency || 'GBP').toUpperCase();
    if (c === 'INR') return '₹';
    if (c === 'USD') return '$';
    if (c === 'EUR') return '€';
    return '£';
  };

  const sym = getCurrencySymbol(dossier?.stats?.currency);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Audit Reports & Complete Reconciliation Dossier</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Download the complete financial reconciliation package in PDF, Excel, CSV, or JSON and inspect everything on-screen
          </p>
        </div>

        {selectedCaseId && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Batch:</span>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-800 bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_reference} - {c.title}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Prominent Download Options Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Download className="w-4 h-4 text-sky-600" />
              Download The Whole Case Reconciliation Package
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Select your preferred export format to download the complete case audit dossier to your computer
            </p>
          </div>

          <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={includeRejected}
              onChange={(e) => setIncludeRejected(e.target.checked)}
              className="h-3.5 w-3.5 text-sky-600 rounded border-slate-300 focus:ring-sky-500"
            />
            <span className="font-medium">Include rejected findings in report</span>
          </label>
        </div>

        {/* 4 Download Format Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
          {/* 1. PDF Report */}
          <button
            type="button"
            disabled={!selectedCaseId || exporting !== null}
            onClick={() => handleExport('PDF')}
            className="flex flex-col items-start p-4 rounded-xl border border-rose-200 bg-rose-50/50 hover:bg-rose-100/60 hover:border-rose-400 text-left transition-all group disabled:opacity-50 shadow-sm"
          >
            <div className="flex items-center justify-between w-full">
              <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-xs">
                <FileText className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 bg-rose-200/60 px-2 py-0.5 rounded">
                PDF
              </span>
            </div>
            <span className="font-bold text-slate-900 text-xs mt-3 group-hover:text-rose-900">
              {exporting === 'PDF' ? 'Generating PDF...' : 'Formal PDF Audit Report'}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              Executive summary, evidence documents, line items, and itemized exceptions table
            </span>
          </button>

          {/* 2. Excel Workbook */}
          <button
            type="button"
            disabled={!selectedCaseId || exporting !== null}
            onClick={() => handleExport('EXCEL')}
            className="flex flex-col items-start p-4 rounded-xl border border-emerald-200 bg-emerald-50/50 hover:bg-emerald-100/60 hover:border-emerald-400 text-left transition-all group disabled:opacity-50 shadow-sm"
          >
            <div className="flex items-center justify-between w-full">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-200/60 px-2 py-0.5 rounded">
                Excel (.xlsx)
              </span>
            </div>
            <span className="font-bold text-slate-900 text-xs mt-3 group-hover:text-emerald-900">
              {exporting === 'EXCEL' ? 'Generating Excel...' : 'Multi-Sheet Excel Workbook'}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              4 tabs: Executive Summary, Findings, Extracted Line Items, Documents
            </span>
          </button>

          {/* 3. CSV Register */}
          <button
            type="button"
            disabled={!selectedCaseId || exporting !== null}
            onClick={() => handleExport('CSV')}
            className="flex flex-col items-start p-4 rounded-xl border border-sky-200 bg-sky-50/50 hover:bg-sky-100/60 hover:border-sky-400 text-left transition-all group disabled:opacity-50 shadow-sm"
          >
            <div className="flex items-center justify-between w-full">
              <div className="w-8 h-8 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center font-bold text-xs">
                <Layers className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-sky-700 bg-sky-200/60 px-2 py-0.5 rounded">
                CSV
              </span>
            </div>
            <span className="font-bold text-slate-900 text-xs mt-3 group-hover:text-sky-900">
              {exporting === 'CSV' ? 'Generating CSV...' : 'Raw Findings CSV Register'}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              Clean structured table for accounting ERP and billing system ingestion
            </span>
          </button>

          {/* 4. JSON Full Package */}
          <button
            type="button"
            disabled={!selectedCaseId || exporting !== null}
            onClick={() => handleExport('JSON')}
            className="flex flex-col items-start p-4 rounded-xl border border-indigo-200 bg-indigo-50/50 hover:bg-indigo-100/60 hover:border-indigo-400 text-left transition-all group disabled:opacity-50 shadow-sm"
          >
            <div className="flex items-center justify-between w-full">
              <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
                <FileCode className="w-4 h-4" />
              </div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 bg-indigo-200/60 px-2 py-0.5 rounded">
                JSON
              </span>
            </div>
            <span className="font-bold text-slate-900 text-xs mt-3 group-hover:text-indigo-900">
              {exporting === 'JSON' ? 'Generating JSON...' : 'Full Case Dossier (JSON)'}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              Complete machine-readable audit package with raw payloads & metadata
            </span>
          </button>
        </div>

        {message && (
          <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{message}</span>
          </div>
        )}
      </div>

      {/* ====================================================================== */}
      {/* LIVE AUDIT REPORT & FULL DOSSIER VIEWER (SEE THE WHOLE THING ON SCREEN) */}
      {/* ====================================================================== */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/70 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center">
              <Eye className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Live Audit Report & Reconciliation Dossier Viewer
              </h3>
              <p className="text-[11px] text-slate-500">
                Inspect the full reconciliation breakdown, documents, line items, and findings on-screen
              </p>
            </div>
          </div>

          {/* Dossier Tabs */}
          <div className="flex items-center gap-1 bg-slate-200/70 p-1 rounded-xl text-xs font-semibold">
            <button
              type="button"
              onClick={() => setActiveDossierTab('OVERVIEW')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeDossierTab === 'OVERVIEW'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Executive Summary
            </button>
            <button
              type="button"
              onClick={() => setActiveDossierTab('FINDINGS')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeDossierTab === 'FINDINGS'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Findings ({dossier?.findings.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveDossierTab('ITEMS')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeDossierTab === 'ITEMS'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Line Items ({dossier?.line_items.length || 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveDossierTab('DOCS')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeDossierTab === 'DOCS'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Documents ({dossier?.documents.length || 0})
            </button>
          </div>
        </div>

        {loadingDossier ? (
          <div className="p-12 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-sky-600"></div>
            <span>Loading full reconciliation dossier...</span>
          </div>
        ) : !dossier ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No reconciliation data found for this batch. Upload and reconcile documents first.
          </div>
        ) : (
          <div className="p-6 space-y-6">
            {/* TAB 1: EXECUTIVE SUMMARY */}
            {activeDossierTab === 'OVERVIEW' && (
              <div className="space-y-6">
                {/* 4 KPI Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70">
                    <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                      Evidence Documents
                    </span>
                    <span className="text-xl font-bold text-slate-900 mt-1 block">
                      {dossier.stats.total_documents}
                    </span>
                    <span className="text-[11px] text-slate-500 mt-0.5 block">Analyzed & Reconciled</span>
                  </div>

                  <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/60">
                    <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider block">
                      Confirmed Leakage
                    </span>
                    <span className="text-xl font-bold text-emerald-700 mt-1 block">
                      {sym}{dossier.stats.confirmed_leakage.toLocaleString()}
                    </span>
                    <span className="text-[11px] text-emerald-700 mt-0.5 block">
                      {dossier.stats.confirmed_count} reviewed & confirmed
                    </span>
                  </div>

                  <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/60">
                    <span className="text-[11px] font-bold text-amber-800 uppercase tracking-wider block">
                      Pending Unreviewed Leakage
                    </span>
                    <span className="text-xl font-bold text-amber-700 mt-1 block">
                      {sym}{dossier.stats.pending_leakage.toLocaleString()}
                    </span>
                    <span className="text-[11px] text-amber-700 mt-0.5 block">
                      {dossier.stats.pending_count} awaiting human decision
                    </span>
                  </div>

                  <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/60">
                    <span className="text-[11px] font-bold text-rose-800 uppercase tracking-wider block">
                      Total Exceptions
                    </span>
                    <span className="text-xl font-bold text-rose-700 mt-1 block">
                      {dossier.stats.total_findings}
                    </span>
                    <span className="text-[11px] text-rose-700 mt-0.5 block">
                      {sym}{dossier.stats.total_potential_leakage.toLocaleString()} total variance
                    </span>
                  </div>
                </div>

                {/* Case Metadata Bar */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <span className="text-slate-400 block font-bold uppercase text-[10px]">Case Ref:</span>
                    <span className="font-semibold text-slate-900">{dossier.case.case_reference}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-bold uppercase text-[10px]">Supplier:</span>
                    <span className="font-semibold text-slate-900">{dossier.case.supplier_name || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-bold uppercase text-[10px]">Currency:</span>
                    <span className="font-semibold text-slate-900">{dossier.case.currency} ({sym})</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-bold uppercase text-[10px]">Status:</span>
                    <span className="font-semibold text-emerald-700">{dossier.case.status}</span>
                  </div>
                </div>

                {/* Findings Preview Table */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Reconciliation Findings Preview ({dossier.findings.length})
                    </h4>
                    <button
                      type="button"
                      onClick={() => setActiveDossierTab('FINDINGS')}
                      className="text-xs text-sky-600 hover:text-sky-800 font-semibold flex items-center gap-1"
                    >
                      View All Findings <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase">
                          <th className="py-2.5 px-3">Invoice</th>
                          <th className="py-2.5 px-3">Category</th>
                          <th className="py-2.5 px-3 text-right">Expected</th>
                          <th className="py-2.5 px-3 text-right">Invoiced</th>
                          <th className="py-2.5 px-3 text-right">Variance</th>
                          <th className="py-2.5 px-3 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {dossier.findings.slice(0, 5).map((f) => (
                          <tr key={f.id} className="hover:bg-slate-50">
                            <td className="py-2.5 px-3 font-semibold text-slate-900">{f.invoice_reference}</td>
                            <td className="py-2.5 px-3 text-slate-600">{f.finding_category.replace(/_/g, ' ')}</td>
                            <td className="py-2.5 px-3 text-right text-slate-600">{sym}{f.expected_amount.toLocaleString()}</td>
                            <td className="py-2.5 px-3 text-right text-slate-600">{sym}{f.invoiced_amount.toLocaleString()}</td>
                            <td className="py-2.5 px-3 text-right font-bold text-rose-600">{sym}{f.potential_difference.toLocaleString()}</td>
                            <td className="py-2.5 px-3 text-center">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                  f.review_status === 'CONFIRMED'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : f.review_status === 'REJECTED'
                                    ? 'bg-rose-100 text-rose-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {f.review_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: ALL FINDINGS */}
            {activeDossierTab === 'FINDINGS' && (
              <div className="space-y-3">
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase">
                        <th className="py-3 px-3">Invoice & Line</th>
                        <th className="py-3 px-3">Category</th>
                        <th className="py-3 px-3">Description</th>
                        <th className="py-3 px-3 text-right">Expected</th>
                        <th className="py-3 px-3 text-right">Invoiced</th>
                        <th className="py-3 px-3 text-right">Variance</th>
                        <th className="py-3 px-3">Severity</th>
                        <th className="py-3 px-3">Status</th>
                        <th className="py-3 px-3">Explanation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {dossier.findings.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="py-6 text-center text-slate-400">
                            No findings found for this batch.
                          </td>
                        </tr>
                      ) : (
                        dossier.findings.map((f) => (
                          <tr key={f.id} className="hover:bg-slate-50">
                            <td className="py-2.5 px-3 font-semibold text-slate-900 whitespace-nowrap">
                              {f.invoice_reference}
                              {f.line_number ? ` (L${f.line_number})` : ''}
                            </td>
                            <td className="py-2.5 px-3 text-slate-700 whitespace-nowrap">
                              {f.finding_category.replace(/_/g, ' ')}
                            </td>
                            <td className="py-2.5 px-3 text-slate-600 max-w-xs truncate" title={f.item_description || ''}>
                              {f.item_description || '-'}
                            </td>
                            <td className="py-2.5 px-3 text-right text-slate-600 whitespace-nowrap">
                              {sym}{f.expected_amount.toLocaleString()}
                            </td>
                            <td className="py-2.5 px-3 text-right text-slate-600 whitespace-nowrap">
                              {sym}{f.invoiced_amount.toLocaleString()}
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-rose-600 whitespace-nowrap">
                              {sym}{f.potential_difference.toLocaleString()}
                            </td>
                            <td className="py-2.5 px-3">
                              <span className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] font-bold text-slate-700">
                                {f.severity}
                              </span>
                            </td>
                            <td className="py-2.5 px-3">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                  f.review_status === 'CONFIRMED'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : f.review_status === 'REJECTED'
                                    ? 'bg-rose-100 text-rose-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {f.review_status}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-[11px] text-slate-600 max-w-md" title={f.calculation_explanation}>
                              {f.calculation_explanation}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 3: EXTRACTED LINE ITEMS */}
            {activeDossierTab === 'ITEMS' && (
              <div className="space-y-3">
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase">
                        <th className="py-3 px-3">Invoice Ref</th>
                        <th className="py-3 px-3">Line #</th>
                        <th className="py-3 px-3">Item Code</th>
                        <th className="py-3 px-3">Description</th>
                        <th className="py-3 px-3 text-right">Quantity</th>
                        <th className="py-3 px-3 text-right">Unit Price</th>
                        <th className="py-3 px-3 text-right">Line Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {dossier.line_items.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="py-6 text-center text-slate-400">
                            No extracted line items found.
                          </td>
                        </tr>
                      ) : (
                        dossier.line_items.map((li, idx) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            <td className="py-2 px-3 font-semibold text-slate-900">{li.invoice_number}</td>
                            <td className="py-2 px-3 text-slate-500">{li.line_number || '-'}</td>
                            <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">{li.item_code || '-'}</td>
                            <td className="py-2 px-3 text-slate-800">{li.description}</td>
                            <td className="py-2 px-3 text-right text-slate-600">{li.quantity}</td>
                            <td className="py-2 px-3 text-right text-slate-600">{sym}{li.unit_price.toFixed(2)}</td>
                            <td className="py-2 px-3 text-right font-semibold text-slate-900">{sym}{li.line_total.toFixed(2)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB 4: EVIDENCE DOCUMENTS */}
            {activeDossierTab === 'DOCS' && (
              <div className="space-y-3">
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase">
                        <th className="py-3 px-3">Filename</th>
                        <th className="py-3 px-3">Category</th>
                        <th className="py-3 px-3">File Size</th>
                        <th className="py-3 px-3">SHA-256 Hash</th>
                        <th className="py-3 px-3">Extraction Status</th>
                        <th className="py-3 px-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {dossier.documents.map((d) => (
                        <tr key={d.id} className="hover:bg-slate-50">
                          <td className="py-2.5 px-3 font-semibold text-slate-900 flex items-center gap-2">
                            <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                            <span>{d.original_filename}</span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-[10px] font-bold text-slate-700">
                              {d.category.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-500">{(d.file_size_bytes / 1024).toFixed(1)} KB</td>
                          <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">{d.sha256_hash.substring(0, 16)}...</td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-emerald-100 text-emerald-800">
                              {d.processing_status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleDeleteDocFromReport(d.id, d.original_filename)}
                              className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                              title="Delete Document"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Generated Reports History Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900">Generated Reports History</h3>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-500 font-medium">{recentExports.length} export file(s) available</span>
            {recentExports.length > 0 && (
              <button
                type="button"
                onClick={handleClearExportHistory}
                className="text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 px-2 py-1 rounded-lg border border-rose-200 transition-colors flex items-center gap-1 shadow-sm"
                title="Clear all generated reports history"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Clear All
              </button>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Report File</th>
                <th className="py-3 px-4">Format</th>
                <th className="py-3 px-4">Records</th>
                <th className="py-3 px-4">Leakage Exposure</th>
                <th className="py-3 px-4">Generated At</th>
                <th className="py-3 px-4 text-right">Download</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {recentExports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-400">
                    No export files generated yet. Choose an export format above to generate and download.
                  </td>
                </tr>
              ) : (
                recentExports.map((rec) => (
                  <tr key={rec.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                      <span>{rec.file_name}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="bg-slate-100 text-slate-700 font-bold px-2 py-0.5 rounded text-[10px]">
                        {rec.format}
                      </span>
                    </td>
                    <td className="py-3 px-4">{rec.record_count} items</td>
                    <td className="py-3 px-4 font-bold text-rose-600">
                      {sym}{Number(rec.total_leakage_amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {new Date(rec.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => downloadFileBlob(rec.download_url || `/v1/cases/${rec.case_id}/exports/${rec.id}/download`, rec.file_name)}
                          className="inline-flex items-center gap-1 text-sky-600 hover:text-sky-800 font-semibold px-2 py-1 rounded-lg hover:bg-sky-50 transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteExport(rec.id, rec.file_name)}
                          className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                          title="Delete Report"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
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

