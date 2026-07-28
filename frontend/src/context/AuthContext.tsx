import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export interface User {
  email: string;
  name: string;
  message?: string;
  isGuest?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
  loginAsGuest: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    const performCheck = async () => {
      try {
        const response = await fetch('/auth/me', { credentials: 'include' });
        if (!isMounted) return;
        
        if (response.ok) {
          const data = await response.json();
          if (data.authenticated) {
            setUser({
              email: data.email,
              name: data.name,
              message: data.message,
              isGuest: data.is_guest,
            });
          } else {
            setUser(null);
          }
        } else {
          setUser(null);
        }
      } catch (error) {
        console.error('Authentication check failed:', error);
        if (isMounted) setUser(null);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    performCheck();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = () => {
    window.location.href = '/auth/login';
  };

  const logout = () => {
    window.location.href = '/auth/logout';
  };

  const loginAsGuest = async () => {
    try {
      setLoading(true);
      const response = await fetch('/auth/guest', { method: 'POST' });
      if (response.ok) {
        const data = await response.json();
        if (data.authenticated) {
          setUser({
            email: data.email,
            name: data.name,
            isGuest: data.is_guest,
          });
        }
      }
    } catch (error) {
      console.error('Guest login failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        loginAsGuest,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
