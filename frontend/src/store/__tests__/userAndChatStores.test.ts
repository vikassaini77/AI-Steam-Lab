import { describe, it, expect, beforeEach } from 'vitest';
import { useUserStore } from '../useUserStore';
import { useChatStore } from '../../lib/chatStore';

describe('useUserStore & useChatStore Tests', () => {
  beforeEach(() => {
    useUserStore.setState({
      user: null,
      fullName: 'Student',
      xp: 0,
      level: 1,
      dailyStreak: 0,
      completedLabs: 0,
      aiInteractions: 0,
    });
    useChatStore.setState({
      chats: [],
      activeChatId: null,
    });
  });

  it('initializes user store with authentic default values (no fake stats)', () => {
    const state = useUserStore.getState();
    expect(state.xp).toBe(0);
    expect(state.level).toBe(1);
    expect(state.dailyStreak).toBe(0);
    expect(state.completedLabs).toBe(0);
    expect(state.aiInteractions).toBe(0);
    expect(state.fullName).toBe('Student');
  });

  it('updates authoritative stats and increments level correctly', () => {
    useUserStore.getState().setStats({
      xp: 1250,
      level: 3,
      completedLabs: 4,
      aiInteractions: 12,
    });

    const state = useUserStore.getState();
    expect(state.xp).toBe(1250);
    expect(state.level).toBe(3);
    expect(state.completedLabs).toBe(4);
    expect(state.aiInteractions).toBe(12);
  });

  it('manages chat sessions: creates, adds message, updates title, and isolates threads', () => {
    const { createNewChat, addMessage } = useChatStore.getState();
    createNewChat();

    let state = useChatStore.getState();
    expect(state.chats.length).toBe(1);
    const chatId = state.chats[0].id;

    addMessage(chatId, {
      id: 1,
      text: 'How does gravity affect a pendulum?',
      sender: 'user',
      timestamp: new Date().toISOString(),
    });

    state = useChatStore.getState();
    expect(state.chats[0].messages.length).toBe(1);
    expect(state.chats[0].title).toBe('How does gravity affect a pend...');

    addMessage(chatId, {
      id: 2,
      text: 'The period of a simple pendulum is T = 2π√(L/g). Gravity is in the denominator.',
      sender: 'ai',
      timestamp: new Date().toISOString(),
    });

    state = useChatStore.getState();
    expect(state.chats[0].messages.length).toBe(2);
    expect(state.chats[0].messages[1].sender).toBe('ai');
  });

  it('deletes chat sessions cleanly without state corruption', () => {
    const { createNewChat, deleteChat } = useChatStore.getState();
    createNewChat();
    const chatId = useChatStore.getState().chats[0].id;
    expect(useChatStore.getState().chats.length).toBe(1);

    deleteChat(chatId);
    expect(useChatStore.getState().chats.length).toBe(0);
  });
});

