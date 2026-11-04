const accessTokenKey = "sales_analytics_access_token";

export const tokenStorage = {
  get(): string | null {
    return sessionStorage.getItem(accessTokenKey);
  },
  set(token: string): void {
    sessionStorage.setItem(accessTokenKey, token);
  },
  clear(): void {
    sessionStorage.removeItem(accessTokenKey);
  },
};
