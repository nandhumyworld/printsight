import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { PrinterProvider } from '@/context/PrinterContext';
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import DashboardPage from '@/pages/dashboard/DashboardPage';
import PrintersPage from '@/pages/printers/PrintersPage';
import AddPrinterPage from '@/pages/printers/AddPrinterPage';
import PrinterDetailPage from '@/pages/printers/PrinterDetailPage';
import ColumnMappingPage from '@/pages/printers/ColumnMappingPage';
import AnalyticsPage from '@/pages/analytics/AnalyticsPage';
import CostConfigPage from '@/pages/settings/CostConfigPage';
import TonerReplacementsPage from '@/pages/settings/TonerReplacementsPage';
import ReportsPage from '@/pages/reports/ReportsPage';
import TonerYieldPage from '@/pages/reports/TonerYieldPage';
import AdminPage from '@/pages/admin/AdminPage';
import AdminUsersPage from '@/pages/admin/AdminUsersPage';

const Placeholder = ({ title }: { title: string }) => (
  <div className="p-2">
    <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
    <p className="mt-1 text-muted-foreground">Coming soon.</p>
  </div>
);

export default function App() {
  return (
    <PrinterProvider>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/printers" element={<PrintersPage />} />
        <Route path="/printers/new" element={<AddPrinterPage />} />
        <Route path="/printers/:id" element={<PrinterDetailPage />} />
        <Route path="/printers/:id/mapping" element={<ColumnMappingPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/toner-yield" element={<TonerYieldPage />} />
        <Route path="/settings/costs" element={<CostConfigPage />} />
        <Route path="/settings/toner-replacements" element={<TonerReplacementsPage />} />
        <Route path="/settings/notifications" element={<Placeholder title="Notifications" />} />
        <Route path="/settings/webhooks" element={<Placeholder title="Webhooks" />} />
        <Route path="/profile" element={<Placeholder title="Profile" />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </PrinterProvider>
  );
}
