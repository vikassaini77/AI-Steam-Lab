import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Message {
  id: number;
  text: string;
  sender: 'user' | 'ai';
  timestamp: string; // Dates become strings when serialized
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: string;
}

interface ChatState {
  chats: ChatSession[];
  activeChatId: string | null;
  createNewChat: () => void;
  setActiveChat: (id: string) => void;
  deleteChat: (id: string) => void;
  addMessage: (chatId: string, message: Message) => void;
  updateMessage: (chatId: string, messageId: number, newText: string) => void;
  updateTitle: (chatId: string, title: string) => void;
  setMessages: (chatId: string, newMessages: Message[]) => void;
  botName: string;
  setBotName: (name: string) => void;
  botVoiceURI: string;
  setBotVoiceURI: (uri: string) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      chats: [],
      activeChatId: null,
      botName: 'Professor Nova',
      botVoiceURI: '', // Empty means default voice

      setBotName: (name) => set({ botName: name }),
      setBotVoiceURI: (uri) => set({ botVoiceURI: uri }),

      createNewChat: () => {
        const newId = Date.now().toString();
        const newChat: ChatSession = {
          id: newId,
          title: 'New Chat',
          messages: [],
          updatedAt: new Date().toISOString()
        };
        set((state) => ({
          chats: [newChat, ...state.chats],
          activeChatId: newId
        }));
      },

      setActiveChat: (id) => {
        set({ activeChatId: id });
      },

      deleteChat: (id) => {
        set((state) => {
          const newChats = state.chats.filter(c => c.id !== id);
          return {
            chats: newChats,
            activeChatId: state.activeChatId === id ? (newChats[0]?.id || null) : state.activeChatId
          };
        });
      },

      addMessage: (chatId, message) => {
        set((state) => ({
          chats: state.chats.map(chat => {
            if (chat.id === chatId) {
              let title = chat.title;
              if (title === 'New Chat' && message.sender === 'user') {
                title = message.text.slice(0, 30) + (message.text.length > 30 ? '...' : '');
              }
              return {
                ...chat,
                title,
                messages: [...chat.messages, message],
                updatedAt: new Date().toISOString()
              };
            }
            return chat;
          }).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        }));
      },

      updateMessage: (chatId, messageId, newText) => {
        set((state) => ({
          chats: state.chats.map(chat => {
            if (chat.id === chatId) {
              return {
                ...chat,
                messages: chat.messages.map(m => m.id === messageId ? { ...m, text: newText } : m),
                updatedAt: new Date().toISOString()
              };
            }
            return chat;
          }).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        }));
      },

      updateTitle: (chatId, title) => {
        set((state) => ({
          chats: state.chats.map(chat => chat.id === chatId ? { ...chat, title } : chat)
        }));
      },

      setMessages: (chatId, newMessages) => {
        set((state) => ({
          chats: state.chats.map(chat => {
            if (chat.id === chatId) {
              return {
                ...chat,
                messages: newMessages,
                updatedAt: new Date().toISOString()
              };
            }
            return chat;
          }).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        }));
      }
    }),
    {
      name: 'neurolab-chat-storage',
    }
  )
);
