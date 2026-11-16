import React, { useEffect, useState, useRef } from 'react';
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { DashboardStats, ReconciliationCase, Finding, RecentDocumentItem } from '../types';
import { AutomatedRecognitionPipelineView } from '../components/pipeline/AutomatedRecognitionPipelineView';
import {
  FileText,
  Briefcase,
  AlertOctagon,
  Clock,
  CheckCircle2,
  TrendingDown,
  ArrowRight,
  UploadCloud,
  CheckSquare,
  Sparkles,
  RefreshCw,
  Zap,
  FolderOpen,
  ShieldCheck,
  Check,
  X,
  FileCheck,
  FileSpreadsheet,
  Layers,
  ChevronRight,
  Trash2
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [recentFindings, setRecentFindings] = useState<Finding[]>([]);
  const [recentDocs, setRecentDocs] = useState<RecentDocumentItem[]>([]);
  const [latestPipelineData, setLatestPipelineData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Quick Ingest State directly on Dashboard
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [category, setCategory] = useState<string>('AUTO');
  const [uploading, setUploading] = useState(false);
  const [uploadProgressStep, setUploadProgressStep] = useState<string>('');
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState<string | null>(null);
  const [uploadErrorMessage, setUploadErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async (isManualRefresh = false) => {
    try {
      if (isManualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const [statsRes, casesRes, docsRes, pipelineRes] = await Promise.all([
        apiClient.get('/cases/summary/dashboard'),
        apiClient.get('/cases/'),
        apiClient.get('/cases/documents/recent?limit=10').catch(() => ({ data: [] })),
        apiClient.get('/cases/pipeline/latest').catch(() => ({ data: null })),
      ]);

      setStats(statsRes.data);
      setCases(casesRes.data);
      setRecentDocs(docsRes.data || []);
      if (pipelineRes?.data) {
        setLatestPipelineData(pipelineRes.data);
      }

      if (casesRes.data.length > 0) {
        if (!selectedCaseId) {
          setSelectedCaseId(casesRes.data[0].id);
        }
        // Fetch recent findings awaiting human review (review_status=NEW)
        try {
          const findingsRes = await apiClient.get('/findings/?review_status=NEW&limit=8');
          setRecentFindings(findingsRes.data);
        } catch {
          // Fallback to case findings
          const findingsRes = await apiClient.get(`/cases/${casesRes.data[0].id}/findings`);
          setRecentFindings(findingsRes.data.filter((f: any) => f.review_status === 'NEW').slice(0, 8));
        }
      }
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleDeleteDocument = async (caseId: string, docId: string, filename: string) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      await apiClient.delete(`/cases/${caseId}/documents/${docId}`);
      await fetchDashboardData(true);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  const handleExecuteQuickUpload = async (overrideFile?: File | unknown) => {
    const fileToUse = (overrideFile instanceof File) ? overrideFile : uploadFile;
    if (!fileToUse) {
      setUploadErrorMessage('Please select a file to upload.');
      return;
    }
    const targetCaseId = selectedCaseId || (cases.length > 0 ? cases[0].id : '');
    if (!targetCaseId) {
      setUploadErrorMessage('Please select or create an active reconciliation case first.');
      return;
    }

    setUploading(true);
    setUploadErrorMessage(null);
    setUploadSuccessMessage(null);
    setUploadProgressStep('1. Uploading file & computing SHA-256 hash...');

    const formData = new FormData();
    formData.append('file', fileToUse);
    formData.append('category', category);

    try {
      setTimeout(() => {
        setUploadProgressStep('2. Parsing document, OCR & extracting line items...');
      }, 500);

      setTimeout(() => {
        setUploadProgressStep('3. Executing multi-way reconciliation against contracts & POs...');
      }, 1100);

      const res = await apiClient.post(`/cases/${targetCaseId}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (res.data?.recognized_data || res.data?.automated_steps) {
        setLatestPipelineData(res.data);
      }

      setUploadProgressStep('4. Updating dashboard analytics & findings...');

      const targetCase = cases.find((c) => c.id === targetCaseId);
      const caseRef = targetCase ? targetCase.case_reference : 'active case';
      
      const successMsg =
        res.data.message ||
        `Document "${fileToUse.name}" successfully processed and reconciled into ${caseRef}.`;
      setUploadSuccessMessage(successMsg);
      setUploadFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';

      // Refresh dashboard data so the user instantly sees the results!
      await fetchDashboardData(true);
    } catch (err: any) {
      setUploadErrorMessage(err.response?.data?.detail || 'Failed to upload and process document.');
    } finally {
      setUploading(false);
      setUploadProgressStep('');
    }
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      setUploadFile(file);
      setUploadSuccessMessage(null);
      setUploadErrorMessage(null);
      handleExecuteQuickUpload(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setUploadFile(file);
      setUploadSuccessMessage(null);
      setUploadErrorMessage(null);
      handleExecuteQuickUpload(file);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-72 gap-3">
        <div className="animate-spin rounded-full h-9 w-9 border-b-2 border-sky-600"></div>
        <p className="text-xs text-slate-500 font-medium">Loading live reconciliation dashboard...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Quick Actions */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white p-6 rounded-2xl shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border border-slate-700">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-semibold border border-emerald-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Live Reconciliation Engine Active
            </span>
          </div>
          <h2 className="text-xl font-bold tracking-tight mt-1.5">Contract & Invoice Leakage Overview</h2>
          <p className="text-xs text-slate-300 mt-1 max-w-xl">
            Upload files to instantly extract line items, execute multi-way financial reconciliation, and visualize detected variances directly on this dashboard.
            Monitor real-time financial reconciliation, track invoice and contract exceptions, and review detected leakage across all active audit cases.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => fetchDashboardData(true)}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-600 transition-all disabled:opacity-50"
            title="Refresh Dashboard Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-sky-400' : ''}`} />
            Refresh
          </button>
          <Link
            to="/cases/new"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow transition-all"
          >
            <Briefcase className="w-3.5 h-3.5" />
            New Case
          </Link>
          <Link
            to="/documents/upload"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow transition-all"
          >
            <FolderOpen className="w-3.5 h-3.5" />
            Disk Browser
          </Link>
          <Link
            to="/review"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition-all"
          >
            <CheckSquare className="w-3.5 h-3.5" />
            Review Queue
          </Link>
        </div>
      </div>

      {/* ============================================================== */}
      {/* ⚡ INSTANT LIVE UPLOAD & WORKING PIPELINE WIDGET ON DASHBOARD */}
      {/* ============================================================== */}
      <div className="bg-white rounded-2xl border-2 border-sky-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 bg-sky-50/60 border-b border-sky-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-600 text-white flex items-center justify-center shadow-sm">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                Quick File Ingest & Real-Time Reconciliation
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold uppercase">
                  Auto-Analyzes Live
                </span>
              </h3>
              <p className="text-[11px] text-slate-500">
                Drop an invoice, contract, or PO here — watch it extract line items and compute leakage right on your dashboard
              </p>
            </div>
          </div>

          {cases.length > 0 && (
            <div className="flex items-center gap-2 text-xs">
              <span className="font-semibold text-slate-600 text-[11px] uppercase tracking-wider">Target Batch:</span>
              <select
                value={selectedCaseId}
                onChange={(e) => setSelectedCaseId(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs bg-white text-slate-800 font-semibold focus:outline-none focus:ring-2 focus:ring-sky-500"
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

        <div className="p-6 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
            {/* Dropzone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`lg:col-span-8 border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all flex flex-col items-center justify-center min-h-[110px] ${
                isDragOver
                  ? 'border-sky-500 bg-sky-100/50 scale-[1.01]'
                  : uploadFile
                  ? 'border-emerald-400 bg-emerald-50/40'
                  : 'border-slate-300 hover:border-sky-400 bg-slate-50/50 hover:bg-sky-50/30'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.csv,.xlsx,.xls"
                onChange={handleFileChange}
                className="hidden"
              />

              {uploadFile ? (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0">
                    <FileCheck className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <p className="text-xs font-bold text-slate-900 truncate max-w-md">{uploadFile.name}</p>
                    <p className="text-[11px] text-slate-500">
                      {(uploadFile.size / 1024).toFixed(1)} KB • Ready for extraction & multi-way matching
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setUploadFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                    className="p-1 rounded-md text-slate-400 hover:text-rose-600 transition-colors ml-2"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-sky-100 text-sky-600 flex items-center justify-center flex-shrink-0">
                    <UploadCloud className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <p className="text-xs font-bold text-slate-800">
                      Click to Browse File or Drag & Drop Here
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Supports PDF invoices, Contracts, POs, or CSV/Excel spreadsheets
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Category & Action Button */}
            <div className="lg:col-span-4 flex flex-col gap-2.5">
              <div>
                <label className="block text-[10px] font-bold text-slate-600 uppercase tracking-wider mb-1">
                  Document Type
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-xs bg-white text-slate-800 font-semibold focus:outline-none focus:ring-2 focus:ring-sky-500"
                >
                  <option value="AUTO">Auto-Detect Type</option>
                  <option value="INVOICE">Supplier Invoice</option>
                  <option value="CONTRACT">Supplier Contract</option>
                  <option value="PRICE_SCHEDULE">Price Schedule / Rate Card</option>
                  <option value="PURCHASE_ORDER">Purchase Order (PO)</option>
                  <option value="GOODS_RECEIVED_NOTE">Goods Received Note (GRN)</option>
                </select>
              </div>

              <button
                type="button"
                disabled={uploading || !uploadFile}
                onClick={handleExecuteQuickUpload}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {uploading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                    <span>Processing Pipeline...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Upload & Reconcile Live</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Live Progress Stage Bar */}
          {uploading && (
            <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 text-sky-900 text-xs space-y-2 animate-in fade-in">
              <div className="flex items-center justify-between font-semibold">
                <span className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-sky-600"></div>
                  {uploadProgressStep}
                </span>
                <span className="text-[11px] text-sky-700 font-mono">Working...</span>
              </div>
              <div className="w-full bg-sky-200 rounded-full h-1.5 overflow-hidden">
                <div className="bg-sky-600 h-1.5 rounded-full animate-pulse w-3/4"></div>
              </div>
            </div>
          )}

          {/* Success Banner */}
          {uploadSuccessMessage && !uploading && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-start justify-between gap-3 animate-in fade-in">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">File Processed & Dashboard Updated Live!</p>
                  <p className="text-emerald-800 text-[11px] mt-0.5">{uploadSuccessMessage}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setUploadSuccessMessage(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Error Banner */}
          {uploadErrorMessage && !uploading && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-300 text-rose-900 text-xs flex items-center justify-between gap-3 animate-in fade-in">
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{uploadErrorMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setUploadErrorMessage(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ============================================================== */}
      {/* 🚀 AUTOMATED RECOGNITION & MULTI-WAY PIPELINE RESULT */}
      {/* ============================================================== */}
      {latestPipelineData && (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              Latest Ingested Document: Everything Recognized & Multi-Way Automated Outcomes
            </span>
            <button
              type="button"
              onClick={() => setLatestPipelineData(null)}
              className="text-xs font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
            >
              <X className="w-3.5 h-3.5" /> Close View
            </button>
          </div>
          <AutomatedRecognitionPipelineView
            pipelineData={latestPipelineData}
            onClose={() => setLatestPipelineData(null)}
          />
        </div>
      )}

      {/* ============================================================== */}
      {/* KPI CARDS GRID */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Invoices */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Invoices Ingested</span>
            <FileText className="w-4 h-4 text-sky-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-slate-900">{stats?.total_invoices ?? 0}</div>
          <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
            <span>Total files:</span>
            <b className="text-slate-700">{stats?.total_documents ?? stats?.total_invoices ?? 0}</b>
          </div>
        </div>

        {/* Total Cases */}
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider">Audit Batches</span>
            <Briefcase className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-slate-900">{stats?.total_cases ?? 0}</div>
          <div className="text-[11px] text-slate-500 mt-1">Active reconciliations</div>
        </div>

        {/* Potential Leakage Identified (Awaiting Review) */}
        <div className="bg-white p-5 rounded-xl border border-rose-200 bg-rose-50/20 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-rose-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Potential Leakage</span>
            <TrendingDown className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-rose-700">
            £{Number(stats?.potential_leakage || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-rose-600 mt-1 font-medium">Unconfirmed pending review</div>
        </div>

        {/* Awaiting Review */}
        <div className="bg-white p-5 rounded-xl border border-amber-200 bg-amber-50/20 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-amber-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Awaiting Review</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-amber-700">{stats?.findings_awaiting_review ?? 0}</div>
          <div className="text-[11px] text-amber-700 mt-1">Requires human analyst signoff</div>
        </div>

        {/* Confirmed Findings */}
        <div className="bg-white p-5 rounded-xl border border-emerald-200 bg-emerald-50/20 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-emerald-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Confirmed Leakage</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-emerald-700">
            £{Number(stats?.confirmed_leakage_amount || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-emerald-700 mt-1 font-medium">{stats?.confirmed_findings ?? 0} approved findings</div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* GRID: RECENT DOCUMENTS INGESTION & PIPELINE STATUS */}
      {/* ============================================================== */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-600" />
            <h3 className="text-sm font-bold text-slate-800">
              Recent Documents & Processing Pipeline Activity ({recentDocs.length})
            </h3>
          </div>
          <Link
            to="/documents/upload"
            className="text-xs font-semibold text-sky-600 hover:text-sky-700 flex items-center gap-1"
          >
            Open Full Filesystem Ingest <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          {recentDocs.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">
              No evidence documents uploaded yet. Use the Quick Upload widget above or visit Document Upload.
              No evidence documents uploaded yet. Visit Document Upload to add evidence files.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Document Name</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Case Reference</th>
                  <th className="py-3 px-4">File Size</th>
                  <th className="py-3 px-4">Processing Pipeline Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {recentDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                      <span className="truncate max-w-[220px]" title={doc.original_filename}>
                        {doc.original_filename}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                          doc.category === 'INVOICE'
                            ? 'bg-sky-100 text-sky-800'
                            : doc.category === 'CONTRACT'
                            ? 'bg-indigo-100 text-indigo-800'
                            : doc.category === 'PURCHASE_ORDER'
                            ? 'bg-purple-100 text-purple-800'
                            : doc.category === 'GOODS_RECEIVED_NOTE'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {doc.category.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                        {doc.case_reference}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">{(doc.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          doc.processing_status === 'EXTRACTED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : doc.processing_status === 'PROCESSING'
                            ? 'bg-sky-100 text-sky-800 animate-pulse'
                            : doc.processing_status === 'FAILED'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {doc.processing_status === 'EXTRACTED' ? (
                          <>
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Extracted & Reconciled
                          </>
                        ) : doc.processing_status === 'PROCESSING' ? (
                          <>
                            <RefreshCw className="w-3 h-3 animate-spin text-sky-600" />
                            Working / Extracting
                          </>
                        ) : (
                          doc.processing_status
                        )}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2.5">
                        <Link
                          to={`/reconciliation?caseId=${doc.case_id}`}
                          className="text-sky-600 hover:text-sky-700 font-semibold text-xs inline-flex items-center gap-1"
                        >
                          Inspect Case <ChevronRight className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleDeleteDocument(doc.case_id, doc.id, doc.original_filename)}
                          className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition-colors"
                          title="Delete / Clear Document"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ============================================================== */}
      {/* GRID: ACTIVE CASES & RECENT FINDINGS */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cases List */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-sky-600" />
              <h3 className="text-sm font-bold text-slate-800">Active Reconciliation Batches</h3>
            </div>
            <Link to="/cases/new" className="text-xs font-semibold text-sky-600 hover:text-sky-700">
              + New Case
            </Link>
          </div>

          <div className="divide-y divide-slate-100">
            {cases.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No reconciliation cases yet. Click "+ New Case" to create your first audit case.
              </div>
            ) : (
              cases.map((c) => (
                <div key={c.id} className="p-5 hover:bg-slate-50/80 transition-colors flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5">
                      <span className="font-semibold text-sm text-slate-900">{c.title}</span>
                      <span className="text-[11px] font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                        {c.case_reference}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                          c.status === 'RECONCILED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : c.status === 'PROCESSING'
                            ? 'bg-sky-100 text-sky-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {c.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 flex items-center gap-3">
                      <span>
                        Supplier: <b className="text-slate-700">{c.supplier_name || 'Multi-Supplier'}</b>
                      </span>
                      <span>•</span>
                      <span>{c.document_count} Evidence Documents</span>
                      <span>•</span>
                      <span>{c.finding_count} Findings</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-xs text-slate-500">Variance Exposure</div>
                      <div className="text-sm font-bold text-rose-600">
                        £{Number(c.potential_leakage_amount || 0).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                    <Link
                      to={`/reconciliation?caseId=${c.id}`}
                      className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                      title="Inspect Reconciliation Results"
                    >
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent High Priority Findings Awaiting Review */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-rose-600" />
              <h3 className="text-sm font-bold text-slate-800">Awaiting Human Review ({recentFindings.length})</h3>
            </div>
            <Link to="/review" className="text-xs font-semibold text-sky-600 hover:text-sky-700">
              Review Queue →
            </Link>
          </div>

          <div className="p-4 flex-1 divide-y divide-slate-100 overflow-y-auto max-h-[380px]">
            {recentFindings.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs space-y-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto opacity-80" />
                <p className="font-bold text-slate-700">No Unreviewed Findings on Dashboard</p>
                <p className="text-[11px] text-slate-400">
                  Once findings are reviewed, they leave this dashboard view and move to the Review Archive.
                </p>
                <Link
                  to="/review"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700 pt-1"
                >
                  View Reviewed History & Archive <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            ) : (
              recentFindings.map((f) => (
                <div key={f.id} className="py-3 first:pt-0 last:pb-0 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-800 truncate">{f.invoice_reference}</span>
                    <span className="text-xs font-bold text-rose-600">
                      +{f.currency === 'INR' ? '₹' : '£'}{Number(f.potential_difference).toFixed(2)}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 truncate">{f.supplier_name}</div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[10px] font-medium bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                      {f.finding_category.replace(/_/g, ' ')}
                    </span>
                    <Link
                      to={`/findings/${f.id}`}
                      className="text-[11px] text-sky-600 font-medium hover:underline flex items-center gap-0.5"
                    >
                      Review <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>

          {recentFindings.length > 0 && (
            <div className="p-3 bg-slate-50 border-t border-slate-100 text-center">
              <Link to="/review" className="text-xs font-semibold text-sky-600 hover:text-sky-700 inline-flex items-center gap-1">
                Open Review Queue to Confirm / Reject <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
