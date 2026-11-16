import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { ShieldCheck, Lock, Mail, ArrowRight, UserCheck } from 'lucide-react';

export const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await apiClient.post('/auth/login', { email, password });
      const data = res.data;
      login(
        data.access_token,
        {
          id: data.user_id,
          email: data.email,
          full_name: data.full_name,
          role: data.role,
          is_active: true,
          organization_id: data.organization_id,
          created_at: new Date().toISOString()
        },
        data.organization_name
      );
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  const fillQuickDemo = (roleEmail: string) => {
    setEmail(roleEmail);
    setPassword('Password123!');
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-sky-600 shadow-xl shadow-sky-600/30 mb-4">
          <ShieldCheck className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          CONTRACT & INVOICE LEAKAGE FINDER
        </h2>
        <p className="mt-2 text-xs text-slate-400">
          Deterministic Financial Exception Engine & Multi-Way Reconciliation
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-900 py-8 px-6 shadow-2xl rounded-xl sm:px-10 border border-slate-800">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs">
              {error}
            </div>
          )}

          <form className="space-y-4" onSubmit={handleLogin}>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Business Email</label>
              <div className="relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="block w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
              <div className="relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="block w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center items-center gap-2 py-2.5 px-4 border border-transparent rounded-lg text-sm font-semibold text-white bg-sky-600 hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 transition-all shadow-md shadow-sky-900/50"
            >
              {loading ? 'Authenticating...' : 'Sign In to Workspace'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Quick Demo Access Buttons */}
          <div className="mt-6 pt-6 border-t border-slate-800">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <UserCheck className="w-3.5 h-3.5 text-sky-400" />
              1-Click Demo Accounts (Pre-Seeded)
            </p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => fillQuickDemo('admin@apexretail.co.uk')}
                className="p-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded text-left transition-colors"
              >
                <div className="font-semibold text-indigo-400">Admin</div>
                <div className="text-[10px] text-slate-400">Full Config & RBAC</div>
              </button>
              <button
                type="button"
                onClick={() => fillQuickDemo('manager@apexretail.co.uk')}
                className="p-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded text-left transition-colors"
              >
                <div className="font-semibold text-sky-400">Manager</div>
                <div className="text-[10px] text-slate-400">Cases & Reports</div>
              </button>
              <button
                type="button"
                onClick={() => fillQuickDemo('reviewer@apexretail.co.uk')}
                className="p-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded text-left transition-colors"
              >
                <div className="font-semibold text-emerald-400">Reviewer</div>
                <div className="text-[10px] text-slate-400">Confirm/Reject Findings</div>
              </button>
              <button
                type="button"
                onClick={() => fillQuickDemo('viewer@apexretail.co.uk')}
                className="p-2 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded text-left transition-colors"
              >
                <div className="font-semibold text-slate-400">Viewer</div>
                <div className="text-[10px] text-slate-500">Read-Only Audit</div>
              </button>
            </div>
          </div>

          <div className="mt-4 text-center">
            <span className="text-xs text-slate-400">Need a new organization? </span>
            <Link to="/register" className="text-xs font-semibold text-sky-400 hover:text-sky-300">
              Register Organization
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

