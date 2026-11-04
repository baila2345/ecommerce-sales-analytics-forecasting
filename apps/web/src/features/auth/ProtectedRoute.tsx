import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <main className="session-loading" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Đang kiểm tra phiên đăng nhập...</p>
      </main>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
