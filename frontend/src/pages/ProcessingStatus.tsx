import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ReconciliationCase, UploadedDocument, ExtractedField } from '../types';
import {
  Clock,
  Sparkles,
  FileText,
  CheckCircle2,
  AlertCircle,
  Edit2,
  Check,
  X,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';

export const ProcessingStatus: React.FC = () => {
  const [searchParams] = useSearchParams();
  const caseIdFromQuery = searchParams.get('caseId') || '';
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdFromQuery);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<UploadedDocument | null>(null);
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [editingFieldId, setEditingFieldId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [runningReconciliation, setRunningReconciliation] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchCases();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      fetchDocuments(selectedCaseId);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    if (selectedDoc) {
      fetchFields(selectedCaseId, selectedDoc.id);
    }
  }, [selectedDoc]);

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

  const fetchDocuments = async (cId: string) => {
    try {
      setLoading(true);
      const res = await apiClient.get(`/cases/${cId}/documents`);
      setDocuments(res.data);
      if (res.data.length > 0) {
        setSelectedDoc(res.data[0]);
      } else {
        setSelectedDoc(null);
        setFields([]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFields = async (cId: string, docId: string) => {
    try {
      const res = await apiClient.get(`/cases/${cId}/documents/${docId}/fields`);
      setFields(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditField = (field: ExtractedField) => {
    setEditingFieldId(field.id);
    setEditValue(field.reviewed_value || field.extracted_value || '');
  };

  const handleSaveField = async (fieldId: string) => {
    try {
      await apiClient.patch(`/cases/fields/${fieldId}`, {
        reviewed_value: editValue,
      });
      setEditingFieldId(null);
      if (selectedDoc) fetchFields(selectedCaseId, selectedDoc.id);
    } catch (err) {
      console.error('Failed to update field:', err);
    }
  };

  const handleRunReconciliation = async () => {
    if (!selectedCaseId) return;
    setRunningReconciliation(true);
    try {
      await apiClient.post(`/cases/${selectedCaseId}/run`);
      navigate(`/reconciliation?caseId=${selectedCaseId}`);
    } catch (err) {
      console.error('Failed to run reconciliation:', err);
    } finally {
      setRunningReconciliation(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Document Processing & Provenance</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Inspect AI extraction confidence, review field citations, and trigger multi-way reconciliation
          </p>
        </div>

        {selectedCaseId && documents.length > 0 && (
          <button
            onClick={handleRunReconciliation}
            disabled={runningReconciliation}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-all disabled:opacity-50"
          >
            {runningReconciliation ? (
              <>
                <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-white"></div>
                Executing Reconciliation Engine...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Run Financial Reconciliation
              </>
            )}
          </button>
        )}
      </div>

      {/* Case Selector */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
        <label className="text-xs font-bold text-slate-700 uppercase tracking-wider">
          Active Case:
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document Master List */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="px-5 py-3.5 border-b border-slate-200 bg-slate-50/50">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Documents in Batch ({documents.length})
            </h3>
          </div>
          <div className="divide-y divide-slate-100 flex-1 overflow-y-auto">
            {documents.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                No documents uploaded. <Link to={`/documents/upload?caseId=${selectedCaseId}`} className="text-sky-600 font-semibold underline">Upload now</Link>
              </div>
            ) : (
              documents.map((doc) => {
                const isSelected = selectedDoc?.id === doc.id;
                return (
                  <button
                    key={doc.id}
                    onClick={() => setSelectedDoc(doc)}
                    className={`w-full text-left p-4 hover:bg-slate-50 transition-colors flex items-center justify-between ${
                      isSelected ? 'bg-sky-50/60 border-l-4 border-sky-600' : ''
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="font-semibold text-xs text-slate-900 truncate max-w-[200px]">
                        {doc.original_filename}
                      </div>
                      <div className="text-[11px] text-slate-500 flex items-center gap-2">
                        <span>{doc.category.replace(/_/g, ' ')}</span>
                        <span>•</span>
                        <span>{(doc.file_size_bytes / 1024).toFixed(0)} KB</span>
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      doc.processing_status === 'EXTRACTED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {doc.processing_status}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Extracted Fields & Provenance Viewer */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Extracted Provenance & Audit Trail
              </h3>
              <p className="text-[11px] text-slate-500">
                Document: <span className="font-semibold text-slate-800">{selectedDoc?.original_filename || 'None selected'}</span>
              </p>
            </div>
            {selectedDoc && (
              <span className="text-[11px] bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md font-mono">
                SHA-256: {selectedDoc.sha256_hash.substring(0, 12)}...
              </span>
            )}
          </div>

          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Field Name</th>
                  <th className="py-3 px-4">Extracted Value</th>
                  <th className="py-3 px-4">Source Provenance</th>
                  <th className="py-3 px-4">Method / Confidence</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {fields.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      No extracted fields for this document or processing pending.
                    </td>
                  </tr>
                ) : (
                  fields.map((f) => {
                    const isEditing = editingFieldId === f.id;
                    const displayValue = f.reviewed_value || f.extracted_value || '—';
                    return (
                      <tr key={f.id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3 px-4 font-semibold text-slate-800 font-mono text-[11px]">
                          {f.field_name}
                        </td>
                        <td className="py-3 px-4 font-medium text-slate-900">
                          {isEditing ? (
                            <input
                              type="text"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              className="px-2 py-1 border border-sky-500 rounded text-xs w-full focus:outline-none"
                              autoFocus
                            />
                          ) : (
                            <div className="flex items-center gap-1.5">
                              <span>{displayValue}</span>
                              {f.reviewed_value && (
                                <span className="text-[9px] bg-amber-100 text-amber-800 font-bold px-1 rounded">
                                  MANUAL EDIT
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-slate-500">{f.source_page_or_cell || 'Header'}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                              {f.extraction_method}
                            </span>
                            {f.confidence_score && (
                              <span className="text-[10px] text-emerald-600 font-bold">
                                {Math.round(Number(f.confidence_score) * 100)}%
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          {isEditing ? (
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => handleSaveField(f.id)}
                                className="p-1 rounded bg-emerald-600 text-white hover:bg-emerald-500"
                              >
                                <Check className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setEditingFieldId(null)}
                                className="p-1 rounded bg-slate-200 text-slate-600 hover:bg-slate-300"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => handleEditField(f)}
                              className="text-slate-400 hover:text-sky-600 transition-colors p-1"
                              title="Edit extracted value"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

