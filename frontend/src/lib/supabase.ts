import { createClient } from '@supabase/supabase-js';
import type { Session, User } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

const isRealSupabaseConfigured =
  supabaseUrl &&
  supabaseUrl !== '' &&
  !supabaseUrl.includes('0ec90b57d6e95fcbda19832f') &&
  !supabaseUrl.includes('your-supabase-project-id');

// Initialize the real supabase client
const realSupabase = createClient(
  supabaseUrl || 'https://tmxlvvypzbrtwvpukvfx.supabase.co',
  supabaseAnonKey || 'sb_publishable_Cmpj3H-TzdYLRo0qCMZltQ_CQ3aHtQ8'
);

interface MockSignUpParams {
  email?: string;
  password?: string;
  options?: {
    data?: {
      full_name?: string;
      username?: string;
      country?: string;
      education?: string;
      stem_interest?: string;
    };
  };
}

interface MockSignInParams {
  email?: string;
  password?: string;
}

// Robust mock auth system to handle offline mode or when credentials are placeholders
class MockAuth {
  private listeners: ((event: string, session: Session | null) => void)[] = [];
  private currentSession: Session | null = null;

  constructor() {
    // Load active session from local storage on init
    try {
      const stored = localStorage.getItem('neurolab_session');
      if (stored) {
        this.currentSession = JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to parse stored mock session:', e);
    }
  }

  private triggerChange(event: string) {
    this.listeners.forEach((listener) => {
      try {
        listener(event, this.currentSession);
      } catch (e) {
        console.error('Error in auth state listener:', e);
      }
    });
  }

  async getSession() {
    return { data: { session: this.currentSession }, error: null };
  }

  onAuthStateChange(callback: (event: string, session: Session | null) => void) {
    this.listeners.push(callback);
    // Call instantly with current session
    callback('INITIAL_SESSION', this.currentSession);

    return {
      data: {
        subscription: {
          unsubscribe: () => {
            this.listeners = this.listeners.filter((l) => l !== callback);
          },
        },
      },
    };
  }

  async signUp({ email, password, options }: MockSignUpParams) {
    if (!email || !password) {
      return { data: { session: null, user: null }, error: new Error('Email and password are required') };
    }

    const users = this.getMockUsers();
    const normalizedEmail = email.toLowerCase().trim();

    if (users[normalizedEmail]) {
      return { data: { session: null, user: null }, error: new Error('User already exists') };
    }

    const mockUser = {
      id: 'user_' + Math.random().toString(36).substr(2, 9),
      email: normalizedEmail,
      created_at: new Date().toISOString(),
      user_metadata: {
        full_name: options?.data?.full_name || 'Student',
        username: options?.data?.username || '',
        country: options?.data?.country || '',
        education: options?.data?.education || '',
        stem_interest: options?.data?.stem_interest || '',
        student_level: 'Junior Scientist',
        stem_interests: [options?.data?.stem_interest || 'Physics'],
      },
    };

    users[normalizedEmail] = {
      password, // In mock, we store the password for demo simplicity
      user: mockUser as unknown as User,
    };
    this.saveMockUsers(users);

    const mockSession = {
      access_token: 'mock_jwt_token_' + Math.random().toString(36).substr(2),
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'mock_refresh_token_' + Math.random().toString(36).substr(2),
      user: mockUser,
    };

    this.currentSession = mockSession as unknown as Session;
    localStorage.setItem('neurolab_session', JSON.stringify(mockSession));
    this.triggerChange('SIGNED_IN');

    return { data: { session: mockSession as unknown as Session, user: mockUser as unknown as User }, error: null };
  }

  async signInWithPassword({ email, password }: MockSignInParams) {
    if (!email || !password) {
      return { data: { session: null, user: null }, error: new Error('Email and password are required') };
    }

    const users = this.getMockUsers();
    const normalizedEmail = email.toLowerCase().trim();
    const existing = users[normalizedEmail];

    if (!existing || existing.password !== password) {
      return { data: { session: null, user: null }, error: new Error('Invalid login credentials') };
    }

    const mockSession = {
      access_token: 'mock_jwt_token_' + Math.random().toString(36).substr(2),
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'mock_refresh_token_' + Math.random().toString(36).substr(2),
      user: existing.user,
    };

    this.currentSession = mockSession as unknown as Session;
    localStorage.setItem('neurolab_session', JSON.stringify(mockSession));
    this.triggerChange('SIGNED_IN');

    return { data: { session: mockSession as unknown as Session, user: existing.user as unknown as User }, error: null };
  }

  async signInWithOAuth({ provider, options }: { provider: string; options?: { redirectTo?: string } }) {
    const mockUser = {
      id: 'oauth_user_' + Math.random().toString(36).substr(2, 9),
      email: `${provider}_student@neurolab.ai`,
      created_at: new Date().toISOString(),
      user_metadata: {
        full_name: `${provider.charAt(0).toUpperCase() + provider.slice(1)} Student`,
      },
    };

    const mockSession = {
      access_token: 'mock_oauth_token_' + Math.random().toString(36).substr(2),
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'mock_oauth_refresh_' + Math.random().toString(36).substr(2),
      user: mockUser,
    };

    this.currentSession = mockSession as unknown as Session;
    localStorage.setItem('neurolab_session', JSON.stringify(mockSession));
    this.triggerChange('SIGNED_IN');

    // Simulate OAuth redirect or direct login
    setTimeout(() => {
      if (options?.redirectTo) {
        window.location.href = options.redirectTo;
      }
    }, 100);

    return { data: { session: mockSession as unknown as Session, user: mockUser as unknown as User }, error: null };
  }

  async signOut() {
    this.currentSession = null;
    localStorage.removeItem('neurolab_session');
    this.triggerChange('SIGNED_OUT');
    return { error: null };
  }

  async updateUser(attributes: { password?: string; data?: Record<string, unknown> }) {
    if (!this.currentSession?.user) {
      return { data: { user: null }, error: new Error('No active session') };
    }

    const user = this.currentSession.user;
    
    // Update metadata if provided
    if (attributes.data) {
      user.user_metadata = {
        ...(user.user_metadata || {}),
        ...attributes.data
      };
    }

    const email = user.email?.toLowerCase().trim();
    if (email) {
      const users = this.getMockUsers();
      if (users[email]) {
        if (attributes.password) {
          users[email].password = attributes.password;
        }
        users[email].user = user;
        this.saveMockUsers(users);
      }
    }

    this.currentSession.user = user;
    localStorage.setItem('neurolab_session', JSON.stringify(this.currentSession));
    this.triggerChange('USER_UPDATED');

    return { data: { user }, error: null };
  }

  async resetPasswordForEmail(email: string) {
    if (!email) {
      return { data: null, error: new Error('Email is required') };
    }
    const normalizedEmail = email.toLowerCase().trim();
    const users = this.getMockUsers();
    
    if (!users[normalizedEmail]) {
      return { data: null, error: new Error('User does not exist') };
    }

    return { data: {}, error: null };
  }

  private getMockUsers(): Record<string, { password: string; user: User }> {
    try {
      const data = localStorage.getItem('neurolab_mock_users');
      return data ? JSON.parse(data) : {};
    } catch {
      return {};
    }
  }

  private saveMockUsers(users: Record<string, { password: string; user: User }>) {
    try {
      localStorage.setItem('neurolab_mock_users', JSON.stringify(users));
    } catch (e) {
      console.error('Failed to save mock users:', e);
    }
  }
}

const mockAuthInstance = new MockAuth();

// Proxy for supabase that catches errors and switches to mock authentication
export const supabase = new Proxy(realSupabase, {
  get(target, prop, receiver) {
    if (prop === 'auth') {
      // If real Supabase is not properly configured, instantly fall back to mock auth
      if (!isRealSupabaseConfigured) {
        return mockAuthInstance;
      }

      // If configured, wrap the methods to gracefully fall back on network/unreachable exceptions
      const realAuth = target.auth;
      return new Proxy(realAuth, {
        get(authTarget, authProp, authReceiver) {
          const original = (authTarget as unknown as Record<string | symbol, unknown>)[authProp];
          if (typeof original !== 'function') {
            return Reflect.get(authTarget, authProp, authReceiver);
          }

          // onAuthStateChange is synchronous and shouldn't be wrapped in an async function
          if (authProp === 'onAuthStateChange') {
            return original.bind(authTarget);
          }

          return async function (...args: unknown[]) {
            try {
              const result = (await (original as (...a: unknown[]) => unknown).apply(authTarget, args)) as { error?: { message?: string; status?: number } } | null;
              if (result?.error && (
                result.error.message?.includes('Failed to fetch') ||
                result.error.message?.includes('NetworkError') ||
                result.error.status === 0
              )) {
                console.warn('[Supabase] Real auth failed, falling back to mock authentication:', result.error);
                const mockFn = (mockAuthInstance as unknown as Record<string | symbol, (...a: unknown[]) => unknown>)[authProp];
                return await mockFn.apply(mockAuthInstance, args);
              }
              return result;
            } catch (err: unknown) {
              const errorObj = err as { message?: string; status?: number };
              if (
                errorObj?.message?.includes('Failed to fetch') ||
                errorObj?.message?.includes('NetworkError') ||
                errorObj?.status === 0
              ) {
                console.warn('[Supabase] Network exception caught. Switching to mock authentication offline mode:', err);
                const mockFn = (mockAuthInstance as unknown as Record<string | symbol, (...a: unknown[]) => unknown>)[authProp];
                return await mockFn.apply(mockAuthInstance, args);
              }
              throw err;
            }
          };
        }
      });
    }

    return Reflect.get(target, prop, receiver);
  }
}) as typeof realSupabase;
