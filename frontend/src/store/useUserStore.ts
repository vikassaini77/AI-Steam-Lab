import { create } from 'zustand';
import type { User } from '@supabase/supabase-js';

interface UserStatsUpdate {
  xp?: number;
  level?: number;
  dailyStreak?: number;
  completedLabs?: number;
  aiInteractions?: number;
}

interface UserState {
  user: User | null;
  fullName: string;
  xp: number;
  level: number;
  dailyStreak: number;
  completedLabs: number;
  aiInteractions: number;
  setUser: (user: User | null) => void;
  setXp: (xp: number) => void;
  addXp: (amount: number) => void;
  setLevel: (level: number) => void;
  setStats: (stats: UserStatsUpdate) => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  fullName: 'Student',
  xp: 0,
  level: 1,
  dailyStreak: 0,
  completedLabs: 0,
  aiInteractions: 0,
  setUser: (user) =>
    set({
      user,
      fullName: user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Student',
    }),
  setXp: (xp) => set({ xp }),
  addXp: (amount) => set((state) => ({ xp: state.xp + amount })),
  setLevel: (level) => set({ level }),
  setStats: (stats) => set((state) => ({ ...state, ...stats })),
}));
