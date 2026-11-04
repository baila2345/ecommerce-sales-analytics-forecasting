import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getCurrentUser, login as loginRequest } from "./api";
import { tokenStorage } from "./storage";
import type { AuthUser, LoginCredentials } from "./types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const logout = useCallback(() => {
    tokenStorage.clear();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    const token = tokenStorage.get();
    if (!token) {
      setStatus("unauthenticated");
      return;
    }

    let active = true;
    getCurrentUser(token)
      .then((currentUser) => {
        if (!active) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!active) return;
        tokenStorage.clear();
        setUser(null);
        setStatus("unauthenticated");
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const tokenResponse = await loginRequest(credentials);
    tokenStorage.set(tokenResponse.access_token);

    try {
      const currentUser = await getCurrentUser(tokenResponse.access_token);
      setUser(currentUser);
      setStatus("authenticated");
    } catch (error) {
      tokenStorage.clear();
      throw error;
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, login, logout }),
    [status, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
