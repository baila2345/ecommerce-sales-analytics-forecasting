export type UserRole = "admin" | "analyst" | "manager";

export type AuthUser = {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

export type LoginCredentials = {
  email: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};
