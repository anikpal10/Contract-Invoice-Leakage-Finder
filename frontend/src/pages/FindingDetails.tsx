import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { Finding } from '../types';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileText,
  ShieldCheck,
  TrendingDown,
  Building2,
  Calendar,
  MessageSquare,
  Clock
} from 'lucide-react';

export const FindingDetails: React.FC = () => {
  const { findingId } = useParams<{ findingId: string }>();
  const [finding, setFinding] = useState<Finding | null>(null);
  const [comment, setComment] = useState('');
  const [adjustedAmount, setAdjustedAmount] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (findingId) fetchFinding(findingId);
  }, [findingId]);

  const fetchFinding = async (id: string) => {
    try {
      setLoading(true);
      const res = await apiClient.get(`/findings/${id}`);
      setFinding(res.data);
      setAdjustedAmount(String(res.data.potential_difference));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (action: 'CONFIRM' | 'REJECT' | 'REQUEST_INFO') => {
    if (!finding) return;
    setSubmitting(true);
    try {
      const res = await apiClient.post(`/findings/${finding.id}/decisions`, {
        action,
        comment: comment || null,
        adjusted_amount: adjustedAmount ? Number(adjustedAmount) : null
      });
      setFinding(res.data);
      setComment('');
    } catch (err) {
      console.error('Failed to submit review decision:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !finding) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Register
        </button>
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
            finding.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800 border border-rose-300' :
            finding.severity === 'HIGH' ? 'bg-orange-100 text-orange-800 border border-orange-300' :
            'bg-amber-100 text-amber-800'
          }`}>
            Severity: {finding.severity}
          </span>
          <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
            finding.review_status === 'CONFIRMED' ? 'bg-emerald-100 text-emerald-800' :
            finding.review_status === 'REJECTED' ? 'bg-slate-200 text-slate-700' :
            finding.review_status === 'NEEDS_MORE_INFO' ? 'bg-purple-100 text-purple-800' :
            'bg-sky-100 text-sky-800'
          }`}>
            Status: {finding.review_status.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      {/* Main Finding Overview Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 md:p-8 space-y-6">
        <div>
          <div className="text-xs font-bold text-sky-600 uppercase tracking-wider">
            {finding.finding_category.replace(/_/g, ' ')}
          </div>
          <h2 className="text-xl font-bold text-slate-900 mt-1">
            Invoice {finding.invoice_reference} {finding.line_number ? `• Line ${finding.line_number}` : ''}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
            <Building2 className="w-3.5 h-3.5" />
            Supplier: <b className="text-slate-800">{finding.supplier_name}</b>
          </p>
        </div>

        {/* Side-by-Side Financial Math Comparison */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-5 rounded-xl bg-slate-50 border border-slate-200 text-center">
          <div>
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Contracted / Expected</div>
            <div className="mt-1 text-2xl font-bold text-slate-800">
              £{Number(finding.expected_amount).toFixed(2)}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Authorised by PO / Contract</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">Invoiced Charge</div>
            <div className="mt-1 text-2xl font-bold text-slate-900">
              £{Number(finding.invoiced_amount).toFixed(2)}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Stated on supplier invoice</div>
          </div>
          <div className="border-t md:border-t-0 md:border-l border-slate-200 pt-3 md:pt-0">
            <div className="text-xs text-rose-600 font-bold uppercase tracking-wider">Potential Difference</div>
            <div className="mt-1 text-2xl font-bold text-rose-600">
              +£{Number(finding.potential_difference).toFixed(2)}
            </div>
            <div className="text-[11px] text-rose-600 mt-0.5 font-medium">Candidate leakage exposure</div>
          </div>
        </div>

        {/* Audit Calculation Explanation */}
        <div className="p-4 rounded-xl bg-sky-50/50 border border-sky-100">
          <h4 className="text-xs font-bold text-sky-950 uppercase tracking-wider mb-1 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-sky-600" />
            Deterministic Reconciliation Explanation
          </h4>
          <p className="text-xs text-slate-700 leading-relaxed">
            {finding.calculation_explanation}
          </p>
        </div>

        {/* Evidence Citations */}
        <div>
          <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-slate-500" />
            Linked Source Evidence Citations
          </h4>
          <div className="space-y-2">
            {finding.source_document_references?.map((ref, idx) => (
              <div key={idx} className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-xs flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sky-700">{ref.type || 'DOCUMENT'}:</span>
                  <span className="text-slate-800 font-medium">
                    {ref.invoice_number || ref.contract_reference || ref.po_number || ref.grn_number || ref.document_id}
                  </span>
                </div>
                <div className="text-slate-500 text-[11px]">
                  {ref.source || ref.line ? `Location: ${ref.source || 'Line ' + ref.line}` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Human Review Decision History */}
        <div>
          <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-slate-500" />
            Audit Review Decision Trail
          </h4>
          <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
            {(!finding.decisions || finding.decisions.length === 0) ? (
              <div className="p-4 text-center text-xs text-slate-400">
                No human review actions recorded yet. Finding is currently awaiting review.
              </div>
            ) : (
              finding.decisions.map((d) => (
                <div key={d.id} className="p-3.5 bg-white text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">{d.reviewer_name}</span>
                    <span className="text-[11px] text-slate-400">
                      {new Date(d.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sky-600">{d.action}</span>
                    <span className="text-slate-400">({d.previous_status} → {d.new_status})</span>
                  </div>
                  {d.comment && (
                    <p className="text-slate-600 bg-slate-50 p-2 rounded mt-1 text-[11px] italic">
                      "{d.comment}"
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Human Reviewer Action Box */}
        <div className="p-5 rounded-2xl bg-slate-900 text-white space-y-4">
          <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            Human Review Decision Workbench
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Adjusted Potential Amount (£)</label>
              <input
                type="number"
                step="0.01"
                value={adjustedAmount}
                onChange={(e) => setAdjustedAmount(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Reviewer Note / Justification</label>
              <input
                type="text"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Reason for confirmation or rejection..."
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-slate-800">
            <button
              onClick={() => handleDecision('REQUEST_INFO')}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-all"
            >
              <HelpCircle className="w-3.5 h-3.5 text-purple-400" />
              Request More Info
            </button>
            <button
              onClick={() => handleDecision('REJECT')}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-200 border border-rose-800 text-xs font-semibold transition-all"
            >
              <XCircle className="w-3.5 h-3.5" />
              Reject Finding
            </button>
            <button
              onClick={() => handleDecision('CONFIRM')}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition-all"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Confirm Exception
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

