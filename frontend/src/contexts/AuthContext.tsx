import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";

interface User {
  id: string;
  email: string;
  name?: string;
  created_at: string;
}

interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number;
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE_URL = import.meta.env.PROD
  ? "https://agentic-personal-finance-app-2-production.up.railway.app/api/v1"
  : "http://localhost:8000/api/v1";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load session from localStorage on mount
  useEffect(() => {
    const storedSession = localStorage.getItem("session");
    const storedUser = localStorage.getItem("user");

    if (storedSession && storedUser) {
      try {
        const parsedSession: Session = JSON.parse(storedSession);
        const parsedUser: User = JSON.parse(storedUser);

        // Check if token is expired
        const now = Math.floor(Date.now() / 1000);
        if (parsedSession.expires_at > now) {
          setSession(parsedSession);
          setUser(parsedUser);
        } else {
          // Token expired, try to refresh
          refreshSession(parsedSession.refresh_token);
        }
      } catch (error) {
        console.error("Error loading session:", error);
        localStorage.removeItem("session");
        localStorage.removeItem("user");
      }
    }

    setIsLoading(false);
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
        localStorage.setItem("session", JSON.stringify(newSession));
      } else {
        // Refresh failed, clear session
        logout();
      }
    } catch (error) {
      console.error("Error refreshing session:", error);
      logout();
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

    // Store in localStorage
    localStorage.setItem("user", JSON.stringify(data.user));
    localStorage.setItem("session", JSON.stringify(data.session));
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

    // Store in localStorage
    localStorage.setItem("user", JSON.stringify(data.user));
    localStorage.setItem("session", JSON.stringify(data.session));
  };

  const logout = () => {
    // Call logout endpoint if we have a token
    if (session?.access_token) {
      fetch(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
      }).catch(console.error);
    }

    setUser(null);
    setSession(null);
    localStorage.removeItem("user");
    localStorage.removeItem("session");
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
