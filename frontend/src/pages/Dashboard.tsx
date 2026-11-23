import React, { useEffect, useState, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { apiClient } from '../api/client';
import { DashboardStats, ReconciliationCase, Finding, RecentDocumentItem } from '../types';
import { AutomatedRecognitionPipelineView } from '../components/pipeline/AutomatedRecognitionPipelineView';
import { formatBreakdown, renderMoney } from '../utils/currency';
import {
  FileText,
  Briefcase,
  AlertOctagon,
  Clock,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Scale,
  ArrowRight,
  CheckSquare,
  Sparkles,
  RefreshCw,
  FolderOpen,
  UploadCloud,
  Zap,
  X,
  XCircle,
  Layers,
  ChevronRight,
  Trash2
} from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [recentFindings, setRecentFindings] = useState<Finding[]>([]);
  const [recentDocs, setRecentDocs] = useState<RecentDocumentItem[]>([]);
  const [latestPipelineData, setLatestPipelineData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [reviewCompletionNotice, setReviewCompletionNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgressStep, setUploadProgressStep] = useState<string>('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const navigate = useNavigate();

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
      setError(null);

      const queryDocId = searchParams.get('documentId');
      const storedDocId = sessionStorage.getItem('last_uploaded_document_id');
      const targetDocId = queryDocId || storedDocId;

      const pipelineUrl = targetDocId
        ? `/cases/pipeline/latest?document_id=${targetDocId}`
        : '/cases/pipeline/latest';

      const [statsRes, casesRes, docsRes, pipelineRes] = await Promise.all([
        apiClient.get('/cases/summary/dashboard'),
        apiClient.get('/cases/'),
        apiClient.get('/cases/documents/recent?limit=10').catch(() => ({ data: [] })),
        apiClient.get(pipelineUrl).catch(() => ({ data: null })),
      ]);

      setStats(statsRes.data);
      setCases(casesRes.data);
      setRecentDocs(docsRes.data || []);
      if (pipelineRes?.data) {
        setLatestPipelineData(pipelineRes.data);
      }

      // Filter awaiting review findings ONLY to the uploaded file!
      const activeDocId = targetDocId || pipelineRes?.data?.document_id;
      if (activeDocId) {
        try {
          const findingsRes = await apiClient.get(`/findings/?document_id=${activeDocId}&review_status=NEW&limit=8`);
          setRecentFindings(findingsRes.data);
        } catch {
          if (pipelineRes?.data?.findings) {
            setRecentFindings(
              pipelineRes.data.findings
                .filter((f: any) => f.review_status === 'NEW' || f.review_status === 'UNDER_REVIEW')
                .slice(0, 8)
            );
          } else if (casesRes.data.length > 0) {
            const findingsRes = await apiClient.get(`/cases/${casesRes.data[0].id}/findings`);
            setRecentFindings(findingsRes.data.filter((f: any) => f.review_status === 'NEW').slice(0, 8));
          }
        }
      } else if (casesRes.data.length > 0) {
        try {
          const findingsRes = await apiClient.get('/findings/?review_status=NEW&limit=8');
          setRecentFindings(findingsRes.data);
        } catch {
          const findingsRes = await apiClient.get(`/cases/${casesRes.data[0].id}/findings`);
          setRecentFindings(findingsRes.data.filter((f: any) => f.review_status === 'NEW').slice(0, 8));
        }
      }
    } catch (err: any) {
      console.error('Failed to load dashboard:', err);
      const msg = err.response?.data?.detail || err.message || 'Connection to reconciliation backend failed';
      setError(`Backend connectivity issue: ${msg}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleQuickUpload = async (file: File) => {
    let targetCaseId = cases.length > 0 ? cases[0].id : '';
    if (!targetCaseId) {
      try {
        const casesRes = await apiClient.get('/cases/');
        if (casesRes.data && casesRes.data.length > 0) {
          targetCaseId = casesRes.data[0].id;
        }
      } catch (err) {
        console.error('Failed to get cases:', err);
      }
    }
    if (!targetCaseId) {
      setError('Please create or select an active reconciliation audit batch first.');
      return;
    }

    setUploading(true);
    setUploadProgressStep(`Processing "${file.name}": parsing OCR, extracting commercial entities & reconciling...`);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('files', file);
      formData.append('category', 'AUTO');

      const res = await apiClient.post(`/cases/${targetCaseId}/documents/batch-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const data = res.data || {};
      const uploadedDocId = data.document_id || data.pipeline?.document_id;
      const uploadedDocName = data.original_filename || data.pipeline?.original_filename || file.name;
      if (uploadedDocId) {
        sessionStorage.setItem('last_uploaded_document_id', uploadedDocId);
        if (uploadedDocName) sessionStorage.setItem('last_uploaded_document_name', uploadedDocName);
      }

      if (data.pipeline) {
        setLatestPipelineData(data.pipeline);
      } else {
        const latestRes = await apiClient.get('/cases/pipeline/latest').catch(() => null);
        if (latestRes?.data) setLatestPipelineData(latestRes.data);
      }

      await fetchDashboardData(true);
    } catch (err: any) {
      console.error('Quick upload failed:', err);
      const msg = err.response?.data?.detail || err.message || 'File upload and extraction failed';
      setError(`Upload failed: ${msg}`);
    } finally {
      setUploading(false);
      setUploadProgressStep('');
      if (fileInputRef.current) fileInputRef.current.value = '';
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

  const handleQuickDecision = async (findingId: string, action: 'CONFIRM' | 'REJECT', caseId: string) => {
    setActioningId(findingId);
    try {
      await apiClient.post(`/findings/${findingId}/decisions`, {
        action,
        comment: `Dashboard quick human review: ${action}`
      });

      const remaining = recentFindings.filter((f) => f.id !== findingId);
      setRecentFindings(remaining);

      // If all findings on dashboard are reviewed, route to Reports & Exports!
      if (remaining.length === 0) {
        setReviewCompletionNotice('All findings reviewed! Human review complete — navigating to Reports & Exports...');
        setTimeout(() => {
          navigate(caseId ? `/reports?caseId=${caseId}` : '/reports');
        }, 1000);
      } else {
        fetchDashboardData(true);
      }
    } catch (err) {
      console.error('Failed to submit decision:', err);
    } finally {
      setActioningId(null);
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
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragOver(false);
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleQuickUpload(e.dataTransfer.files[0]);
          }
        }}
        className={`bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white p-6 rounded-2xl shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border transition-all ${
          isDragOver ? 'border-sky-400 ring-2 ring-sky-400/50 bg-slate-850' : 'border-slate-700'
        }`}
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-semibold border border-emerald-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Live Reconciliation Engine Active
            </span>
            {isDragOver && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-sky-500/20 text-sky-300 text-[11px] font-semibold border border-sky-500/30 animate-pulse">
                Drop file to auto-extract & reconcile!
              </span>
            )}
          </div>
          <h2 className="text-xl font-bold tracking-tight mt-1.5">Contract & Invoice Leakage Overview</h2>
          <p className="text-xs text-slate-300 mt-1 max-w-xl">
            Monitor real-time financial reconciliation, track invoice and contract exceptions, and review detected leakage across all active audit cases.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Native hidden file input for immediate auto upload & extraction */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleQuickUpload(e.target.files[0]);
              }
            }}
            className="hidden"
            accept=".pdf,.csv,.xlsx,.xls,.png,.jpg,.jpeg"
          />

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow transition-all disabled:opacity-50"
            title="Upload invoice or contract to auto-extract & view live output"
          >
            {uploading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
                <span>Extracting...</span>
              </>
            ) : (
              <>
                <UploadCloud className="w-3.5 h-3.5 text-white" />
                <span>Upload & Extract</span>
              </>
            )}
          </button>

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
            to="/documents/upload"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow transition-all"
          >
            <FolderOpen className="w-3.5 h-3.5" />
            Disk Browser
          </Link>
          <Link
            to={latestPipelineData?.document_id ? `/review?documentId=${latestPipelineData.document_id}` : '/review'}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition-all"
          >
            <CheckSquare className="w-3.5 h-3.5" />
            Review Queue
          </Link>
        </div>
      </div>

      {/* Live Upload & Extraction Status Alert */}
      {uploading && (
        <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 text-sky-900 flex items-center gap-3 shadow-sm animate-in fade-in">
          <RefreshCw className="w-5 h-5 text-sky-600 animate-spin flex-shrink-0" />
          <div className="text-xs">
            <p className="font-bold text-sky-950">Auto-Extracting & Reconciling Document...</p>
            <p className="text-sky-700 mt-0.5">{uploadProgressStep || 'Processing OCR, extracting line items, and running multi-way mathematical variance analysis...'}</p>
          </div>
        </div>
      )}

      {/* Latest Automated Recognition & Multi-Way Outcome (if available) */}
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

      {/* Backend Connectivity Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 flex items-center justify-between gap-3 shadow-sm animate-in fade-in">
          <div className="flex items-center gap-2.5 text-xs">
            <AlertOctagon className="w-5 h-5 text-amber-600 flex-shrink-0" />
            <div>
              <p className="font-bold text-amber-950">Backend Connectivity Issue</p>
              <p className="text-amber-800 mt-0.5">{error}. Ensure the FastAPI server is running on port 8000.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => fetchDashboardData(true)}
            className="px-3.5 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold flex items-center gap-1.5 flex-shrink-0 shadow transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Retry Connection
          </button>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
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

        {/* Gross Overcharges (Awaiting Review) */}
        <div className="bg-white p-5 rounded-xl border border-rose-200 bg-rose-50/20 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-rose-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Gross Overcharges</span>
            <TrendingDown className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-rose-700">
            {stats?.gross_overcharges_by_currency && Object.keys(stats.gross_overcharges_by_currency).length > 0
              ? formatBreakdown(stats.gross_overcharges_by_currency)
              : renderMoney(Number(stats?.gross_overcharges ?? stats?.potential_leakage ?? 0))}
          </div>
          <div className="text-[11px] text-rose-600 mt-1 font-medium">Gross potential overcharge (pending review)</div>
        </div>

        {/* Potential Undercharges */}
        <div className="bg-white p-5 rounded-xl border border-sky-200 bg-sky-50/20 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-sky-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Potential Undercharges</span>
            <TrendingUp className="w-4 h-4 text-sky-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-sky-700">
            {stats?.potential_undercharges_by_currency && Object.keys(stats.potential_undercharges_by_currency).length > 0
              ? formatBreakdown(stats.potential_undercharges_by_currency)
              : renderMoney(Number(stats?.potential_undercharges || 0))}
          </div>
          <div className="text-[11px] text-sky-600 mt-1 font-medium">Billed below agreed rate (pending review)</div>
        </div>

        {/* Net Variance */}
        <div className="bg-white p-5 rounded-xl border border-indigo-200 bg-indigo-50/20 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between text-indigo-600">
            <span className="text-xs font-semibold uppercase tracking-wider">Net Variance</span>
            <Scale className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-3 text-2xl font-bold text-indigo-700">
            {stats?.net_variance_by_currency && Object.keys(stats.net_variance_by_currency).length > 0
              ? formatBreakdown(stats.net_variance_by_currency)
              : renderMoney(Number(stats?.net_variance || 0))}
          </div>
          <div className="text-[11px] text-indigo-600 mt-1 font-medium">Overcharges minus undercharges</div>
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
            {stats?.confirmed_leakage_by_currency && Object.keys(stats.confirmed_leakage_by_currency).length > 0
              ? formatBreakdown(stats.confirmed_leakage_by_currency)
              : renderMoney(Number(stats?.confirmed_leakage_amount || 0))}
          </div>
          <div className="text-[11px] text-emerald-700 mt-1 font-medium">{stats?.confirmed_findings ?? 0} approved findings</div>
        </div>
      </div>

      {/* Grid: Recent Documents & Activity */}
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
            Open Full Document Ingest <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          {recentDocs.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">
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
                        className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${doc.category === 'INVOICE'
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
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${doc.processing_status === 'EXTRACTED'
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

      {/* Grid: Active Cases & Recent Findings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cases List */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-sky-600" />
              <h3 className="text-sm font-bold text-slate-800">Active Reconciliation Batches</h3>
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            {cases.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No reconciliation cases yet.
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
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${c.status === 'RECONCILED'
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
                        {c.potential_leakage_by_currency && Object.keys(c.potential_leakage_by_currency).length > 0
                          ? formatBreakdown(c.potential_leakage_by_currency)
                          : renderMoney(Number(c.potential_leakage_amount || 0), c.currency)}
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
              <h3 className="text-sm font-bold text-slate-800">
                Awaiting Human Review ({recentFindings.length})
              </h3>
              {latestPipelineData?.original_filename && (
                <span className="text-[10px] font-semibold text-amber-800 bg-amber-100/90 border border-amber-300 px-2 py-0.5 rounded-full max-w-[180px] truncate">
                  {latestPipelineData.original_filename}
                </span>
              )}
            </div>
            <Link
              to={latestPipelineData?.document_id ? `/review?documentId=${latestPipelineData.document_id}` : '/review'}
              className="text-xs font-semibold text-sky-600 hover:text-sky-700"
            >
              Review Queue →
            </Link>
          </div>

          {reviewCompletionNotice && (
            <div className="p-3 m-4 mb-0 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center gap-2 animate-in fade-in shadow-sm">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 animate-pulse flex-shrink-0" />
              <span className="font-bold">{reviewCompletionNotice}</span>
            </div>
          )}

          <div className="p-4 flex-1 divide-y divide-slate-100 overflow-y-auto max-h-[380px]">
            {recentFindings.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs space-y-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto opacity-80" />
                <p className="font-bold text-slate-700">
                  {latestPipelineData?.original_filename
                    ? `All Findings Reviewed for ${latestPipelineData.original_filename}!`
                    : 'All Findings Reviewed!'}
                </p>
                <p className="text-[11px] text-slate-400">
                  Human review is complete. You can inspect exports, generated reports, or view the review archive.
                </p>
                <div className="flex items-center justify-center gap-2 pt-2">
                  <Link
                    to="/reports"
                    className="inline-flex items-center gap-1 text-xs font-semibold px-3.5 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white shadow-sm transition-all"
                  >
                    Go to Reports & Exports <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                  <Link
                    to={latestPipelineData?.document_id ? `/review?documentId=${latestPipelineData.document_id}` : '/review'}
                    className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 transition-all"
                  >
                    Review Archive
                  </Link>
                </div>
              </div>
            ) : (
              recentFindings.map((f) => (
                <div key={f.id} className="py-3 first:pt-0 last:pb-0 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800 truncate">{f.invoice_reference}</span>
                    <span className={`text-xs font-bold ${Number(f.potential_difference) >= 0 ? 'text-rose-600' : 'text-sky-600'}`}>
                      {Number(f.potential_difference) >= 0 ? '+' : ''}{renderMoney(Number(f.potential_difference), f.currency)}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 truncate flex items-center justify-between">
                    <span>{f.supplier_name}</span>
                    <span className="text-[10px] font-medium bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                      {f.finding_category.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <Link
                      to={`/findings/${f.id}`}
                      className="text-[11px] text-sky-600 font-semibold hover:underline flex items-center gap-0.5"
                    >
                      Inspect Evidence <ArrowRight className="w-3 h-3" />
                    </Link>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleQuickDecision(f.id, 'REJECT', f.case_id)}
                        disabled={actioningId === f.id}
                        className="px-2 py-1 rounded-md border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 text-[11px] font-semibold transition-all flex items-center gap-1 disabled:opacity-50"
                        title="Reject Finding"
                      >
                        <XCircle className="w-3 h-3" />
                        Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => handleQuickDecision(f.id, 'CONFIRM', f.case_id)}
                        disabled={actioningId === f.id}
                        className="px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold transition-all flex items-center gap-1 shadow-sm disabled:opacity-50"
                        title="Confirm Finding"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        Confirm
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {recentFindings.length > 0 && (
            <div className="p-3 bg-slate-50 border-t border-slate-100 text-center">
              <Link
                to={latestPipelineData?.document_id ? `/review?documentId=${latestPipelineData.document_id}` : '/review'}
                className="text-xs font-semibold text-sky-600 hover:text-sky-700 inline-flex items-center gap-1"
              >
                Open Review Queue for {latestPipelineData?.original_filename || 'File'} <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
