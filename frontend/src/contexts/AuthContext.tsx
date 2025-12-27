'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  AuthData,
  DiscordUser,
  loadAuthData,
  saveAuthData,
  clearAuthData,
  isAuthenticated as checkIsAuthenticated,
  exchangeCodeForToken,
  getDiscordAuthURL,
  refreshAccessToken,
} from '@/lib/auth';
import api from '@/lib/api';

interface AuthContextType {
  user: DiscordUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (authData: AuthData) => void;
  logout: () => Promise<void>;
  loginWithDiscord: () => Promise<void>;
  handleDiscordCallback: (code: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<DiscordUser | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const authData = loadAuthData();
    if (authData) {
      setUser(authData.user);
      setIsAuthenticated(true);
      api.setAuth(authData.accessToken, authData.user.id);

      const timeUntilExpiry = authData.expiresAt - Date.now();
      if (timeUntilExpiry < 5 * 60 * 1000 && timeUntilExpiry > 0) {
        refreshAccessToken(authData.refreshToken)
          .then((newAuthData) => {
            login(newAuthData);
          })
          .catch((error) => {
            console.error('Token refresh failed:', error);
            logout();
          });
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;

    const checkAndRefreshToken = async () => {
      const authData = loadAuthData();
      if (!authData) {
        logout();
        return;
      }

      const timeUntilExpiry = authData.expiresAt - Date.now();

      if (timeUntilExpiry < 5 * 60 * 1000) {
        try {
          const newAuthData = await refreshAccessToken(authData.refreshToken);
          login(newAuthData);
        } catch (error) {
          console.error('Token refresh failed:', error);
          logout();
        }
      }
    };

    // Check every minute
    const interval = setInterval(checkAndRefreshToken, 60 * 1000);

    return () => clearInterval(interval);
  }, [isAuthenticated]);

  const login = (authData: AuthData) => {
    saveAuthData(authData);
    setUser(authData.user);
    setIsAuthenticated(true);
    api.setAuth(authData.accessToken, authData.user.id);
  };

  const logout = async () => {
    const authData = loadAuthData();

    if (authData?.refreshToken) {
      try {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ refresh_token: authData.refreshToken }),
        });
      } catch (error) {
        console.error('Logout error:', error);
      }
    }

    clearAuthData();
    setUser(null);
    setIsAuthenticated(false);
    api.clearAuth();
    router.push('/');
  };

  const loginWithDiscord = async () => {
    try {
      const authURL = await getDiscordAuthURL();
      window.location.href = authURL;
    } catch (error) {
      console.error('Failed to initiate Discord login:', error);
      throw error;
    }
  };

  const handleDiscordCallback = async (code: string) => {
    try {
      const authData = await exchangeCodeForToken(code);
      login(authData);
    } catch (error) {
      console.error('Discord callback error:', error);
      throw error;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login,
        logout,
        loginWithDiscord,
        handleDiscordCallback,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
