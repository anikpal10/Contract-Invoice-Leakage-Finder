import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { AuditLog } from '../types';
import { History, ShieldCheck, UserCheck, Clock, FileText, ArrowRight } from 'lucide-react';

export const AuditHistory: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuditLogs();
  }, []);

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/audit/?limit=100');
      setLogs(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Immutable Audit Trail & Activity History</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Tamper-evident log of all case creation, document uploads, reconciliation executions, and reviewer decisions
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4">Action Event</th>
                <th className="py-3 px-4">Resource Target</th>
                <th className="py-3 px-4">Resource ID</th>
                <th className="py-3 px-4">Change Payload / Context</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">Loading audit trail...</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">No audit logs recorded yet.</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-mono text-slate-500 text-[11px]">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">
                      <span className="bg-slate-100 text-slate-800 px-2 py-0.5 rounded font-mono text-[11px]">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sky-700 font-semibold text-[11px]">
                        {log.resource_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400 text-[11px]">
                      {log.resource_id.substring(0, 16)}...
                    </td>
                    <td className="py-3 px-4">
                      <pre className="text-[10px] font-mono bg-slate-50 border border-slate-200 p-1.5 rounded max-w-md overflow-x-auto text-slate-600">
                        {JSON.stringify(log.payload_after || log.payload_before || {}, null, 1)}
                      </pre>
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

