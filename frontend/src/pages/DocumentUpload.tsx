import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { ReconciliationCase, UploadedDocument } from '../types';
import { AutomatedRecognitionPipelineView } from '../components/pipeline/AutomatedRecognitionPipelineView';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  FileSpreadsheet,
  FileCheck,
  HardDrive,
  Folder,
  FolderOpen,
  Zap,
  Play,
  RotateCcw,
  Eye,
  Download,
  ChevronRight,
  CornerLeftUp,
  X,
  Search,
  Check,
  Sparkles,
  Trash2
} from 'lucide-react';

interface BatchIngestResult {
  filename: string;
  file_path: string;
  category: string;
  status: string;
  document_id?: string;
  message: string;
}

interface FsDirectory {
  name: string;
  path: string;
  file_count: number;
}

interface FsFile {
  name: string;
  path: string;
  size_bytes: number;
  file_type: string;
  category: string;
}

interface FsBrowseData {
  current_path: string;
  parent_path: string | null;
  directories: FsDirectory[];
  files: FsFile[];
  total_files: number;
  total_dirs: number;
}

interface DocumentPreviewData {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  category: string;
  storage_path: string;
  preview_text: string;
}

export const DocumentUpload: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const caseIdFromQuery = searchParams.get('caseId') || '';
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState(caseIdFromQuery);
  const [category, setCategory] = useState('AUTO');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedDocument[]>([]);
  const [filterQuery, setFilterQuery] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadedPipelineResult, setUploadedPipelineResult] = useState<any | null>(null);

  // Navigation tabs: 'BROWSE' is the default active tab!
  const [activeTab, setActiveTab] = useState<'BROWSE' | 'EXPLORER' | 'PATH'>('BROWSE');

  // Selected browser files staging
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Filesystem Explorer state
  const [fsData, setFsData] = useState<FsBrowseData | null>(null);
  const [fsLoading, setFsLoading] = useState(false);
  const [fsCurrentPath, setFsCurrentPath] = useState<string>('');

  // Direct Path Ingestion state
  const [directFilePath, setDirectFilePath] = useState('synthetic_dataset/sample_files/invoices/INV-2026-1001.csv');
  const [directFolderPath, setDirectFolderPath] = useState('synthetic_dataset/sample_files/invoices');
  const [folderCategory, setFolderCategory] = useState('AUTO');
  const [batchResults, setBatchResults] = useState<BatchIngestResult[]>([]);
  const [batchSummary, setBatchSummary] = useState<{
    total_found: number;
    ingested_count: number;
    skipped_duplicates: number;
    errors: number;
  } | null>(null);

  // Preview Modal state
  const [previewDoc, setPreviewDoc] = useState<DocumentPreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    fetchCases();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      fetchUploadedDocuments(selectedCaseId);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    if (activeTab === 'EXPLORER' && !fsData) {
      fetchFilesystem();
    }
  }, [activeTab]);

  const fetchCases = async () => {
    try {
      const res = await apiClient.get('/cases/');
      setCases(res.data);
      if (!selectedCaseId && res.data.length > 0) {
        setSelectedCaseId(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to load cases:', err);
    }
  };

  const fetchUploadedDocuments = async (cId: string) => {
    try {
      const res = await apiClient.get(`/cases/${cId}/documents`);
      setUploadedFiles(res.data);
    } catch (err) {
      console.error('Failed to load case documents:', err);
    }
  };

  // Upload files to backend (shared by auto-upload and manual upload)
  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return;

    let targetCaseId = selectedCaseId;
    if (!targetCaseId && cases.length > 0) {
      targetCaseId = cases[0].id;
      setSelectedCaseId(targetCaseId);
    }
    if (!targetCaseId) {
      setUploadMessage('Please select or create an active reconciliation batch case first.');
      return;
    }

    setUploading(true);
    setUploadMessage(null);
    setUploadedPipelineResult(null);

    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    formData.append('category', category);

    try {
      const res = await apiClient.post(`/cases/${targetCaseId}/documents/batch-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const data = res.data || {};
      setUploadMessage(data.message || 'Files uploaded and processed successfully! Redirecting to dashboard...');

      let newDocId = data.document_id || data.pipeline?.document_id;
      let newDocName = data.original_filename || data.pipeline?.original_filename || files[0]?.name;

      // Prefer the pipeline-shaped payload returned by the batch endpoint
      if (data.pipeline) {
        setUploadedPipelineResult(data.pipeline);
      } else if (data.recognized_data || data.automated_steps) {
        setUploadedPipelineResult(data);
      }

      if (newDocId) {
        sessionStorage.setItem('last_uploaded_document_id', newDocId);
        if (newDocName) sessionStorage.setItem('last_uploaded_document_name', newDocName);
      }

      setStagedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = '';

      // Auto upload & extracting done → directly go to the dashboard and show the output!
      navigate(newDocId ? `/dashboard?documentId=${newDocId}` : '/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setUploadMessage(
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
            : 'Failed to upload selected files.'
      );
      setStagedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } finally {
      setUploading(false);
    }
  };

  // 1. Browser File Picker Selection → auto-upload immediately
  const handleFileSelection = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      setStagedFiles(filesArray);
      setUploadMessage(null);
      // Immediately upload & extract the selected files
      uploadFiles(filesArray);
    }
  };

  const handleDropFiles = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files);
      setStagedFiles(filesArray);
      setUploadMessage(null);
      uploadFiles(filesArray);
    }
  };

  const removeStagedFile = (index: number) => {
    setStagedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUploadStagedFiles = async () => {
    await uploadFiles(stagedFiles);
  };

  // 2. Local Filesystem Browser
  const fetchFilesystem = async (targetPath?: string) => {
    setFsLoading(true);
    try {
      const url = targetPath ? `/cases/browse/filesystem?path=${encodeURIComponent(targetPath)}` : '/cases/browse/filesystem';
      const res = await apiClient.get(url);
      setFsData(res.data);
      setFsCurrentPath(res.data.current_path);
    } catch (err: any) {
      console.error('Filesystem browse error:', err);
    } finally {
      setFsLoading(false);
    }
  };

  const handleIngestSingleFsFile = async (filePath: string, inferredCat: string) => {
    if (!selectedCaseId) return;
    setUploading(true);
    setUploadMessage(null);
    try {
      const res = await apiClient.post(`/cases/${selectedCaseId}/documents/by-path`, {
        file_path: filePath,
        category: inferredCat,
      });
      setUploadMessage(res.data.message || 'File ingested from disk path successfully.');
      if (res.data?.recognized_data || res.data?.automated_steps) {
        setUploadedPipelineResult(res.data);
      }
      fetchUploadedDocuments(selectedCaseId);
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      setUploadMessage(err.response?.data?.detail || 'Failed to ingest file.');
    } finally {
      setUploading(false);
    }
  };

  const handleIngestCurrentFolder = async () => {
    if (!fsCurrentPath || !selectedCaseId) return;
    setUploading(true);
    setUploadMessage(null);
    try {
      const res = await apiClient.post(`/cases/${selectedCaseId}/documents/by-folder`, {
        folder_path: fsCurrentPath,
        category: 'AUTO',
      });
      setUploadMessage(`Folder ingested: ${res.data.ingested_count} extracted, ${res.data.skipped_duplicates} duplicate(s) skipped.`);
      const latestRes = await apiClient.get('/cases/pipeline/latest').catch(() => null);
      if (latestRes?.data) setUploadedPipelineResult(latestRes.data);
      fetchUploadedDocuments(selectedCaseId);
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      setUploadMessage(err.response?.data?.detail || 'Failed to ingest current folder.');
    } finally {
      setUploading(false);
    }
  };

  // 3. Direct Single Path & Folder Ingestion
  const handleDirectPathIngest = async () => {
    if (!directFilePath.trim() || !selectedCaseId) return;
    setUploading(true);
    setUploadMessage(null);
    try {
      const res = await apiClient.post(`/cases/${selectedCaseId}/documents/by-path`, {
        file_path: directFilePath.trim(),
        category: category === 'AUTO' ? undefined : category,
      });
      setUploadMessage(res.data.message || 'File registered from disk path and extracted.');
      if (res.data?.recognized_data || res.data?.automated_steps) {
        setUploadedPipelineResult(res.data);
      }
      fetchUploadedDocuments(selectedCaseId);
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      setUploadMessage(err.response?.data?.detail || 'Failed to ingest file from path.');
    } finally {
      setUploading(false);
    }
  };

  const handleDirectFolderIngest = async (customFolder?: string, customCat?: string) => {
    const targetFolder = customFolder || directFolderPath;
    const targetCat = customCat || folderCategory;
    if (!targetFolder.trim() || !selectedCaseId) return;

    setUploading(true);
    setUploadMessage(null);
    setBatchResults([]);
    setBatchSummary(null);

    try {
      const res = await apiClient.post(`/cases/${selectedCaseId}/documents/by-folder`, {
        folder_path: targetFolder.trim(),
        category: targetCat,
      });
      const data = res.data;
      setBatchSummary({
        total_found: data.total_found,
        ingested_count: data.ingested_count,
        skipped_duplicates: data.skipped_duplicates,
        errors: data.errors,
      });
      setBatchResults(data.results || []);
      setUploadMessage(
        `Batch Complete: ${data.ingested_count} newly extracted, ${data.skipped_duplicates} duplicate(s) skipped.`
      );
      const latestRes = await apiClient.get('/cases/pipeline/latest').catch(() => null);
      if (latestRes?.data) setUploadedPipelineResult(latestRes.data);
      fetchUploadedDocuments(selectedCaseId);
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      setUploadMessage(err.response?.data?.detail || 'Failed to batch ingest folder.');
    } finally {
      setUploading(false);
    }
  };

  // 4. Document Preview & Download
  const handleOpenPreview = async (docId: string) => {
    if (!selectedCaseId) return;
    setPreviewLoading(true);
    try {
      const res = await apiClient.get(`/cases/${selectedCaseId}/documents/${docId}/preview`);
      setPreviewDoc(res.data);
    } catch (err) {
      console.error('Failed to load document preview:', err);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDownloadDocument = (docId: string, filename: string) => {
    if (!selectedCaseId) return;
    const downloadUrl = `/v1/cases/${selectedCaseId}/documents/${docId}/download`;
    const token = localStorage.getItem('token') || localStorage.getItem('access_token');

    // Trigger browser download with authorization
    fetch(downloadUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
      .then((res) => res.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch((err) => console.error('Download error:', err));
  };

  const handleDeleteDocument = async (docId: string, filename: string) => {
    if (!selectedCaseId) return;
    if (!window.confirm(`Are you sure you want to delete and clear "${filename}"?`)) return;

    try {
      await apiClient.delete(`/cases/${selectedCaseId}/documents/${docId}`);
      setUploadMessage(`Document "${filename}" was deleted successfully.`);
      fetchUploadedDocuments(selectedCaseId);
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  const handleClearAllDocuments = async () => {
    if (!selectedCaseId) return;
    if (!window.confirm('Are you sure you want to delete ALL documents in this reconciliation batch? This will clear all files and unreviewed findings.')) return;

    try {
      const res = await apiClient.delete(`/cases/${selectedCaseId}/documents`);
      setUploadMessage(res.data.message || 'All documents cleared.');
      setUploadedPipelineResult(null);
      fetchUploadedDocuments(selectedCaseId);
      setTimeout(() => {
        navigate('/dashboard');
      }, 700);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to clear documents');
    }
  };

  const filteredDocs = uploadedFiles.filter(
    (d) =>
      d.original_filename.toLowerCase().includes(filterQuery.toLowerCase()) ||
      d.category.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Document Upload & Filesystem Browser</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Browse files on your computer, explore local disk directories, or ingest zero-memory filesystem paths
          </p>
        </div>

        {selectedCaseId && (
          <Link
            to={`/documents/status?caseId=${selectedCaseId}`}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow transition-all"
          >
            <Clock className="w-4 h-4" />
            Inspect Processing Status & Run
          </Link>
        )}
      </div>

      {/* Case Selector */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-sky-600" />
          Active Reconciliation Batch:
        </label>
        <select
          value={selectedCaseId}
          onChange={(e) => setSelectedCaseId(e.target.value)}
          className="w-full sm:w-96 px-3 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
        >
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.case_reference} - {c.title}
            </option>
          ))}
        </select>
      </div>

      {/* Mode Switch Tabs */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab('BROWSE')}
          className={`flex items-center gap-2 py-3 px-6 text-xs font-bold border-b-2 transition-all ${activeTab === 'BROWSE'
              ? 'border-sky-600 text-sky-700 bg-sky-50/50'
              : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
        >
          <UploadCloud className="w-4 h-4 text-sky-600" />
          📁 Browse & Upload Files
          <span className="px-2 py-0.5 rounded-full bg-sky-100 text-sky-800 text-[10px] uppercase font-bold">
            Interactive Picker
          </span>
        </button>

        <button
          onClick={() => setActiveTab('EXPLORER')}
          className={`flex items-center gap-2 py-3 px-6 text-xs font-bold border-b-2 transition-all ${activeTab === 'EXPLORER'
              ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50'
              : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
        >
          <FolderOpen className="w-4 h-4 text-indigo-600" />
          🗂️ Local Filesystem Explorer
          <span className="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800 text-[10px] uppercase font-bold">
            Direct Disk
          </span>
        </button>

        <button
          onClick={() => setActiveTab('PATH')}
          className={`flex items-center gap-2 py-3 px-6 text-xs font-bold border-b-2 transition-all ${activeTab === 'PATH'
              ? 'border-emerald-600 text-emerald-700 bg-emerald-50/50'
              : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
        >
          <HardDrive className="w-4 h-4 text-emerald-600" />
          ⚡ Zero-Memory Path Ingest
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] uppercase font-bold">
            Presets
          </span>
        </button>
      </div>

      {/* ============================================================== */}
      {/* TAB 1: BROWSE & UPLOAD FILES (NATIVE FILE PICKER) */}
      {/* ============================================================== */}
      {activeTab === 'BROWSE' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 md:p-8 space-y-6">
          {/* Category selection */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Select Document Category
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
              {[
                { id: 'AUTO', name: 'Auto-Detect', icon: Zap },
                { id: 'INVOICE', name: 'Supplier Invoice', icon: FileText },
                { id: 'CONTRACT', name: 'Supplier Contract', icon: FileCheck },
                { id: 'PRICE_SCHEDULE', name: 'Price Schedule', icon: FileSpreadsheet },
                { id: 'PURCHASE_ORDER', name: 'Purchase Order', icon: FileText },
                { id: 'GOODS_RECEIVED_NOTE', name: 'Goods Received (GRN)', icon: CheckCircle2 },
              ].map((cat) => {
                const Icon = cat.icon;
                const isSelected = category === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setCategory(cat.id)}
                    className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${isSelected
                        ? 'border-sky-500 bg-sky-50 text-sky-900 font-semibold ring-2 ring-sky-500/20'
                        : 'border-slate-200 hover:border-slate-300 bg-slate-50/50 text-slate-600'
                      }`}
                  >
                    <Icon className={`w-4 h-4 mb-1 ${isSelected ? 'text-sky-600' : 'text-slate-400'}`} />
                    <span className="text-[11px] leading-tight">{cat.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Hidden File Input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelection}
            accept=".pdf,.csv,.xlsx,.xls"
            multiple
            className="hidden"
            id="browse-file-input"
          />

          {/* Interactive File Drop & Browse Box */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDropFiles}
            className="border-2 border-dashed border-sky-300 hover:border-sky-500 rounded-2xl p-8 text-center transition-colors bg-sky-50/30 flex flex-col items-center"
          >
            <div className="w-16 h-16 rounded-2xl bg-sky-100 text-sky-600 flex items-center justify-center shadow-inner mb-3">
              <UploadCloud className="w-8 h-8" />
            </div>

            <p className="text-base font-bold text-slate-900">
              Select or Drag & Drop Documents to Upload
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-md">
              Select one or multiple PDFs, CSV spreadsheets, or XLSX workbooks from your computer
            </p>

            {/* Prominent Browse Button */}
            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-md hover:shadow-lg transition-all flex items-center gap-2"
              >
                <FolderOpen className="w-4 h-4" />
                Browse Computer Files...
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('EXPLORER')}
                className="px-4 py-2.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-sm transition-all flex items-center gap-2"
              >
                <HardDrive className="w-4 h-4 text-slate-500" />
                Browse Local Disk Folders
              </button>
            </div>

            <div className="mt-5 px-3.5 py-1.5 rounded-full bg-white border border-slate-200 text-[11px] font-medium text-slate-600 shadow-sm flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Automated SHA-256 Hash Verification & Instant Line Item Parser
            </div>
          </div>

          {/* Staged Files Preview List (shown during auto-upload) */}
          {stagedFiles.length > 0 && (
            <div className="p-4 rounded-xl border border-sky-200 bg-sky-50/50 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-sky-950 uppercase tracking-wider flex items-center gap-2">
                  {uploading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-sky-600"></div>
                      Auto-Uploading & Extracting ({stagedFiles.length} file{stagedFiles.length > 1 ? 's' : ''})...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-sky-600" />
                      {stagedFiles.length} file{stagedFiles.length > 1 ? 's' : ''} selected
                    </>
                  )}
                </span>
              </div>

              <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                {stagedFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-white border border-slate-200 text-xs"
                  >
                    <div className="flex items-center gap-2.5 truncate max-w-md">
                      <FileText className="w-4 h-4 text-sky-600 flex-shrink-0" />
                      <span className="font-semibold text-slate-800 truncate">{file.name}</span>
                      <span className="text-[10px] text-slate-400">({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {uploading && (
            <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 text-sky-800 text-xs flex items-center gap-3">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-sky-600"></div>
              <span>Uploading files, verifying SHA-256 hashes, and extracting line items...</span>
            </div>
          )}

          {uploadMessage && !uploading && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm animate-in fade-in">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-slate-900">Document Processing & Financial Reconciliation Complete</p>
                  <p className="font-bold text-slate-900">Document Processing Complete — Loading Live on Dashboard...</p>
                  <p className="text-emerald-800 text-[11px] mt-0.5 leading-relaxed">{uploadMessage}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  to="/"
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center gap-1.5 shadow transition-all text-xs"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  View Live on Dashboard
                </Link>
                <Link
                  to={`/reconciliation?caseId=${selectedCaseId}`}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-semibold flex items-center gap-1 transition-all text-xs"
                >
                  Inspect Case <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* TAB 2: LOCAL FILESYSTEM EXPLORER (BROWSE DIRECTORIES ON DISK) */}
      {/* ============================================================== */}
      {activeTab === 'EXPLORER' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 md:p-8 space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-200">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-indigo-600" />
                Local Disk Directory Explorer
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Navigate folders and pick documents directly from your workspace disk without browser memory buffering
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => fetchFilesystem()}
                className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Root
              </button>

              <button
                type="button"
                disabled={uploading || !fsData}
                onClick={handleIngestCurrentFolder}
                className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow flex items-center gap-1.5 disabled:opacity-50"
              >
                <Zap className="w-3.5 h-3.5" />
                Ingest Entire Current Folder
              </button>
            </div>
          </div>

          {/* Current Path Bar & Parent Navigation */}
          <div className="flex items-center gap-2 bg-slate-50 p-2.5 rounded-xl border border-slate-200">
            {fsData?.parent_path ? (
              <button
                type="button"
                onClick={() => fetchFilesystem(fsData.parent_path!)}
                className="p-1.5 rounded-lg bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs flex items-center gap-1 font-semibold flex-shrink-0"
                title="Go to Parent Folder"
              >
                <CornerLeftUp className="w-3.5 h-3.5" />
                Up
              </button>
            ) : null}

            <span className="text-xs text-slate-400 font-bold">Path:</span>
            <input
              type="text"
              value={fsCurrentPath}
              onChange={(e) => setFsCurrentPath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchFilesystem(fsCurrentPath)}
              className="flex-1 px-2.5 py-1 bg-white border border-slate-200 rounded text-xs font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <button
              type="button"
              onClick={() => fetchFilesystem(fsCurrentPath)}
              className="px-3 py-1 bg-slate-200 hover:bg-slate-300 rounded text-xs font-semibold text-slate-700"
            >
              Go
            </button>
          </div>

          {fsLoading ? (
            <div className="p-8 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
              <span>Scanning directory...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Directories List */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Folder className="w-4 h-4 text-amber-500" />
                  Subdirectories ({fsData?.directories.length || 0})
                </span>

                <div className="border border-slate-200 rounded-xl max-h-72 overflow-y-auto divide-y divide-slate-100 bg-white">
                  {fsData?.directories.length === 0 ? (
                    <div className="p-4 text-center text-xs text-slate-400">No subdirectories found</div>
                  ) : (
                    fsData?.directories.map((dir, i) => (
                      <div
                        key={i}
                        onClick={() => fetchFilesystem(dir.path)}
                        className="p-2.5 flex items-center justify-between hover:bg-indigo-50/60 cursor-pointer transition-colors group"
                      >
                        <div className="flex items-center gap-2 truncate">
                          <Folder className="w-4 h-4 text-amber-500 flex-shrink-0" />
                          <span className="text-xs font-semibold text-slate-800 group-hover:text-indigo-700 truncate">
                            {dir.name}
                          </span>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold group-hover:bg-indigo-100 group-hover:text-indigo-800">
                          {dir.file_count} files
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Files in Current Directory */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-sky-600" />
                  Files in this folder ({fsData?.files.length || 0})
                </span>

                <div className="border border-slate-200 rounded-xl max-h-72 overflow-y-auto divide-y divide-slate-100 bg-white">
                  {fsData?.files.length === 0 ? (
                    <div className="p-4 text-center text-xs text-slate-400">No supported files in this folder</div>
                  ) : (
                    fsData?.files.map((file, i) => (
                      <div key={i} className="p-2.5 flex items-center justify-between hover:bg-slate-50 transition-colors">
                        <div className="truncate max-w-[200px] flex items-center gap-2">
                          <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                          <span className="text-xs font-semibold text-slate-800 truncate" title={file.name}>
                            {file.name}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            ({(file.size_bytes / 1024).toFixed(1)} KB)
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            {file.category}
                          </span>
                          <button
                            type="button"
                            disabled={uploading}
                            onClick={() => handleIngestSingleFsFile(file.path, file.category)}
                            className="px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[11px] font-bold transition-colors flex items-center gap-1 disabled:opacity-50"
                          >
                            <Play className="w-3 h-3" />
                            Ingest
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {uploading && (
            <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-900 text-xs flex items-center gap-3">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-indigo-600"></div>
              <span>Ingesting file from disk path with zero memory buffering...</span>
            </div>
          )}

          {uploadMessage && !uploading && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm animate-in fade-in">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-slate-900">Document Processing & Financial Reconciliation Complete</p>
                  <p className="font-bold text-slate-900">Document Processing Complete — Loading Live on Dashboard...</p>
                  <p className="text-emerald-800 text-[11px] mt-0.5 leading-relaxed">{uploadMessage}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  to="/"
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center gap-1.5 shadow transition-all text-xs"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  View Live on Dashboard
                </Link>
                <Link
                  to={`/reconciliation?caseId=${selectedCaseId}`}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-semibold flex items-center gap-1 transition-all text-xs"
                >
                  Inspect Case <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* TAB 3: ZERO-MEMORY PATH INGEST (PRESETS & MANUAL PATHS) */}
      {/* ============================================================== */}
      {activeTab === 'PATH' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 md:p-8 space-y-6">
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-start gap-3">
            <Zap className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Zero-Memory Direct Filesystem Ingestion</p>
              <p className="text-emerald-800 text-[11px] mt-0.5 leading-relaxed">
                The application streams files sequentially from disk using 64 KB chunks without holding document buffers
                in RAM or browser memory.
              </p>
            </div>
          </div>

          {/* Quick Preset Buttons for Synthetic Dataset */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Quick Ingest from Synthetic Dataset Folders
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
              {[
                {
                  label: 'Invoices (65 files)',
                  folder: 'synthetic_dataset/sample_files/invoices',
                  cat: 'INVOICE',
                  icon: FileText,
                },
                {
                  label: 'Contracts (20 files)',
                  folder: 'synthetic_dataset/sample_files/contracts',
                  cat: 'CONTRACT',
                  icon: FileCheck,
                },
                {
                  label: 'Purchase Orders (25 files)',
                  folder: 'synthetic_dataset/sample_files/pos',
                  cat: 'PURCHASE_ORDER',
                  icon: FileText,
                },
                {
                  label: 'GRNs (15 files)',
                  folder: 'synthetic_dataset/sample_files/grns',
                  cat: 'GOODS_RECEIVED_NOTE',
                  icon: CheckCircle2,
                },
                {
                  label: 'ALL Folders (125 files)',
                  folder: 'synthetic_dataset/sample_files',
                  cat: 'AUTO',
                  icon: Folder,
                },
              ].map((btn, idx) => {
                const Icon = btn.icon;
                return (
                  <button
                    key={idx}
                    type="button"
                    disabled={uploading}
                    onClick={() => {
                      setDirectFolderPath(btn.folder);
                      setFolderCategory(btn.cat);
                      handleDirectFolderIngest(btn.folder, btn.cat);
                    }}
                    className="flex flex-col items-start p-3 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-emerald-50/70 hover:border-emerald-300 transition-all text-left group"
                  >
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800 group-hover:text-emerald-700">
                      <Icon className="w-4 h-4 text-slate-500 group-hover:text-emerald-600" />
                      <span>{btn.label}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono mt-1 truncate w-full">
                      {btn.folder}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-200">
            {/* Direct Single File Ingest */}
            <div className="space-y-3 bg-slate-50/50 p-4 rounded-xl border border-slate-200">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-sky-600" />
                Single File Direct Path
              </span>
              <input
                type="text"
                value={directFilePath}
                onChange={(e) => setDirectFilePath(e.target.value)}
                placeholder="e.g. C:\Invoices\INV-2026-001.pdf or synthetic_dataset/..."
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              <div className="flex items-center gap-3">
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs text-slate-800 bg-white"
                >
                  <option value="AUTO">Auto Detect</option>
                  <option value="INVOICE">Supplier Invoice</option>
                  <option value="CONTRACT">Contract</option>
                  <option value="PRICE_SCHEDULE">Price Schedule</option>
                  <option value="PURCHASE_ORDER">Purchase Order</option>
                  <option value="GOODS_RECEIVED_NOTE">Goods Received (GRN)</option>
                </select>

                <button
                  type="button"
                  disabled={uploading}
                  onClick={handleDirectPathIngest}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold flex items-center justify-center gap-1.5 shadow transition-all disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5" />
                  Direct Ingest File
                </button>
              </div>
            </div>

            {/* Direct Folder Ingest */}
            <div className="space-y-3 bg-slate-50/50 p-4 rounded-xl border border-slate-200">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Folder className="w-4 h-4 text-emerald-600" />
                Directory / Folder Batch Path
              </span>
              <input
                type="text"
                value={directFolderPath}
                onChange={(e) => setDirectFolderPath(e.target.value)}
                placeholder="e.g. C:\FinancialDocs\Invoices\ or synthetic_dataset/sample_files"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono text-slate-900 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <div className="flex items-center gap-3">
                <select
                  value={folderCategory}
                  onChange={(e) => setFolderCategory(e.target.value)}
                  className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs text-slate-800 bg-white"
                >
                  <option value="AUTO">AUTO (Detect from folder/filename)</option>
                  <option value="INVOICE">Supplier Invoices</option>
                  <option value="CONTRACT">Contracts</option>
                  <option value="PRICE_SCHEDULE">Price Schedules</option>
                  <option value="PURCHASE_ORDER">Purchase Orders</option>
                  <option value="GOODS_RECEIVED_NOTE">Goods Received (GRN)</option>
                </select>

                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => handleDirectFolderIngest()}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 shadow transition-all disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5" />
                  Ingest Entire Folder
                </button>
              </div>
            </div>
          </div>

          {batchSummary && (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
              <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                <span>Batch Processing Summary:</span>
                <div className="flex items-center gap-4 text-[11px]">
                  <span className="text-slate-600">Total Scanned: <strong>{batchSummary.total_found}</strong></span>
                  <span className="text-emerald-700 font-semibold">Extracted: <strong>{batchSummary.ingested_count}</strong></span>
                  <span className="text-amber-700">Duplicates Skipped: <strong>{batchSummary.skipped_duplicates}</strong></span>
                  {batchSummary.errors > 0 && <span className="text-rose-700">Errors: <strong>{batchSummary.errors}</strong></span>}
                </div>
              </div>
            </div>
          )}

          {uploading && (
            <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 text-sky-800 text-xs flex items-center gap-3">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-sky-600"></div>
              <span>Processing files directly from disk path, streaming hashes, and extracting data structures...</span>
            </div>
          )}

          {uploadMessage && !uploading && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-950 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm animate-in fade-in">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-slate-900">Document Processing & Financial Reconciliation Complete</p>
                  <p className="font-bold text-slate-900">Document Processing Complete — Loading Live on Dashboard...</p>
                  <p className="text-emerald-800 text-[11px] mt-0.5 leading-relaxed">{uploadMessage}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  to="/"
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center gap-1.5 shadow transition-all text-xs"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  View Live on Dashboard
                </Link>
                <Link
                  to={`/reconciliation?caseId=${selectedCaseId}`}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-semibold flex items-center gap-1 transition-all text-xs"
                >
                  Inspect Case <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* 🚀 AUTOMATED RECOGNITION & MULTI-WAY PIPELINE RESULT */}
      {/* ============================================================== */}
      {uploadedPipelineResult && (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              Ingested Document: Everything Recognized & Multi-Way Automated Outcomes
            </span>
            <button
              type="button"
              onClick={() => setUploadedPipelineResult(null)}
              className="text-xs font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
            >
              <X className="w-3.5 h-3.5" /> Close View
            </button>
          </div>
          <AutomatedRecognitionPipelineView
            pipelineData={uploadedPipelineResult}
            onClose={() => setUploadedPipelineResult(null)}
          />
        </div>
      )}

      {/* ============================================================== */}
      {/* UPLOADED DOCUMENTS BROWSER & VIEWER */}
      {/* ============================================================== */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50">
          <div>
            <h3 className="text-sm font-bold text-slate-800">
              Uploaded Evidence Documents ({uploadedFiles.length})
            </h3>
            <p className="text-[11px] text-slate-500">
              Browse, preview file content, and inspect extracted fields for each uploaded document
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                placeholder="Filter documents..."
                className="pl-8 pr-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-500 w-48"
              />
            </div>

            {uploadedFiles.length > 0 && selectedCaseId && (
              <>
                <button
                  type="button"
                  onClick={handleClearAllDocuments}
                  className="text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 px-2.5 py-1.5 rounded-lg border border-rose-200 transition-colors flex items-center gap-1 shadow-sm"
                  title="Clear all documents in this batch"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear All Files
                </button>

                <Link
                  to={`/documents/status?caseId=${selectedCaseId}`}
                  className="text-xs font-semibold text-sky-600 hover:text-sky-700 flex items-center gap-1"
                >
                  Inspect Extracted Fields <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Filename</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Size</th>
                <th className="py-3 px-4">SHA-256 Hash</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Uploaded</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400">
                    No documents found. Browse and upload files from your computer or disk above.
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-900 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                      <span className="truncate max-w-[220px]" title={doc.original_filename}>
                        {doc.original_filename}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="bg-slate-100 text-slate-700 font-medium px-2 py-0.5 rounded text-[11px]">
                        {doc.category.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">{(doc.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400">{doc.sha256_hash.substring(0, 14)}...</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${doc.processing_status === 'EXTRACTED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : doc.processing_status === 'FAILED'
                              ? 'bg-rose-100 text-rose-800'
                              : 'bg-sky-100 text-sky-800'
                          }`}
                      >
                        {doc.processing_status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500">{new Date(doc.created_at).toLocaleDateString()}</td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Preview Document Button */}
                        <button
                          type="button"
                          onClick={() => handleOpenPreview(doc.id)}
                          className="p-1.5 text-slate-500 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors"
                          title="Preview Document Content"
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        {/* Download Document Button */}
                        <button
                          type="button"
                          onClick={() => handleDownloadDocument(doc.id, doc.original_filename)}
                          className="p-1.5 text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                          title="Download Original File"
                        >
                          <Download className="w-4 h-4" />
                        </button>

                        {/* Delete Document Button */}
                        <button
                          type="button"
                          onClick={() => handleDeleteDocument(doc.id, doc.original_filename)}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                          title="Delete / Clear Document"
                        >
                          <Trash2 className="w-4 h-4" />
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

      {/* ============================================================== */}
      {/* DOCUMENT PREVIEW MODAL */}
      {/* ============================================================== */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-sky-100 text-sky-600 flex items-center justify-center">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-slate-900">{previewDoc.filename}</h4>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span className="font-semibold text-sky-700">{previewDoc.category}</span>
                    <span>•</span>
                    <span>{(previewDoc.size_bytes / 1024).toFixed(1)} KB</span>
                    <span>•</span>
                    <span>Format: {previewDoc.file_type.toUpperCase()}</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setPreviewDoc(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-4 flex-1">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] font-mono text-slate-600 break-all">
                <span className="font-bold text-slate-800">Source Disk Path: </span>
                {previewDoc.storage_path}
              </div>

              <div>
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2">
                  Document Content Preview
                </span>
                <pre className="bg-slate-900 text-slate-100 p-4 rounded-xl font-mono text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-96">
                  {previewDoc.preview_text || 'No preview text extracted.'}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 border-t border-slate-200 flex items-center justify-between bg-slate-50 text-xs">
              <span className="text-slate-500 text-[11px]">
                Showing first 120 lines from disk
              </span>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleDownloadDocument(previewDoc.id, previewDoc.filename)}
                  className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-semibold flex items-center gap-1.5 shadow-sm"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download File
                </button>

                <button
                  type="button"
                  onClick={() => setPreviewDoc(null)}
                  className="px-4 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
