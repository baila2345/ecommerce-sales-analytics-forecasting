import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthProvider";

type LocationState = { from?: { pathname?: string } };

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      const state = location.state as LocationState | null;
      navigate(state?.from?.pathname ?? "/", { replace: true });
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "Không thể kết nối đến hệ thống. Vui lòng kiểm tra API và thử lại.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-story" aria-label="Giới thiệu hệ thống">
        <div className="brand brand--light">
          <span className="brand__mark" aria-hidden="true">S</span>
          <span><strong>Salescope</strong><small>Analytics & Forecast</small></span>
        </div>
        <div className="auth-story__content">
          <p className="section-label section-label--light">Dữ liệu thành quyết định</p>
          <h1>Hiểu doanh thu hôm nay. Chuẩn bị cho ngày mai.</h1>
          <p>Một không gian thống nhất để kiểm tra dữ liệu bán hàng, theo dõi chỉ số và xây dựng dự báo có thể giải thích.</p>
          <ul className="feature-list">
            <li><span>01</span> Kiểm soát chất lượng dữ liệu trước khi phân tích</li>
            <li><span>02</span> Theo dõi doanh thu, đơn hàng và khách hàng</li>
            <li><span>03</span> Dự báo theo khoảng và giải thích biến động</li>
          </ul>
        </div>
        <p className="auth-story__foot">Olist dataset · Daily revenue forecasting</p>
      </section>

      <section className="auth-form-section">
        <div className="auth-form-wrap">
          <div className="auth-form-heading">
            <p className="section-label">Truy cập hệ thống</p>
            <h2>Chào mừng bạn quay lại</h2>
            <p>Đăng nhập bằng tài khoản đã được quản trị viên cấp.</p>
          </div>
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Email</span>
              <input name="email" type="email" autoComplete="username" placeholder="admin@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required disabled={submitting} />
            </label>
            <label className="field">
              <span>Mật khẩu</span>
              <span className="password-input">
                <input name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="Nhập mật khẩu" value={password} onChange={(event) => setPassword(event.target.value)} required disabled={submitting} />
                <button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"} disabled={submitting}>{showPassword ? "Ẩn" : "Hiện"}</button>
              </span>
            </label>
            {error ? <div className="form-error" role="alert">{error}</div> : null}
            <button className="button button--primary button--large" type="submit" disabled={submitting}>
              {submitting ? <><span className="spinner spinner--button" aria-hidden="true" /> Đang đăng nhập...</> : "Đăng nhập"}
            </button>
          </form>
          <div className="security-note"><span aria-hidden="true">◆</span>Phiên đăng nhập chỉ được lưu trong tab trình duyệt hiện tại.</div>
        </div>
      </section>
    </main>
  );
}
