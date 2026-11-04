import { apiRequest } from "../../api/client";
import type { AuthUser, LoginCredentials, TokenResponse } from "./types";

export function login(credentials: LoginCredentials): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function getCurrentUser(token: string): Promise<AuthUser> {
  return apiRequest<AuthUser>("/api/v1/auth/me", { token });
}
