import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { PipelineResultFinding, AutomatedStepItem } from '../../types';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  ArrowRight,
  TrendingDown,
  Layers,
  Sparkles,
  ShieldCheck,
  Check,
  Zap,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  FileCheck
} from 'lucide-react';

interface Props {
  pipelineData: {
    original_filename: string;
    category: string;
    case_reference?: string;
    case_title?: string;
    case_id: string;
    recognized_data?: Record<string, any>;
    findings?: PipelineResultFinding[];
    findings_count?: number;
    potential_leakage?: number;
    automated_steps?: AutomatedStepItem[];
  };
  onClose?: () => void;
}

export const AutomatedRecognitionPipelineView: React.FC<Props> = ({ pipelineData, onClose }) => {
  const [activeTab, setActiveTab] = useState<'RECOGNITION' | 'PIPELINE' | 'FINDINGS'>('FINDINGS');
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);

  const recognized = pipelineData.recognized_data || {};
  const lineItems: any[] = recognized.line_items || [];
  const findings: PipelineResultFinding[] = pipelineData.findings || [];
  const steps: AutomatedStepItem[] = pipelineData.automated_steps || [];
  const findingsCount = pipelineData.findings_count ?? findings.length;
  const potentialLeakage = Number(pipelineData.potential_leakage ?? 0);

  const toggleFinding = (id: string) => {
    setExpandedFindingId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="bg-white rounded-2xl border-2 border-indigo-200 shadow-xl overflow-hidden animate-in fade-in duration-200">
      {/* Top Status Header */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-5 md:p-6 border-b border-indigo-900">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold border border-emerald-500/40">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                Automatic Recognition & Multi-Way Reconciliation Completed
              </span>
              <span className="text-xs text-indigo-200 font-mono bg-indigo-900/60 px-2 py-0.5 rounded">
                {pipelineData.case_reference || 'Active Audit Case'}
              </span>
            </div>
            <h2 className="text-lg md:text-xl font-bold flex items-center gap-2">
              <FileText className="w-5 h-5 text-sky-400" />
              <span>{pipelineData.original_filename || 'Uploaded Document'}</span>
              <span className="text-xs font-normal text-slate-300">
                ({(pipelineData.category || 'DOCUMENT').replace(/_/g, ' ')})
              </span>
            </h2>
            <p className="text-xs text-indigo-200 mt-1">
              Case: <b className="text-white">{pipelineData.case_title || 'Procurement Reconciliation'}</b>
            </p>
          </div>

          {/* Quick Metrics Badge */}
          <div className="flex items-center gap-3">
            <div className="px-4 py-2.5 rounded-xl bg-white/10 backdrop-blur border border-white/10 text-right">
              <div className="text-[10px] text-slate-300 font-semibold uppercase tracking-wider">
                Total Billed
              </div>
              <div className="text-base font-bold text-white">
                £{Number(recognized.total_amount || 0).toLocaleString('en-GB', { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div className={`px-4 py-2.5 rounded-xl border text-right ${
              findingsCount > 0
                ? 'bg-rose-500/20 border-rose-500/40 text-rose-200'
                : 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200'
            }`}>
              <div className="text-[10px] font-semibold uppercase tracking-wider">
                {findingsCount > 0 ? 'Variance Exposure' : 'Audit Status'}
              </div>
              <div className={`text-base font-bold ${findingsCount > 0 ? 'text-rose-300' : 'text-emerald-300'}`}>
                {findingsCount > 0 ? `+£${potentialLeakage.toLocaleString('en-GB', { minimumFractionDigits: 2 })}` : 'Clean Match (0 Discrepancy)'}
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 mt-5 border-t border-indigo-900/60 pt-3">
          <button
            type="button"
            onClick={() => setActiveTab('FINDINGS')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'FINDINGS'
                ? 'bg-rose-600 text-white shadow'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            3. What Happened ({findingsCount} Exceptions)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('RECOGNITION')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'RECOGNITION'
                ? 'bg-sky-600 text-white shadow'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            1. Everything Recognized ({lineItems.length} Line Items)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('PIPELINE')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'PIPELINE'
                ? 'bg-indigo-600 text-white shadow'
                : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            2. Automated Processes Executed (6 Steps)
          </button>
        </div>
      </div>

      {/* ============================================================== */}
      {/* TAB 1: 3. WHAT HAPPENED (FINDINGS & RECONCILIATION RESULTS) */}
      {/* ============================================================== */}
      {activeTab === 'FINDINGS' && (
        <div className="p-6 space-y-6">
          {findingsCount === 0 ? (
            <div className="p-8 rounded-xl bg-emerald-50 border border-emerald-200 text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-emerald-950">Clean Reconciliation — No Leakage Detected</h3>
              <p className="text-xs text-emerald-800 max-w-lg mx-auto">
                All recognized line items match the authorized master contract pricing and purchase order quantities exactly. No arithmetic errors, rate variances, or duplicate invoices were detected.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-700 flex items-center justify-center flex-shrink-0">
                    <TrendingDown className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold">
                      {findingsCount} Variance Exception{findingsCount > 1 ? 's' : ''} Identified Automatically
                    </h4>
                    <p className="text-xs text-rose-800">
                      Total financial variance exposure: <b className="text-rose-900">£{potentialLeakage.toLocaleString('en-GB', { minimumFractionDigits: 2 })}</b> requiring review.
                    </p>
                  </div>
                </div>

                <Link
                  to="/review"
                  className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow flex items-center gap-1.5 self-start sm:self-auto"
                >
                  Confirm / Reject in Review Queue <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {/* List of Detailed Findings */}
              <div className="space-y-3">
                {findings.map((f, idx) => {
                  const isExpanded = expandedFindingId === f.id || idx === 0;
                  return (
                    <div
                      key={f.id}
                      className="border border-slate-200 rounded-xl overflow-hidden hover:border-slate-300 transition-all bg-white"
                    >
                      <div
                        onClick={() => toggleFinding(f.id)}
                        className="p-4 bg-slate-50/60 hover:bg-slate-100/60 cursor-pointer flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                              f.severity === 'CRITICAL'
                                ? 'bg-rose-100 text-rose-800'
                                : f.severity === 'HIGH'
                                ? 'bg-orange-100 text-orange-800'
                                : f.severity === 'MEDIUM'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {f.severity}
                          </span>

                          <div>
                            <span className="font-bold text-xs text-slate-900">
                              {(f.finding_category || 'VARIANCE').replace(/_/g, ' ')}
                            </span>
                            {f.item_code && (
                              <span className="ml-2 font-mono text-[11px] bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                                {f.item_code}
                              </span>
                            )}
                            <p className="text-[11px] text-slate-500 truncate max-w-lg mt-0.5">
                              {f.item_description || f.supplier_name}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <span className="text-[10px] text-slate-500 block">Cost Variance</span>
                            <span className="text-sm font-bold text-rose-600">
                              +£{Number(f.potential_difference).toFixed(2)}
                            </span>
                          </div>
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-slate-400" />
                          )}
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="p-4 border-t border-slate-200 bg-white space-y-3">
                          {/* Explanation */}
                          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-800 leading-relaxed">
                            <p className="font-semibold text-slate-900 mb-1">Calculation & Finding Explanation:</p>
                            {f.calculation_explanation}
                          </div>

                          {/* Amounts comparison */}
                          <div className="grid grid-cols-3 gap-3 text-center text-xs">
                            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                              <span className="text-[10px] text-slate-500 block uppercase">Invoiced Amount</span>
                              <span className="font-bold text-slate-900">
                                £{Number(f.invoiced_amount).toFixed(2)}
                              </span>
                            </div>

                            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                              <span className="text-[10px] text-slate-500 block uppercase">Expected (Contract / PO)</span>
                              <span className="font-bold text-emerald-700">
                                £{Number(f.expected_amount).toFixed(2)}
                              </span>
                            </div>

                            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200">
                              <span className="text-[10px] text-rose-600 block uppercase">Difference (Leakage)</span>
                              <span className="font-bold text-rose-700">
                                +£{Number(f.potential_difference).toFixed(2)}
                              </span>
                            </div>
                          </div>

                          {/* Evidence citation links */}
                          {f.source_document_references && f.source_document_references.length > 0 && (
                            <div className="text-[11px] text-slate-600 flex flex-wrap items-center gap-2 pt-1">
                              <span className="font-semibold">Evidence Citations:</span>
                              {f.source_document_references.map((ref: any, refIdx: number) => (
                                <span
                                  key={refIdx}
                                  className="px-2 py-0.5 rounded bg-slate-100 font-mono text-slate-700 border border-slate-200"
                                >
                                  {ref.type}: {ref.invoice_number || ref.contract_reference || ref.po_number || 'Document'} {ref.line ? `(Line ${ref.line})` : ''}
                                </span>
                              ))}
                            </div>
                          )}

                          <div className="pt-2 flex justify-end">
                            <Link
                              to={`/findings/${f.id}`}
                              className="text-xs font-semibold text-sky-600 hover:text-sky-700 flex items-center gap-1"
                            >
                              Inspect Full Provenance & History <ArrowRight className="w-3.5 h-3.5" />
                            </Link>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* TAB 2: 1. EVERYTHING RECOGNIZED (EXTRACTED HEADERS & LINES) */}
      {/* ============================================================== */}
      {activeTab === 'RECOGNITION' && (
        <div className="p-6 space-y-6">
          {/* Header Metadata Cards */}
          <div>
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
              Recognized Document Header & Financial Terms
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Supplier Name</span>
                <span className="text-xs font-bold text-slate-900 truncate block mt-0.5">
                  {recognized.supplier_name || 'Apex Industrial Supplies'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Reference / Invoice #</span>
                <span className="text-xs font-bold text-slate-900 truncate block mt-0.5 font-mono">
                  {recognized.invoice_number || recognized.contract_reference || recognized.po_number || 'INV-2026-1001'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Document Date</span>
                <span className="text-xs font-bold text-slate-900 block mt-0.5">
                  {recognized.invoice_date || recognized.effective_date || recognized.order_date || '2026-10-01'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Currency</span>
                <span className="text-xs font-bold text-slate-900 block mt-0.5">
                  {recognized.currency || 'GBP (£)'}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Subtotal</span>
                <span className="text-xs font-bold text-slate-900 block mt-0.5">
                  £{Number(recognized.subtotal || 0).toFixed(2)}
                </span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Total Amount</span>
                <span className="text-xs font-bold text-emerald-700 block mt-0.5">
                  £{Number(recognized.total_amount || 0).toFixed(2)}
                </span>
              </div>
            </div>
          </div>

          {/* Line Items Table */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Recognized Commercial Line Items ({lineItems.length})
              </h4>
              <span className="text-[11px] text-slate-500">
                AI Recognition Confidence: <b className="text-emerald-700">{Math.round((recognized.confidence || 0.95) * 100)}%</b>
              </span>
            </div>

            <div className="border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="py-2.5 px-3">#</th>
                    <th className="py-2.5 px-3">Item Code</th>
                    <th className="py-2.5 px-3">Product / Service Description</th>
                    <th className="py-2.5 px-3 text-right">Quantity</th>
                    <th className="py-2.5 px-3 text-right">Unit Price</th>
                    <th className="py-2.5 px-3 text-right">Line Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                  {lineItems.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400">
                        No individual line items parsed from this document.
                      </td>
                    </tr>
                  ) : (
                    lineItems.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">
                          {item.line_number || idx + 1}
                        </td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-slate-800 text-[11px]">
                          {item.item_code || '—'}
                        </td>
                        <td className="py-2.5 px-3 font-medium text-slate-900">
                          {item.description || item.product_name || 'Item'}
                        </td>
                        <td className="py-2.5 px-3 text-right font-semibold">
                          {item.quantity ?? item.quantity_received ?? 1}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-900">
                          £{Number(item.unit_price ?? item.contracted_unit_price ?? 0).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                          £{Number(item.line_total ?? (Number(item.quantity || 1) * Number(item.unit_price || 0))).toFixed(2)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* TAB 3: 2. AUTOMATED PROCESSES EXECUTED */}
      {/* ============================================================== */}
      {activeTab === 'PIPELINE' && (
        <div className="p-6 space-y-4">
          <p className="text-xs text-slate-600">
            The following 6-step multi-way financial exception pipeline was executed automatically in background upon file upload:
          </p>

          <div className="space-y-3">
            {steps.map((st, i) => (
              <div
                key={i}
                className="flex items-start gap-3.5 p-3.5 rounded-xl bg-slate-50 border border-slate-200"
              >
                <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Check className="w-4 h-4 font-bold" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{st.name}</span>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full uppercase">
                      {st.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 mt-1">{st.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer Navigation Bar */}
      <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <span className="text-slate-500">
          Reconciliation Batch: <b>{pipelineData.case_reference || 'Active Audit Case'}</b>
        </span>

        <div className="flex items-center gap-2.5">
          <Link
            to={`/reconciliation${pipelineData.case_id ? `?caseId=${pipelineData.case_id}` : ''}`}
            className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold transition-all flex items-center gap-1.5 shadow"
          >
            <span>Inspect Full Case Reconciliation</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 font-semibold transition-colors"
            >
              Close Inspector
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
