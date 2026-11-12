import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../components/AppLayout";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { useAuth } from "../features/auth/AuthProvider";
import { AnalyticsPage } from "../pages/AnalyticsPage";
import { HomePage } from "../pages/HomePage";
import { ImportPage } from "../pages/ImportPage";
import { LoginPage } from "../pages/LoginPage";
import { ModelLabPage } from "../pages/ModelLabPage";

export function AppRoutes() {
  const { status } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={
          status === "authenticated" ? <Navigate to="/" replace /> : <LoginPage />
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="imports" element={<ImportPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="model-lab" element={<ModelLabPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
