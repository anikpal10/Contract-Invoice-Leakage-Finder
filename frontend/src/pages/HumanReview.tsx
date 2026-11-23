import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { apiClient } from '../api/client';
import { Finding, ReconciliationCase, UploadedDocument } from '../types';
import { renderMoney } from '../utils/currency';
import {
  CheckSquare,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ArrowRight,
  TrendingDown,
  Building2,
  Clock,
  ShieldAlert,
  FileText,
  Filter
} from 'lucide-react';

export const HumanReview: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('ALL');
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'PENDING' | 'HISTORY'>('PENDING');
  const [redirectNotice, setRedirectNotice] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchInitial();
  }, []);

  const fetchInitial = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/cases/');
      setCases(res.data);
      if (res.data.length > 0) {
        const queryCaseId = searchParams.get('caseId');
        const cId = (queryCaseId && res.data.some((c: any) => c.id === queryCaseId)) ? queryCaseId : res.data[0].id;
        setSelectedCaseId(cId);

        // Fetch documents for the selected case
        let docsList: UploadedDocument[] = [];
        try {
          const docsRes = await apiClient.get(`/cases/${cId}/documents`);
          docsList = docsRes.data || [];
          setDocuments(docsList);
        } catch (e) {
          console.error('Failed to load case documents:', e);
        }

        // Determine which document to filter to (prioritize URL query param, then sessionStorage, then latest uploaded)
        const queryDocId = searchParams.get('documentId');
        const storedDocId = sessionStorage.getItem('last_uploaded_document_id');
        let initialDocId = 'ALL';

        if (queryDocId && docsList.some((d) => d.id === queryDocId)) {
          initialDocId = queryDocId;
        } else if (storedDocId && docsList.some((d) => d.id === storedDocId)) {
          initialDocId = storedDocId;
        } else if (docsList.length > 0) {
          // Default to the most recently uploaded file so only its awaiting decisions appear!
          initialDocId = docsList[0].id;
        }

        setSelectedDocId(initialDocId);
        await fetchFindings(cId, initialDocId);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFindings = async (cId: string, docId: string = 'ALL') => {
    try {
      setLoading(true);
      const endpoint = (docId && docId !== 'ALL')
        ? `/cases/${cId}/findings?document_id=${docId}`
        : `/cases/${cId}/findings`;
      const res = await apiClient.get(endpoint);
      setFindings(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCaseChange = async (cId: string) => {
    setSelectedCaseId(cId);
    let docsList: UploadedDocument[] = [];
    try {
      const docsRes = await apiClient.get(`/cases/${cId}/documents`);
      docsList = docsRes.data || [];
      setDocuments(docsList);
    } catch (e) {
      console.error(e);
    }
    const nextDocId = docsList.length > 0 ? docsList[0].id : 'ALL';
    setSelectedDocId(nextDocId);
    fetchFindings(cId, nextDocId);
  };

  const handleDocumentChange = (docId: string) => {
    setSelectedDocId(docId);
    if (docId && docId !== 'ALL') {
      sessionStorage.setItem('last_uploaded_document_id', docId);
      setSearchParams({ caseId: selectedCaseId, documentId: docId });
    } else {
      setSearchParams(selectedCaseId ? { caseId: selectedCaseId } : {});
    }
    fetchFindings(selectedCaseId, docId);
  };

  const activeDoc = documents.find((d) => d.id === selectedDocId);

  const handleQuickDecision = async (findingId: string, action: 'CONFIRM' | 'REJECT' | 'REQUEST_INFO') => {
    setActioningId(findingId);
    try {
      await apiClient.post(`/findings/${findingId}/decisions`, {
        action,
        comment: `Quick review action: ${action}`
      });

      const remaining = pendingFindings.filter((f) => f.id !== findingId);
      if (remaining.length === 0) {
        const fileLabel = activeDoc?.original_filename ? ` for ${activeDoc.original_filename}` : '';
        setRedirectNotice(`All awaiting decisions completed${fileLabel}! Human review done — routing to Reports & Exports...`);
        setTimeout(() => {
          const docParam = selectedDocId && selectedDocId !== 'ALL' ? `&documentId=${selectedDocId}` : '';
          navigate(selectedCaseId ? `/reports?caseId=${selectedCaseId}${docParam}` : '/reports');
        }, 1100);
      } else {
        fetchFindings(selectedCaseId, selectedDocId);
      }
    } catch (err) {
      console.error('Failed to update decision:', err);
    } finally {
      setActioningId(null);
    }
  };

  const pendingFindings = findings.filter((f) => f.review_status === 'NEW' || f.review_status === 'UNDER_REVIEW');
  const reviewedFindings = findings.filter((f) => f.review_status !== 'NEW' && f.review_status !== 'UNDER_REVIEW');

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Human Review & Approval Queue</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Only human reviewers can confirm financial discrepancies. Review candidate leakage and authorize exceptions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Case Selector */}
          <select
            value={selectedCaseId}
            onChange={(e) => handleCaseChange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-sky-500 shadow-sm"
          >
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.case_reference} - {c.title}
              </option>
            ))}
          </select>

          {/* Document / Uploaded File Selector */}
          <select
            value={selectedDocId}
            onChange={(e) => handleDocumentChange(e.target.value)}
            className="px-3 py-2 border border-indigo-200 rounded-lg text-sm font-medium text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm max-w-[280px] truncate"
            title="Filter by uploaded file"
          >
            {documents.length > 0 && (
              <optgroup label="Uploaded Documents">
                {documents.map((d, idx) => (
                  <option key={d.id} value={d.id}>
                    {idx === 0 ? '⭐ (Latest) ' : '📄 '}{d.original_filename}
                  </option>
                ))}
              </optgroup>
            )}
            <option value="ALL">📁 All Case Documents ({documents.length} files)</option>
          </select>
        </div>
      </div>

      {/* Uploaded File Filter Focus Pill */}
      {selectedDocId !== 'ALL' && activeDoc && (
        <div className="p-3.5 rounded-xl bg-amber-50/90 border border-amber-200/80 text-amber-900 text-xs flex items-center justify-between shadow-sm animate-in fade-in">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>
              Showing awaiting decisions exclusively for uploaded file: <b className="font-bold text-amber-950">{activeDoc.original_filename}</b> ({pendingFindings.length} awaiting decision)
            </span>
          </div>
          <button
            type="button"
            onClick={() => handleDocumentChange('ALL')}
            className="text-amber-800 hover:text-amber-950 font-bold underline text-xs ml-3 whitespace-nowrap"
          >
            Show All Documents
          </button>
        </div>
      )}

      {redirectNotice && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-900 text-xs flex items-center gap-2.5 animate-in fade-in shadow-sm">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 animate-pulse flex-shrink-0" />
          <span className="font-bold">{redirectNotice}</span>
        </div>
      )}

      {/* Review Queue Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-amber-800 uppercase tracking-wider">Awaiting Decision</div>
            <div className="text-2xl font-bold text-amber-900 mt-1">{pendingFindings.length}</div>
            {activeDoc && selectedDocId !== 'ALL' && (
              <div className="text-[11px] text-amber-700 font-medium truncate max-w-[200px]">for {activeDoc.original_filename}</div>
            )}
          </div>
          <Clock className="w-6 h-6 text-amber-600" />
        </div>
        <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-emerald-800 uppercase tracking-wider">Confirmed Exceptions</div>
            <div className="text-2xl font-bold text-emerald-900 mt-1">
              {findings.filter((f) => f.review_status === 'CONFIRMED').length}
            </div>
          </div>
          <CheckCircle2 className="w-6 h-6 text-emerald-600" />
        </div>
        <div className="bg-slate-100 border border-slate-200 p-4 rounded-xl flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">Rejected Findings</div>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {findings.filter((f) => f.review_status === 'REJECTED').length}
            </div>
          </div>
          <XCircle className="w-6 h-6 text-slate-500" />
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('PENDING')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'PENDING'
            ? 'bg-amber-600 text-white shadow-sm'
            : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
        >
          <Clock className="w-4 h-4" />
          Awaiting Decision ({pendingFindings.length})
        </button>
        <button
          onClick={() => setActiveTab('HISTORY')}
          className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${activeTab === 'HISTORY'
            ? 'bg-slate-900 text-white shadow-sm'
            : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
            }`}
        >
          <CheckCircle2 className="w-4 h-4" />
          Reviewed History & Archive ({reviewedFindings.length})
        </button>
      </div>

      {/* Main Content Area */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900">
            {activeTab === 'PENDING'
              ? `Pending Review Workbench (${pendingFindings.length})`
              : `Reviewed Decisions Archive (${reviewedFindings.length})`}
          </h3>
          <span className="text-xs text-slate-500">
            {activeTab === 'PENDING'
              ? 'Exceptions requiring human analyst confirmation or rejection'
              : 'Permanent audit record of human reviews & decisions'}
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {loading ? (
            <div className="p-8 text-center text-slate-400 text-xs">Loading review queue...</div>
          ) : activeTab === 'PENDING' ? (
            pendingFindings.length === 0 ? (
              <div className="p-10 text-center text-slate-500 text-xs space-y-3">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto opacity-80" />
                <p className="font-bold text-sm text-slate-800">All findings have been reviewed for this case!</p>
                <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                  Every exception has been evaluated and confirmed or rejected. You can proceed directly to audit reports and dossier exports.
                </p>
                <div className="pt-2 flex items-center justify-center gap-3">
                  <button
                    onClick={() => setActiveTab('HISTORY')}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-sm transition-all"
                  >
                    View Decision History ({reviewedFindings.length})
                  </button>
                  <Link
                    to={selectedCaseId ? `/reports?caseId=${selectedCaseId}${selectedDocId && selectedDocId !== 'ALL' ? `&documentId=${selectedDocId}` : ''}` : '/reports'}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow transition-all"
                  >
                    Go to Reports & Exports <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ) : (
              pendingFindings.map((f) => (
                <div key={f.id} className="p-5 hover:bg-slate-50/60 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">{f.invoice_reference}</span>
                      <span className="text-xs text-slate-500 font-medium">({f.supplier_name})</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${f.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' :
                        f.severity === 'HIGH' ? 'bg-orange-100 text-orange-800' :
                          'bg-amber-100 text-amber-800'
                        }`}>
                        {f.severity}
                      </span>
                      <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[11px] font-semibold">
                        {f.finding_category.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 line-clamp-2 max-w-3xl">
                      {f.calculation_explanation}
                    </p>

                    <div className="text-[11px] text-slate-500 flex items-center gap-4 pt-1">
                      <span>Expected: <b className="text-slate-700">{renderMoney(Number(f.expected_amount), f.currency)}</b></span>
                      <span>Invoiced: <b className="text-slate-700">{renderMoney(Number(f.invoiced_amount), f.currency)}</b></span>
                      <span>Variance: <b className={Number(f.potential_difference) >= 0 ? "text-rose-600 font-bold" : "text-sky-600 font-bold"}>
                        {Number(f.potential_difference) >= 0 ? '+' : ''}{renderMoney(Number(f.potential_difference), f.currency)}
                      </b></span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleQuickDecision(f.id, 'REQUEST_INFO')}
                      disabled={actioningId === f.id}
                      className="p-2 rounded-lg border border-purple-200 bg-purple-50 text-purple-700 hover:bg-purple-100 text-xs font-semibold flex items-center gap-1 transition-all"
                      title="Request More Information"
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                      Info
                    </button>
                    <button
                      onClick={() => handleQuickDecision(f.id, 'REJECT')}
                      disabled={actioningId === f.id}
                      className="p-2 rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 text-xs font-semibold flex items-center gap-1 transition-all"
                      title="Reject Finding"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Reject
                    </button>
                    <button
                      onClick={() => handleQuickDecision(f.id, 'CONFIRM')}
                      disabled={actioningId === f.id}
                      className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition-all"
                      title="Confirm Finding"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Confirm
                    </button>
                    <Link
                      to={`/findings/${f.id}`}
                      className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold"
                      title="Detailed view"
                    >
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>
                </div>
              ))
            )
          ) : (
            /* Reviewed History Archive View */
            reviewedFindings.length === 0 ? (
              <div className="p-10 text-center text-slate-500 text-xs">
                No reviewed findings in this case yet. Use the "Awaiting Decision" tab to confirm or reject findings.
              </div>
            ) : (
              reviewedFindings.map((f) => {
                const latestDecision = f.decisions && f.decisions.length > 0 ? f.decisions[f.decisions.length - 1] : null;
                return (
                  <div key={f.id} className="p-5 hover:bg-slate-50/60 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-900">{f.invoice_reference}</span>
                        <span className="text-xs text-slate-500 font-medium">({f.supplier_name})</span>

                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${f.review_status === 'CONFIRMED'
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                          : f.review_status === 'REJECTED'
                            ? 'bg-slate-200 text-slate-800 border border-slate-300'
                            : 'bg-purple-100 text-purple-800 border border-purple-300'
                          }`}>
                          {f.review_status === 'CONFIRMED' && '✓ Confirmed Exception'}
                          {f.review_status === 'REJECTED' && '✕ Rejected Finding'}
                          {f.review_status === 'NEEDS_MORE_INFO' && '? More Info Requested'}
                        </span>

                        <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[11px] font-semibold">
                          {f.finding_category.replace(/_/g, ' ')}
                        </span>
                      </div>

                      <p className="text-xs text-slate-600 line-clamp-2 max-w-3xl">
                        {f.calculation_explanation}
                      </p>

                      <div className="text-[11px] text-slate-500 flex flex-wrap items-center gap-4 pt-1">
                        <span>Expected: <b className="text-slate-700">{renderMoney(Number(f.expected_amount), f.currency)}</b></span>
                        <span>Invoiced: <b className="text-slate-700">{renderMoney(Number(f.invoiced_amount), f.currency)}</b></span>
                        <span>Variance: <b className="text-slate-800">
                          {Number(f.potential_difference) >= 0 ? '+' : ''}{renderMoney(Number(f.potential_difference), f.currency)}
                        </b></span>
                        {latestDecision && (
                          <span className="text-slate-400">
                            Reviewed by: <b className="text-slate-600">{latestDecision.reviewer_name}</b> on{' '}
                            {new Date(latestDecision.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleQuickDecision(f.id, 'RESET' as any)}
                        disabled={actioningId === f.id}
                        className="px-2.5 py-1.5 rounded-lg border border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-semibold transition-all"
                        title="Move back to Pending Decision queue"
                      >
                        Re-open for Review
                      </button>

                      {/* Reversal / Change Decision buttons */}
                      {f.review_status === 'CONFIRMED' ? (
                        <button
                          onClick={() => handleQuickDecision(f.id, 'REJECT')}
                          disabled={actioningId === f.id}
                          className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-rose-50 hover:text-rose-700 text-slate-600 text-xs font-semibold transition-all"
                          title="Switch to Rejected"
                        >
                          Change to Reject
                        </button>
                      ) : (
                        <button
                          onClick={() => handleQuickDecision(f.id, 'CONFIRM')}
                          disabled={actioningId === f.id}
                          className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-emerald-50 hover:text-emerald-700 text-slate-600 text-xs font-semibold transition-all"
                          title="Switch to Confirmed"
                        >
                          Change to Confirm
                        </button>
                      )}

                      <Link
                        to={`/findings/${f.id}`}
                        className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold"
                        title="Detailed view"
                      >
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>
                  </div>
                );
              })
            )
          )}
        </div>
      </div>
    </div>
  );
};
