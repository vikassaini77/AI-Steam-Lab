import { supabase } from './supabase';

/**
 * Returns the sanitized backend API base URL.
 * Automatically strips accidental "VITE_API_URL=" prefixes or trailing slashes,
 * and defaults to the live Render backend when deployed in production.
 */
export function getApiBaseUrl(): string {
  let url = (import.meta.env.VITE_API_URL || '').trim();
  if (url.startsWith('VITE_API_URL=')) {
    url = url.substring('VITE_API_URL='.length).trim();
  }
  url = url.replace(/\/+$/, '');

  if (url) return url;

  if (typeof window !== 'undefined') {
    const isLocal =
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1';
    if (isLocal) {
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
  }

  // Production fallback to live Render backend
  return 'https://neurolab-backend-uxhv.onrender.com';
}

/**
 * Returns a valid WebSocket URL for backend streaming connections (ws:// or wss://).
 */
export function getWebSocketUrl(path: string = ''): string {
  const base = getApiBaseUrl();
  const wsBase = base.replace(/^http:/i, 'ws:').replace(/^https:/i, 'wss:');
  const cleanPath = path ? (path.startsWith('/') ? path : `/${path}`) : '';
  return `${wsBase}${cleanPath}`;
}

/**
 * Helper to build standard API headers with Supabase Bearer token if session exists.
 */
export async function getAuthHeaders(customHeaders: Record<string, string> = {}): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...customHeaders,
  };
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      headers['Authorization'] = `Bearer ${session.access_token}`;
    }
  } catch (err) {
    console.warn('Could not retrieve Supabase session token:', err);
  }
  return headers;
}

