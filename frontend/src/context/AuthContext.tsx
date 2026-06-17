import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export interface User {
  email: string;
  name: string;
  message?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
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

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
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
