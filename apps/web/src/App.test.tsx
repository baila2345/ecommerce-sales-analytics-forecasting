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
