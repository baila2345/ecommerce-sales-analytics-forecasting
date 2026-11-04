import { useAuth } from "../features/auth/AuthProvider";

const roleLabels = { admin: "Quản trị viên", analyst: "Chuyên viên phân tích", manager: "Người quản lý" };

export function HomePage() {
  const { user } = useAuth();
  return (
    <main className="home-page">
      <section className="welcome-row">
        <div><p className="section-label">Tổng quan</p><h1>Xin chào, {user?.email.split("@")[0]}</h1><p>Hệ thống đã sẵn sàng. Bước tiếp theo là nhập và kiểm tra dữ liệu bán hàng.</p></div>
        <div className="account-card"><span className="account-card__label">Quyền truy cập</span><strong>{user ? roleLabels[user.role] : ""}</strong><small>Tài khoản đang hoạt động</small></div>
      </section>
      <section className="metric-grid" aria-label="Trạng thái hệ thống">
        <article className="metric-card"><div className="metric-card__icon metric-card__icon--green">✓</div><span>API & Authentication</span><strong>Hoạt động</strong><small>JWT và phân quyền đã sẵn sàng</small></article>
        <article className="metric-card"><div className="metric-card__icon metric-card__icon--blue">DB</div><span>MySQL Database</span><strong>Đã kết nối</strong><small>Migration 0001 đang hoạt động</small></article>
        <article className="metric-card metric-card--next"><div className="metric-card__icon metric-card__icon--amber">⇧</div><span>Data Import</span><strong>Giai đoạn tiếp theo</strong><small>Upload, preview và kiểm tra CSV</small></article>
      </section>
      <section className="next-step-card">
        <div className="next-step-card__number">02</div>
        <div><p className="section-label">Lộ trình triển khai</p><h2>Xây dựng luồng nhập dữ liệu</h2><p>Tạo batch import cho năm tệp Olist cốt lõi, kiểm tra cấu trúc và xem trước dữ liệu trước khi ghi vào hệ thống.</p></div>
        <span className="next-step-card__status">Sắp triển khai</span>
      </section>
    </main>
  );
}
