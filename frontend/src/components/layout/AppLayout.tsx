import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Building2,
  UploadCloud,
  Clock,
  Sparkles,
  AlertTriangle,
  CheckSquare,
  FileText,
  Sliders,
  Users,
  History,
  LogOut,
  ShieldCheck,
  ChevronRight,
  Menu,
  X
} from 'lucide-react';

export const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, organizationName, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Document Upload', href: '/documents/upload', icon: UploadCloud },
    { name: 'Processing Status', href: '/documents/status', icon: Clock },
    { name: 'Reconciliation Results', href: '/reconciliation', icon: Sparkles },
    { name: 'Findings Register', href: '/findings', icon: AlertTriangle },
    { name: 'Human Review', href: '/review', icon: CheckSquare },
    { name: 'Reports & Exports', href: '/reports', icon: FileText },
    { name: 'Admin Settings', href: '/admin/settings', icon: Sliders, roles: ['ADMIN'] },
    { name: 'User Management', href: '/admin/users', icon: Users, roles: ['ADMIN'] },
    { name: 'Audit History', href: '/audit', icon: History },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const filteredNavigation = navigation.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 antialiased overflow-hidden">
      {/* Sidebar for Desktop */}
      <aside className="hidden md:flex flex-col w-64 bg-slate-950 border-r border-slate-800 flex-shrink-0">
        {/* Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800 gap-3">
          <div className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center text-white shadow-md shadow-sky-900/40">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white leading-tight">
              LEAKAGE FINDER
            </h1>
            <p className="text-[10px] text-slate-400 font-medium tracking-wide uppercase">
              Audit & Exception Engine
            </p>
          </div>
        </div>

        {/* Tenant Organization Badge */}
        <div className="px-4 py-3 border-b border-slate-800/80 bg-slate-900/60">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
            Organization
          </div>
          <div className="text-xs font-medium text-sky-400 truncate flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5 flex-shrink-0" />
            <span className="truncate">{organizationName || 'Default Tenant'}</span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {filteredNavigation.map((item) => {
            const isActive = location.pathname === item.href || location.pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-sky-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/70'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Card & Logout */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div className="truncate">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.full_name}</p>
              <p className="text-[11px] text-slate-400 truncate">{user?.email}</p>
            </div>
            <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
              user?.role === 'ADMIN' ? 'bg-indigo-900/60 text-indigo-300 border border-indigo-700/50' :
              user?.role === 'MANAGER' ? 'bg-sky-900/60 text-sky-300 border border-sky-700/50' :
              user?.role === 'REVIEWER' ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50' :
              'bg-slate-800 text-slate-300'
            }`}>
              {user?.role}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="mt-1 flex items-center justify-center gap-2 w-full py-1.5 px-3 rounded text-xs font-medium text-rose-300 bg-rose-950/30 hover:bg-rose-900/50 border border-rose-900/40 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-slate-100 text-slate-900">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 z-10">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-slate-600 hover:text-slate-900"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
            <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
              <span>Tenant</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-semibold text-slate-800">{organizationName}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center gap-1.5 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1 rounded-full font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Deterministic Engine Active
            </span>
            <div className="text-right">
              <div className="text-xs font-semibold text-slate-800">{user?.full_name}</div>
              <div className="text-[10px] text-slate-500">{user?.role} Role</div>
            </div>
          </div>
        </header>

        {/* Page Content Body */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

