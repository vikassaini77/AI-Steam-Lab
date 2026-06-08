import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { 
  Plus, MessageSquare, PanelLeftClose, 
  PanelLeftOpen, MoreHorizontal, Settings, ArrowLeft,
  Trash2, Zap, Sliders, User, HelpCircle, LogOut
} from 'lucide-react';
import AITutorSettingsModal from './AITutorSettingsModal';
import { useChatStore } from '../../lib/chatStore';
import { useUserStore } from '../../store/useUserStore';
import { UserAvatar } from '../dashboard/DashboardLayout';
import KnowledgeMap from './KnowledgeMap';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export default function AITutorSidebar({ isOpen, onToggle }: SidebarProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const navigate = useNavigate();

  // Phase 2: Accessibility - Reading Level
  const [readingLevel, setReadingLevel] = useState('Middle School');

  const chats = useChatStore((state) => state.chats) || [];
  const activeChatId = useChatStore((state) => state.activeChatId);
  const createNewChat = useChatStore((state) => state.createNewChat);
  const setActiveChat = useChatStore((state) => state.setActiveChat);
  const deleteChat = useChatStore((state) => state.deleteChat);

  const { fullName } = useUserStore();

  return (
    <>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="h-full bg-[#0d0d20]/90 backdrop-blur-xl border-r border-white/10 flex flex-col flex-shrink-0 relative"
          >
            {/* Header: Back & Toggle Sidebar */}
            <div className="flex items-center justify-between p-3 pb-1">
              <button 
                onClick={() => navigate('/dashboard')}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-cyan-400 transition-colors text-xs font-medium"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Dashboard
              </button>
              <button 
                onClick={onToggle}
                className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-cyan-400 transition-colors"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>

            {/* Header: New Chat */}
            <div className="p-3 pt-1">
              <button 
                onClick={createNewChat}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium text-gray-200"
              >
                <div className="bg-gradient-to-r from-cyan-500 to-blue-500 text-white rounded-full p-1 w-6 h-6 flex items-center justify-center">
                  <span className="text-sm leading-none font-bold">+</span>
                </div>
                New chat
              </button>
            </div>

            {/* Scrollable History */}
            <div className="flex-1 overflow-y-auto p-3 pt-0 space-y-4 scrollbar-hide">
              <div>
                <h3 className="text-xs font-semibold text-gray-500 px-3 pb-1">Recents</h3>
                {chats.length === 0 && (
                  <p className="text-xs text-gray-600 px-3">No chats yet</p>
                )}
                {chats.map((chat) => (
                  <div key={chat.id} className="relative group">
                    <button 
                      onClick={() => setActiveChat(chat.id)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors truncate pr-8 ${
                        activeChatId === chat.id 
                          ? 'bg-white/10 text-cyan-400' 
                          : 'text-gray-300 hover:bg-white/5 hover:text-cyan-400'
                      }`}
                    >
                      {chat.title}
                    </button>
                    <button
                      onClick={() => deleteChat(chat.id)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Phase 2: Accessibility Reading Level */}
              <div className="px-3">
                <h3 className="text-xs font-semibold text-gray-500 pb-2">Reading Level</h3>
                <select 
                  value={readingLevel}
                  onChange={(e) => setReadingLevel(e.target.value)}
                  className="w-full bg-[#12121a] border border-white/10 rounded-lg text-sm text-gray-300 px-3 py-2 outline-none focus:border-cyan-500/50"
                >
                  <option value="Middle School">Middle School</option>
                  <option value="High School">High School</option>
                  <option value="Undergraduate">Undergraduate</option>
                </select>
              </div>

              {/* Phase 2: Knowledge Graph UI */}
              <div className="px-3 pt-2">
                <KnowledgeMap unlockedNode="Newton's 3rd Law" />
              </div>
            </div>

            {/* Profile Section */}
            <div className="p-3 border-t border-white/5 relative">
              <button 
                onClick={() => setProfileMenuOpen(!profileMenuOpen)}
                className="w-full flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-white/10 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr flex items-center justify-center text-white text-sm font-bold shadow-lg shadow-cyan-500/20 overflow-hidden">
                  <UserAvatar className="w-full h-full object-cover rounded-full" />
                </div>
                <span className="text-sm font-medium text-gray-200 flex-1 text-left truncate">
                  {fullName}
                </span>
                <MoreHorizontal className="w-4 h-4 text-gray-400" />
              </button>

              {/* Profile Popover Menu */}
              <AnimatePresence>
                {profileMenuOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute bottom-full left-3 w-56 mb-2 bg-[#12121a] border border-white/10 rounded-xl shadow-xl overflow-hidden backdrop-blur-md"
                  >
                    <div className="p-2 border-b border-white/5">
                      <div className="px-2 py-1 text-sm text-gray-400">{fullName}</div>
                    </div>
                    <div className="p-1">
                      <button 
                        onClick={() => {
                          setProfileMenuOpen(false);
                          navigate('/pricing');
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-cyan-400 bg-cyan-400/10 hover:bg-cyan-400/20 transition-colors"
                      >
                        <Zap className="w-4 h-4" />
                        Upgrade plan
                      </button>
                      <button 
                        onClick={() => {
                          setSettingsOpen(true);
                          setProfileMenuOpen(false);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-white/10 transition-colors hover:text-cyan-400"
                      >
                        <Sliders className="w-4 h-4" />
                        Personalization
                      </button>
                      <button 
                        onClick={() => {
                          setProfileMenuOpen(false);
                          navigate('/profile');
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-white/10 transition-colors hover:text-cyan-400"
                      >
                        <User className="w-4 h-4" />
                        Profile
                      </button>
                      <button 
                        onClick={() => {
                          setSettingsOpen(true);
                          setProfileMenuOpen(false);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-white/10 transition-colors hover:text-cyan-400"
                      >
                        <Settings className="w-4 h-4" />
                        Settings
                      </button>
                      <button 
                        onClick={() => {
                          setProfileMenuOpen(false);
                          navigate('/docs');
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-white/10 transition-colors hover:text-cyan-400"
                      >
                        <HelpCircle className="w-4 h-4" />
                        Help
                      </button>
                      <div className="h-px bg-white/5 my-1" />
                      <button 
                        onClick={async () => {
                          setProfileMenuOpen(false);
                          try {
                            const { supabase } = await import('../../lib/supabase');
                            await supabase.auth.signOut();
                            navigate('/');
                          } catch (e) {
                            console.error('Logout failed:', e);
                          }
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-400 hover:bg-red-400/10 transition-colors"
                      >
                        <LogOut className="w-4 h-4" />
                        Log out
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Toggle Button (visible only when sidebar is closed) */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="absolute top-4 left-4 z-40 p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-cyan-400 transition-colors"
        >
          <PanelLeftOpen className="w-5 h-5" />
        </button>
      )}

      <AITutorSettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
