import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
