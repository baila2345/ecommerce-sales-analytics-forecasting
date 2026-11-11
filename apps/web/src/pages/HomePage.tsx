import { Link } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";


const roleLabels = {
  admin: "Quản trị viên",
  analyst: "Chuyên viên phân tích",
  manager: "Người quản lý",
};

const datasets = [
  "Danh mục",
  "Khách hàng",
  "Người bán",
  "Sản phẩm",
  "Đơn hàng",
  "Chi tiết đơn",
  "Thanh toán",
  "Đánh giá",
  "Địa lý",
];

export function HomePage() {
  const { user } = useAuth();
  const canImport = user?.role === "admin" || user?.role === "analyst";

  return (
    <main className="admin-home">
      <section className="admin-hero">
        <div className="admin-hero__copy">
          <span className="operational-badge">
            <span aria-hidden="true" /> Hệ thống vận hành ổn định
          </span>
          <p className="section-label">Trung tâm quản trị</p>
          <h1>Xin chào, {user?.email.split("@")[0]}</h1>
          <p>
            Nền tảng xác thực, phân quyền và nhập dữ liệu Olist đã sẵn sàng.
            Bạn có thể kiểm tra dữ liệu trước khi chuyển sang xây dựng analytics.
          </p>
          {canImport && (
            <div className="admin-hero__actions">
              <Link className="button button--primary hero-action" to="/imports">
                Nhập dữ liệu CSV <span aria-hidden="true">→</span>
              </Link>
              <span>Preview và validation trước khi ghi database</span>
            </div>
          )}
        </div>
        <aside className="admin-profile-card">
          <div className="admin-profile-card__top">
            <span className="avatar avatar--large" aria-hidden="true">
              {user?.email.charAt(0).toUpperCase()}
            </span>
            <span className="status-dot" title="Đang hoạt động" />
          </div>
          <span className="admin-profile-card__label">Phiên làm việc</span>
          <strong>{user?.email}</strong>
          <small>{user ? roleLabels[user.role] : ""}</small>
          <div className="admin-profile-card__permission">
            <span>Quyền truy cập</span>
            <b>{canImport ? "Quản lý dữ liệu" : "Chỉ xem báo cáo"}</b>
          </div>
        </aside>
      </section>

      <section className="admin-section">
        <div className="section-heading-row">
          <div>
            <p className="section-label">Tình trạng nền tảng</p>
            <h2>Các module cốt lõi</h2>
          </div>
          <span className="section-meta">Cập nhật theo phiên bản hiện tại</span>
        </div>
        <div className="status-card-grid">
          <article className="status-card">
            <div className="status-card__head">
              <span className="status-card__icon status-card__icon--green">✓</span>
              <span className="module-state module-state--done">Hoàn tất</span>
            </div>
            <span>Authentication</span>
            <strong>JWT & RBAC</strong>
            <p>Đăng nhập bảo mật và ba vai trò truy cập.</p>
          </article>
          <article className="status-card">
            <div className="status-card__head">
              <span className="status-card__icon status-card__icon--blue">⇧</span>
              <span className="module-state module-state--done">Hoàn tất</span>
            </div>
            <span>Data Import</span>
            <strong>9 loại dữ liệu</strong>
            <p>Preview, validation, checksum và batch upsert.</p>
          </article>
          <article className="status-card">
            <div className="status-card__head">
              <span className="status-card__icon status-card__icon--violet">DB</span>
              <span className="module-state module-state--done">Sẵn sàng</span>
            </div>
            <span>Data Foundation</span>
            <strong>MySQL schema</strong>
            <p>Khóa ngoại, index và audit history đầy đủ.</p>
          </article>
          <article className="status-card">
            <div className="status-card__head">
              <span className="status-card__icon status-card__icon--amber">↗</span>
              <span className="module-state module-state--done">Hoàn tất</span>
            </div>
            <span>Analytics</span>
            <strong>Dashboard KPI</strong>
            <p>KPI, xu hướng, sản phẩm, seller và giao hàng.</p>
          </article>
        </div>
      </section>

      <section className="admin-dashboard-grid">
        <article className="roadmap-panel">
          <div className="section-heading-row">
            <div>
              <p className="section-label">Lộ trình sản phẩm</p>
              <h2>Tiến độ triển khai</h2>
            </div>
            <strong className="progress-value">3/4 phase</strong>
          </div>
          <div className="progress-track"><span /></div>
          <ol className="phase-list">
            <li className="phase phase--done">
              <span>01</span><div><strong>Nền tảng & Authentication</strong><small>Đã hoàn thành</small></div><b>✓</b>
            </li>
            <li className="phase phase--done">
              <span>02</span><div><strong>Data Import Pipeline</strong><small>Đã hoàn thành</small></div><b>✓</b>
            </li>
            <li className="phase phase--done">
              <span>03</span><div><strong>Analytics Dashboard</strong><small>Đã hoàn thành</small></div><b>✓</b>
            </li>
            <li className="phase phase--active">
              <span>04</span><div><strong>Revenue Forecasting</strong><small>Giai đoạn tiếp theo</small></div><b>→</b>
            </li>
          </ol>
        </article>

        <article className="dataset-panel">
          <div className="dataset-panel__head">
            <div>
              <p className="section-label">Olist data model</p>
              <h2>Dataset được hỗ trợ</h2>
            </div>
            <span>9/9</span>
          </div>
          <p>Import theo thứ tự phụ thuộc để bảo đảm toàn vẹn khóa ngoại.</p>
          <div className="dataset-chip-grid">
            {datasets.map((dataset, index) => (
              <span key={dataset}><b>{String(index + 1).padStart(2, "0")}</b>{dataset}<i>✓</i></span>
            ))}
          </div>
          {canImport && <Link className="dataset-panel__link" to="/imports">Mở trung tâm nhập dữ liệu <span>→</span></Link>}
        </article>
      </section>
    </main>
  );
}
