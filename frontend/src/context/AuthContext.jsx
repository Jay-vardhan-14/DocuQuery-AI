/**
 * Authentication context provider.
 *
 * Manages JWT tokens, user profile state, and auth flow.
 * Provides login, register, logout, and auto-profile-fetch on mount.
 */

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { authApi, getTokens, setTokens, clearTokens } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch user profile if tokens exist
  const loadProfile = useCallback(async () => {
    const tokens = getTokens();
    if (!tokens?.access_token) {
      setLoading(false);
      return;
    }
    try {
      const profile = await authApi.getProfile();
      setUser(profile);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const login = useCallback(async (email, password) => {
    const tokens = await authApi.login(email, password);
    setTokens(tokens);
    const profile = await authApi.getProfile();
    setUser(profile);
    return profile;
  }, []);

  const register = useCallback(async (email, password, fullName) => {
    const tokens = await authApi.register(email, password, fullName);
    setTokens(tokens);
    const profile = await authApi.getProfile();
    setUser(profile);
    return profile;
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    isAdmin: user?.role === 'admin',
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
