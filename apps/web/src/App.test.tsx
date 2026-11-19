import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";


const userProfile = {
  id: 1,
  email: "admin@example.com",
  role: "admin",
  is_active: true,
  created_at: "2026-11-04T00:00:00",
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("authentication flow", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("redirects anonymous users to login", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Chào mừng bạn quay lại" })).toBeInTheDocument();
  });

  it("logs in, loads the profile, and stores only the token", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: "test-token", token_type: "bearer", expires_in: 3600 }))
      .mockResolvedValueOnce(jsonResponse(userProfile));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);
    await user.type(await screen.findByLabelText("Email"), "admin@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "valid-test-password");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByRole("heading", { name: "Xin chào, admin" })).toBeInTheDocument();
    expect(screen.getByText("Data Import")).toBeInTheDocument();
    expect(screen.getByText("9 loại dữ liệu")).toBeInTheDocument();
    expect(screen.getByText("Analytics Dashboard")).toBeInTheDocument();
    expect(sessionStorage.getItem("sales_analytics_access_token")).toBe("test-token");
    expect(JSON.stringify(sessionStorage)).not.toContain("valid-test-password");
  });

  it("shows the backend message when credentials are invalid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
      error: { code: "INVALID_CREDENTIALS", message: "Email or password is incorrect" },
      request_id: "request-1",
    }, 401)));
    const user = userEvent.setup();

    render(<App />);
    await user.type(await screen.findByLabelText("Email"), "admin@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect");
    expect(sessionStorage.getItem("sales_analytics_access_token")).toBeNull();
  });

  it("restores a session and clears it on logout", async () => {
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(userProfile)));
    const user = userEvent.setup();

    render(<App />);
    expect(await screen.findByRole("heading", { name: "Xin chào, admin" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Đăng xuất" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Chào mừng bạn quay lại" })).toBeInTheDocument();
    });
    expect(sessionStorage.getItem("sales_analytics_access_token")).toBeNull();
  });
});

