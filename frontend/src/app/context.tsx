import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, clearPrivateStorage, setCSRF } from "../api/client";
import type { SessionInfo, User } from "../api/types";

type Auth = {
  user: User | null;
  loading: boolean;
  error: string;
  accept: (session: SessionInfo) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const client = useQueryClient();
  const accept = useCallback((session: SessionInfo) => {
    setCSRF(session.csrf_token);
    setUser(session.user);
    setError("");
  }, []);
  const refresh = useCallback(async () => {
    try {
      accept(await api<SessionInfo>("/auth/session"));
    } catch {
      setError("暂时无法连接服务，请确认后端和数据库已启动");
    } finally {
      setLoading(false);
    }
  }, [accept]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setCSRF("");
      clearPrivateStorage();
      client.clear();
      void refresh();
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [client, refresh]);
  const logout = async () => {
    await api("/auth/logout", "POST", {});
    clearPrivateStorage();
    client.clear();
    setUser(null);
    await refresh();
  };
  return (
    <AuthContext.Provider
      value={{ user, loading, error, accept, refresh, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("AuthProvider required");
  return auth;
}
