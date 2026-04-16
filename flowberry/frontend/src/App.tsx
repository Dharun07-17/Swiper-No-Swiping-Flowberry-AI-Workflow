import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import MfaPage from "./pages/MfaPage";
import WorkflowSubmissionPage from "./pages/WorkflowSubmissionPage";
import WorkflowDetailPage from "./pages/WorkflowDetailPage";
import WorkflowLogsPage from "./pages/WorkflowLogsPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import IntegrationsPage from "./pages/IntegrationsPage";
import SecurityPage from "./pages/SecurityPage";
import { ProtectedRoute } from "./ProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/mfa" element={<MfaPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/workflows" element={<WorkflowSubmissionPage />} />
          <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
          <Route path="/logs" element={<WorkflowLogsPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="/admin" element={<AdminDashboardPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/workflows" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