describe("product category import flow", () => {
  it("previews the selected CSV before confirming the import", async () => {
    window.history.replaceState({}, "", "/imports");
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(userProfile))
      .mockResolvedValueOnce(jsonResponse([
        {
          dataset_type: "product_categories",
          route_slug: "product-categories",
          display_name: "Danh mục sản phẩm",
          expected_filename: "product_category_name_translation.csv",
          columns: ["product_category_name", "product_category_name_english"],
          max_file_size_mb: 5,
        },
      ]))
      .mockResolvedValueOnce(jsonResponse({
        batch_id: 12,
        dataset_type: "product_categories",
        filename: "product_category_name_translation.csv",
        columns: ["product_category_name", "product_category_name_english"],
        total_rows: 2,
        valid_rows: 2,
        rejected_rows: 0,
        preview_rows: [
          {
            product_category_name: "beleza_saude",
            product_category_name_english: "health_beauty",
          },
          {
            product_category_name: "informatica_acessorios",
            product_category_name_english: "computers_accessories",
          },
        ],
        errors: [],
        can_import: true,
      }))
      .mockResolvedValueOnce(jsonResponse({
        batch_id: 12,
        dataset_type: "product_categories",
        status: "completed",
        imported_rows: 2,
      }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const file = new File(
      [
        "product_category_name,product_category_name_english\n" +
        "beleza_saude,health_beauty\n",
      ],
      "product_category_name_translation.csv",
      { type: "text/csv" },
    );

    render(<App />);
    await user.upload(await screen.findByLabelText(/Chọn file CSV/), file);
    await user.click(screen.getByRole("button", { name: "Kiểm tra & xem trước" }));

    expect(await screen.findByText("health_beauty")).toBeInTheDocument();
    expect(screen.getByText("Có thể import")).toBeInTheDocument();
    expect(screen.queryByText("Import thành công")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Xác nhận import" }));

    expect(await screen.findByText("Import thành công")).toBeInTheDocument();
    expect(screen.getByText(/Đã ghi 2 dòng/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    const previewOptions = fetchMock.mock.calls[2][1] as RequestInit;
    expect(previewOptions.body).toBeInstanceOf(FormData);
    expect((previewOptions.headers as Headers).has("Content-Type")).toBe(false);
  });
});

describe("analytics dashboard", () => {
  it("loads KPI, charts, and business analysis from the analytics API", async () => {
    window.history.replaceState({}, "", "/analytics");
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me")) return Promise.resolve(jsonResponse(userProfile));
      if (url.includes("/analytics/filters")) {
        return Promise.resolve(jsonResponse({
          min_date: "2018-01-01",
          max_date: "2018-12-31",
          states: ["SP"],
          categories: ["beleza_saude"],
          sellers: [{ id: "seller-1", label: "campinas, SP · seller-1" }],
        }));
      }
      return Promise.resolve(jsonResponse({
        filters: {},
        overview: {
          revenue: 1500,
          orders: 12,
          customers: 10,
          average_order_value: 125,
          items_sold: 15,
          freight_value: 120,
          delivered_rate: 92.3,
          average_delivery_days: 5,
        },
        revenue_trend: [{ period: "2018-01", revenue: 1500, orders: 12 }],
        order_statuses: [{ label: "delivered", value: 12, orders: 12 }],
        top_categories: [{ label: "health_beauty", value: 1500, orders: 12 }],
        top_products: [{ product_id: "product-123456", category: "health_beauty", revenue: 900, units: 8, orders: 7 }],
        top_sellers: [{ seller_id: "seller-123456", location: "campinas, SP", revenue: 1500, orders: 12 }],
        regions: [{ state: "SP", revenue: 1500, orders: 12, customers: 10 }],
        delivery: [{ state: "SP", average_days: 5, on_time_rate: 95, delivered_orders: 12 }],
      }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<StrictMode><App /></StrictMode>);

    expect(await screen.findByRole("heading", { name: "Analytics Dashboard" })).toBeInTheDocument();
    expect((await screen.findAllByText("health_beauty")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("5 ngày").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Export CSV/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls.filter(
      ([url]) => String(url).includes("/analytics/dashboard"),
    )).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(
      ([url]) => String(url).includes("/analytics/filters"),
    )).toHaveLength(1);
  });
});

describe("M0 Model Lab", () => {
  const snapshot = {
      id: 2,
      fingerprint: "a".repeat(64),
      status: "ready",
      source_checksums: {},
      rules_version: "daily-sales-v2",
      quality_policy_version: "olist-ml-quality-v1",
      source_timezone: "source-local-brazil",
      maturity_days: 30,
      source_min_date: "2016-09-04",
      source_max_date: "2018-10-17",
      mature_until: "2018-08-29",
      daily_sales_days: 725,
      mature_days: 725,
      sales_value: 1000000,
      orders_count: 90000,
      customer_days: 90000,
      items_count: 100000,
      created_at: "2026-11-12T00:00:00",
      completed_at: "2026-11-12T00:01:00",
  };
  const makeRun = (
    id: number,
    status = "succeeded",
    overrides: Record<string, unknown> = {},
  ) => ({
      id,
      model_code: "M0",
      status,
      dataset_fingerprint: snapshot.fingerprint,
      snapshot_id: snapshot.id,
      horizon_days: 30,
      holdout_days: 90,
      min_train_days: 365,
      step_days: 30,
      experiment_key: "c".repeat(64),
      model_version: "seasonal-naive-v2-asof",
      feature_schema_hash: null,
      holdout_from: "2018-06-01",
      holdout_to: "2018-08-29",
      holdout_evaluated: false,
      fold_count: 1,
      metrics: status === "succeeded" ? {
        mae_mean: 9497.66,
        mae_std: 0,
        rmse_mean: 12441.22,
        rmse_std: 0,
        wape_mean: 34.75,
        wape_std: 0,
      } : null,
      component_metrics: null,
      folds: status === "succeeded" ? [{
        fold_no: 1,
        origin_date: "2018-05-01",
        train_from: "2016-09-04",
        train_to: "2018-04-30",
        test_from: "2018-05-01",
        test_to: "2018-05-30",
        metrics: {
          mae: 9497.66,
          rmse: 12441.22,
          wape: 34.75,
          actual_sum: 100000,
          prediction_sum: 95000,
        },
        predictions: [
          { date: "2018-05-01", actual: 3000, predicted: 2800 },
          { date: "2018-05-02", actual: 3500, predicted: 3200 },
        ],
      }] : [],
      job_id: `job-${id}`,
      error: status === "failed" ? {
        code: "BACKTEST_FOLD_FAILED",
        message: "optimizer failed",
        stage: "fold",
        fold_no: 2,
      } : null,
      created_at: "2026-11-12T00:00:00",
      started_at: status === "queued" ? null : "2026-11-12T00:00:01",
      completed_at: ["succeeded", "failed"].includes(status) ? "2026-11-12T00:00:02" : null,
      ...overrides,
    });

  it("loads the latest run and polls a queued backtest", async () => {
    window.history.replaceState({}, "", "/model-lab");
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/auth/me")) return Promise.resolve(jsonResponse(userProfile));
      if (url.includes("/datasets/snapshots/latest")) return Promise.resolve(jsonResponse(snapshot));
      if (url.includes("/models/runs/latest?model_code=M0")) return Promise.resolve(jsonResponse(makeRun(1)));
      if (url.includes("/models/runs/latest?model_code=M1")) return Promise.resolve(jsonResponse({
        error: { code: "MODEL_RUN_NOT_FOUND", message: "Model run was not found" },
      }, 404));
      if (url.includes("/models/runs/2")) return Promise.resolve(jsonResponse(makeRun(2)));
      if (url.includes("/models/backtests") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(makeRun(2, "queued"), 202));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Model Lab" })).toBeInTheDocument();
    expect(await screen.findByText("Kết quả M0 · Run #1")).toBeInTheDocument();
    expect(screen.getAllByText("34,75%").length).toBeGreaterThan(0);
    expect(screen.getByText("Holdout đang được khóa")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "M2.1 · LightGBM scaled" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "M3 · Orders × AOV" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "M4 · Weighted ensemble" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Chạy backtest M0" }));

    expect(await screen.findByText("M0 đang chờ worker")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Kết quả M0 · Run #2")).toBeInTheDocument();
    }, { timeout: 2500 });
    const postCall = fetchMock.mock.calls.find(
      ([url, options]) => String(url).includes("/models/backtests") && options?.method === "POST",
    );
    expect(postCall).toBeDefined();
    expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
      model_code: "M0",
      dataset_fingerprint: snapshot.fingerprint,
      horizon_days: 30,
      holdout_days: 90,
      season_length: 7,
      sarima_order: [1, 1, 1],
      sarima_seasonal_order: [1, 0, 1, 7],
    });
    expect(fetchMock.mock.calls.some(
      ([url]) => String(url).includes("dataset_fingerprint=")
        && String(url).includes("holdout_days=90")
        && String(url).includes("min_train_days=365"),
    )).toBe(true);
    expect(fetchMock.mock.calls.some(
      ([url]) => String(url).includes("model_code=M2")
        && String(url).includes("m2_n_estimators=200")
        && String(url).includes("m2_seed=42"),
    )).toBe(true);
    expect(fetchMock.mock.calls.some(
      ([url]) => String(url).includes("model_code=M3")
        && String(url).includes("m3_n_estimators=200")
        && String(url).includes("m3_seed=42"),
    )).toBe(true);
    expect(fetchMock.mock.calls.some(
      ([url]) => String(url).includes("model_code=M4")
        && String(url).includes("m2_n_estimators=200")
        && String(url).includes("m3_n_estimators=200")
        && String(url).includes("m4_alpha_grid=0.5"),
    )).toBe(true);
  });

  it("renders the persisted fold error from a failed worker run", async () => {
    window.history.replaceState({}, "", "/model-lab");
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me")) return Promise.resolve(jsonResponse(userProfile));
      if (url.includes("/datasets/snapshots/latest")) return Promise.resolve(jsonResponse(snapshot));
      if (url.includes("model_code=M0")) return Promise.resolve(jsonResponse(makeRun(3, "failed")));
      return Promise.resolve(jsonResponse({ error: { code: "MODEL_RUN_NOT_FOUND", message: "not found" } }, 404));
    }));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("M0 chạy thất bại tại fold #2");
    expect(screen.getByRole("alert")).toHaveTextContent("optimizer failed");
  });

  it("shows the selected M4 alpha and both branch predictions", async () => {
    window.history.replaceState({}, "", "/model-lab");
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    const m4Run = makeRun(19, "succeeded", {
      model_code: "M4",
      model_version: "weighted-ensemble-v1-validation-grid",
      selected_alpha: 0,
      alpha_grid: [0, 0.5, 1],
      folds: [{
        ...makeRun(19).folds[0],
        predictions: [
          { date: "2018-05-01", actual: 3000, predicted: 2900, predicted_m2: 2700, predicted_m3: 2900, ensemble_alpha: 0 },
          { date: "2018-05-02", actual: 3500, predicted: 3300, predicted_m2: 3100, predicted_m3: 3300, ensemble_alpha: 0 },
        ],
      }],
    });
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me")) return Promise.resolve(jsonResponse(userProfile));
      if (url.includes("/datasets/snapshots/latest")) return Promise.resolve(jsonResponse(snapshot));
      if (url.includes("model_code=M4")) return Promise.resolve(jsonResponse(m4Run));
      return Promise.resolve(jsonResponse({ error: { code: "MODEL_RUN_NOT_FOUND", message: "not found" } }, 404));
    }));
    const user = userEvent.setup();

    render(<App />);

    await user.selectOptions(await screen.findByRole("combobox", { name: "Model" }), "M4");
    expect(await screen.findByText("Kết quả M4 · Run #19")).toBeInTheDocument();
    expect(screen.getByText(/α = 0 cho M2\.1 và 1 cho M3/)).toBeInTheDocument();
    expect(screen.getByText(/Composition M4/)).toBeInTheDocument();
  });

  it("refuses to rank runs with different experiment signatures", async () => {
    window.history.replaceState({}, "", "/model-lab");
    sessionStorage.setItem("sales_analytics_access_token", "existing-token");
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me")) return Promise.resolve(jsonResponse(userProfile));
      if (url.includes("/datasets/snapshots/latest")) return Promise.resolve(jsonResponse(snapshot));
      if (url.includes("model_code=M0")) return Promise.resolve(jsonResponse(makeRun(4)));
      if (url.includes("model_code=M1")) return Promise.resolve(jsonResponse(makeRun(5, "succeeded", {
        model_code: "M1",
        horizon_days: 7,
      })));
      return Promise.resolve(jsonResponse({}, 404));
    }));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Không thể xếp hạng: các model không cùng cấu hình thí nghiệm.",
    );
  });
});
