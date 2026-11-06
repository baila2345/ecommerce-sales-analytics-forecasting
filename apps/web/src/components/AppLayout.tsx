import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";

const roleLabels = {
  admin: "Quản trị viên",
  analyst: "Chuyên viên phân tích",
  manager: "Người quản lý",
};

export function AppLayout() {
  const { user, logout } = useAuth();
  const canImport = user?.role === "admin" || user?.role === "analyst";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand brand--sidebar">
          <span className="brand__mark" aria-hidden="true">S</span>
          <span>
            <strong>Salescope</strong>
            <small>Analytics & Forecast</small>
          </span>
        </div>
        <nav className="sidebar__nav" aria-label="Điều hướng chính">
          <p className="sidebar__section-label">Quản trị</p>
          <NavLink className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`} to="/" end><span aria-hidden="true">▦</span>Tổng quan</NavLink>
          {canImport ? (
            <NavLink className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`} to="/imports"><span aria-hidden="true">⇧</span>Nhập dữ liệu<small className="nav-done">Sẵn sàng</small></NavLink>
          ) : (
            <span className="nav-item nav-item--disabled"><span aria-hidden="true">⇧</span>Nhập dữ liệu</span>
          )}
          <p className="sidebar__section-label sidebar__section-label--spaced">Phân tích</p>
          <span className="nav-item nav-item--disabled"><span aria-hidden="true">▥</span>Dashboard<small>Tiếp theo</small></span>
          <span className="nav-item nav-item--disabled"><span aria-hidden="true">⌁</span>Dự báo</span>
        </nav>
        <div className="sidebar__footer">
          <div className="user-mini">
            <span className="avatar" aria-hidden="true">{user?.email.charAt(0).toUpperCase()}</span>
            <span className="user-mini__copy">
              <strong>{user?.email}</strong>
              <small>{user ? roleLabels[user.role] : ""}</small>
            </span>
          </div>
          <button className="button button--ghost button--full" type="button" onClick={logout}>Đăng xuất</button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div><p className="topbar__eyebrow">Không gian làm việc</p><strong>E-commerce Sales Analytics</strong></div>
          <span className="environment-badge"><span aria-hidden="true" /> All services online</span>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
