import { create } from 'zustand';
import type { User } from '@supabase/supabase-js';

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
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  fullName: 'Student',
  xp: 2450,
  level: 12,
  dailyStreak: 5,
  completedLabs: 12,
  aiInteractions: 47,
  setUser: (user) => set({ user, fullName: user?.user_metadata?.full_name || 'Student' }),
  setXp: (xp) => set({ xp }),
  addXp: (amount) => set((state) => ({ xp: state.xp + amount })),
  setLevel: (level) => set({ level }),
}));
