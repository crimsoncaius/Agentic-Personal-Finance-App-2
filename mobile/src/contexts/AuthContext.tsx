import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import * as SecureStore from "expo-secure-store";
import { MobileStorage } from "../../../shared/src/services/storage";
import { ApiService } from "../../../shared/src/services/api";
import type {
  User,
  Session,
  AuthContextType,
} from "../../../shared/src/types/auth";
import { API_BASE_URL } from "../config/api";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Create API service with mobile storage
  const storage = new MobileStorage(SecureStore);
  const apiService = new ApiService({
    baseUrl: API_BASE_URL,
    storage,
  });

  // Load session from secure store on mount
  useEffect(() => {
    const loadSession = async () => {
      try {
        const storedSession = await storage.getItem("session");
        const storedUser = await storage.getItem("user");

        if (storedSession && storedUser) {
          const parsedSession: Session = JSON.parse(storedSession);
          const parsedUser: User = JSON.parse(storedUser);

          // Check if token is expired
          const now = Math.floor(Date.now() / 1000);
          if (parsedSession.expires_at > now) {
            setSession(parsedSession);
            setUser(parsedUser);
          } else {
            // Token expired, try to refresh
            await refreshSession(parsedSession.refresh_token);
          }
        }
      } catch (error) {
        console.error("Error loading session:", error);
        await storage.removeItem("session");
        await storage.removeItem("user");
      } finally {
        setIsLoading(false);
      }
    };

    loadSession();
  }, []);

  const refreshSession = async (refreshToken: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (response.ok) {
        const newSession: Session = await response.json();
        setSession(newSession);
        await storage.setItem("session", JSON.stringify(newSession));
      } else {
        // Refresh failed, clear session
        await logout();
      }
    } catch (error) {
      console.error("Error refreshing session:", error);
      await logout();
    }
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();
    setUser(data.user);
    setSession(data.session);

    // Store in secure store
    await storage.setItem("user", JSON.stringify(data.user));
    await storage.setItem("session", JSON.stringify(data.session));
  };

  const register = async (email: string, password: string, name?: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Registration failed");
    }

    const data = await response.json();
    setUser(data.user);
    setSession(data.session);

    // Store in secure store
    await storage.setItem("user", JSON.stringify(data.user));
    await storage.setItem("session", JSON.stringify(data.session));
  };

  const logout = async () => {
    // Call logout endpoint if we have a token
    if (session?.access_token) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        });
      } catch (error) {
        console.error("Error calling logout endpoint:", error);
      }
    }

    setUser(null);
    setSession(null);
    await storage.removeItem("user");
    await storage.removeItem("session");
  };

  const getAccessToken = (): string | null => {
    if (!session) return null;

    // Check if token is expired
    const now = Math.floor(Date.now() / 1000);
    if (session.expires_at <= now) {
      // Token expired, try to refresh
      refreshSession(session.refresh_token);
      return null;
    }

    return session.access_token;
  };

  const value: AuthContextType = {
    user,
    session,
    isLoading,
    isAuthenticated: !!user && !!session,
    login,
    register,
    logout,
    getAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
