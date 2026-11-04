import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../components/AppLayout";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { useAuth } from "../features/auth/AuthProvider";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";

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
