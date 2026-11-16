import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppLayout } from './components/layout/AppLayout';

import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Dashboard } from './pages/Dashboard';
import { CreateCase } from './pages/CreateCase';
import { DocumentUpload } from './pages/DocumentUpload';
import { ProcessingStatus } from './pages/ProcessingStatus';
import { ReconciliationResults } from './pages/ReconciliationResults';
import { FindingsManagement } from './pages/FindingsManagement';
import { FindingDetails } from './pages/FindingDetails';
import { HumanReview } from './pages/HumanReview';
import { ReportsExports } from './pages/ReportsExports';
import { AdminSettings } from './pages/AdminSettings';
import { UserManagement } from './pages/UserManagement';
import { AuditHistory } from './pages/AuditHistory';

const ProtectedRoute: React.FC<{ children: React.ReactNode; roles?: string[] }> = ({ children, roles }) => {
  const { user, token, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900 text-white">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-500"></div>
      </div>
    );
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <AppLayout>{children}</AppLayout>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected Routes */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/workspaces" element={<Navigate to="/dashboard" replace />} />
          <Route path="/suppliers" element={<Navigate to="/dashboard" replace />} />
          <Route path="/cases/new" element={<ProtectedRoute><CreateCase /></ProtectedRoute>} />
          <Route path="/documents/upload" element={<ProtectedRoute><DocumentUpload /></ProtectedRoute>} />
          <Route path="/documents/status" element={<ProtectedRoute><ProcessingStatus /></ProtectedRoute>} />
          <Route path="/reconciliation" element={<ProtectedRoute><ReconciliationResults /></ProtectedRoute>} />
          <Route path="/findings" element={<ProtectedRoute><FindingsManagement /></ProtectedRoute>} />
          <Route path="/findings/:findingId" element={<ProtectedRoute><FindingDetails /></ProtectedRoute>} />
          <Route path="/review" element={<ProtectedRoute><HumanReview /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute><ReportsExports /></ProtectedRoute>} />
          <Route path="/admin/settings" element={<ProtectedRoute roles={['ADMIN']}><AdminSettings /></ProtectedRoute>} />
          <Route path="/admin/users" element={<ProtectedRoute roles={['ADMIN']}><UserManagement /></ProtectedRoute>} />
          <Route path="/audit" element={<ProtectedRoute><AuditHistory /></ProtectedRoute>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

