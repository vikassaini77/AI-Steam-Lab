import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { pushNotification } from '../../lib/notificationStore';
import { 
  X, Shield, Bell, Palette, LayoutGrid, 
  Database, Lock, Keyboard, Settings2 
} from 'lucide-react';
import { useChatStore } from '../../lib/chatStore';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'General' | 'Notifications' | 'Personalization' | 'Apps' | 'Billing' | 'Data controls' | 'Storage' | 'Security' | 'Account' | 'Keyboard';

export default function AITutorSettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('General');
  const { botName, setBotName, botVoiceURI, setBotVoiceURI } = useChatStore();
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const navigate = useNavigate();

  // Local UI States for interactivity
  const [pushNotifs, setPushNotifs] = useState(true);
  const [emailNotifs, setEmailNotifs] = useState(false);
  const [avatarAnimations, setAvatarAnimations] = useState(true);
  const [dictation, setDictation] = useState(true);
  const [connectedGithub, setConnectedGithub] = useState(false);
  const [connectedDrive, setConnectedDrive] = useState(false);
  const [mfaBannerVisible, setMfaBannerVisible] = useState(true);

  useEffect(() => {
    const loadVoices = () => {
      setVoices(window.speechSynthesis.getVoices());
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, []);

  const tabs: { id: TabType; icon: React.ElementType }[] = [
    { id: 'General', icon: Settings2 },
    { id: 'Notifications', icon: Bell },
    { id: 'Personalization', icon: Palette },
    { id: 'Apps', icon: LayoutGrid },
    { id: 'Data controls', icon: Database },
    { id: 'Security', icon: Shield },
    { id: 'Keyboard', icon: Keyboard },
  ];

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        />

        {/* Modal Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-4xl bg-[#12121a]/95 backdrop-blur-xl text-gray-100 rounded-xl overflow-hidden shadow-[0_0_50px_rgba(0,255,255,0.1)] flex h-[600px] border border-white/10"
        >
          {/* Sidebar Tabs */}
          <div className="w-64 bg-[#0d0d20]/50 flex flex-col p-3 border-r border-white/5 overflow-y-auto scrollbar-hide">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive 
                        ? 'bg-gradient-to-r from-cyan-500/20 to-transparent text-cyan-400 border-l-2 border-cyan-400 rounded-l-none' 
                        : 'text-gray-400 hover:bg-white/5 hover:text-cyan-400'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.id}
                </button>
              );
            })}
          </div>

          {/* Tab Content Area */}
          <div className="flex-1 bg-transparent relative flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-6 pb-2">
              <h2 className="text-xl font-semibold text-white">{activeTab}</h2>
              <button 
                onClick={onClose}
                className="p-2 rounded-full hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto p-6 pt-4">
              {activeTab === 'General' && (
                <div className="space-y-8 max-w-2xl">
                  {/* Security Banner Promo */}
                  {mfaBannerVisible && (
                    <div className="bg-black/40 border border-white/10 rounded-xl p-4 flex gap-4 items-start relative">
                      <Shield className="w-6 h-6 text-gray-300 shrink-0" />
                      <div>
                        <h4 className="font-semibold text-white text-sm">Secure your account</h4>
                        <p className="text-sm text-gray-400 mt-1">Add multi-factor authentication (MFA), like a text message or authenticator app, to help protect your account when logging in.</p>
                        <button 
                          onClick={() => { onClose(); navigate('/dashboard/profile'); }}
                          className="mt-3 px-4 py-1.5 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-semibold rounded-full hover:opacity-90 transition-opacity"
                        >
                          Set up MFA
                        </button>
                      </div>
                      <button 
                        onClick={() => setMfaBannerVisible(false)}
                        className="absolute top-4 right-4 text-gray-500 hover:text-white"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  <div className="space-y-6">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Appearance</span>
                      <select className="bg-transparent border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-white/40 cursor-pointer">
                        <option value="system" className="bg-[#0d0d1a]">System</option>
                        <option value="dark" className="bg-[#0d0d1a]">Dark</option>
                        <option value="light" className="bg-[#0d0d1a]">Light</option>
                      </select>
                    </div>
                    
                    <div className="flex items-center justify-between border-t border-white/5 pt-6">
                      <span className="text-sm text-gray-300">Contrast</span>
                      <select className="bg-transparent border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-white/40 cursor-pointer">
                        <option value="system" className="bg-[#0d0d1a]">System</option>
                        <option value="high" className="bg-[#0d0d1a]">High Contrast</option>
                      </select>
                    </div>

                    <div className="flex items-center justify-between border-t border-white/5 pt-6">
                      <span className="text-sm text-gray-300">Accent color</span>
                      <div className="flex items-center gap-2 text-sm text-gray-300">
                        <div className="w-3 h-3 rounded-full bg-cyan-500 shadow-[0_0_10px_rgba(0,255,255,0.5)]" />
                        <span>Cyan</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between border-t border-white/5 pt-6">
                      <span className="text-sm text-gray-300">Language</span>
                      <select className="bg-transparent border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-white/40 cursor-pointer">
                        <option value="auto" className="bg-[#0d0d1a]">Auto-detect</option>
                        <option value="en" className="bg-[#0d0d1a]">English</option>
                        <option value="es" className="bg-[#0d0d1a]">Spanish</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1 border-t border-white/5 pt-6">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-300">Enable Dictation</span>
                        <div 
                          onClick={() => setDictation(!dictation)}
                          className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${dictation ? 'bg-cyan-500 shadow-[0_0_10px_rgba(0,255,255,0.3)]' : 'bg-white/10'}`}
                        >
                          <span className={`${dictation ? 'translate-x-4 bg-white' : 'translate-x-1 bg-gray-400'} inline-block h-4 w-4 transform rounded-full transition`} />
                        </div>
                      </div>
                      <span className="text-xs text-gray-500">Use dictation in the chat composer.</span>
                    </div>

                  </div>
                </div>
              )}

              {/* Notifications Tab */}
              {activeTab === 'Notifications' && (
                <div className="space-y-6 max-w-2xl">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Push notifications</span>
                      <div 
                        onClick={() => setPushNotifs(!pushNotifs)}
                        className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${pushNotifs ? 'bg-cyan-500 shadow-[0_0_10px_rgba(0,255,255,0.3)]' : 'bg-white/10'}`}
                      >
                        <span className={`${pushNotifs ? 'translate-x-4 bg-white' : 'translate-x-1 bg-gray-400'} inline-block h-4 w-4 transform rounded-full transition`} />
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">Receive alerts when long-running experiments complete.</span>
                  </div>
                  
                  <div className="flex flex-col gap-1 border-t border-white/5 pt-6">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Email notifications</span>
                      <div 
                        onClick={() => setEmailNotifs(!emailNotifs)}
                        className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${emailNotifs ? 'bg-cyan-500 shadow-[0_0_10px_rgba(0,255,255,0.3)]' : 'bg-white/10'}`}
                      >
                        <span className={`${emailNotifs ? 'translate-x-4 bg-white' : 'translate-x-1 bg-gray-400'} inline-block h-4 w-4 transform rounded-full transition`} />
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">Weekly summaries of your STEM learning progress.</span>
                  </div>
                </div>
              )}

              {/* Personalization Tab */}
              {activeTab === 'Personalization' && (
                <div className="space-y-6 max-w-2xl">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">AI Tutor Name</span>
                    <input 
                      type="text"
                      value={botName}
                      onChange={(e) => setBotName(e.target.value)}
                      className="bg-transparent border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-cyan-500 max-w-[200px]"
                      placeholder="e.g. Professor Nova"
                    />
                  </div>
                  
                  <div className="flex items-center justify-between border-t border-white/5 pt-6">
                    <span className="text-sm text-gray-300">AI Voice</span>
                    <select 
                      value={botVoiceURI}
                      onChange={(e) => setBotVoiceURI(e.target.value)}
                      className="bg-[#0c0c19] border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-cyan-500 cursor-pointer max-w-[200px]"
                    >
                      <option value="">System Default</option>
                      {voices.map(v => (
                        <option key={v.voiceURI} value={v.voiceURI}>
                          {v.name} ({v.lang})
                        </option>
                      ))}
                    </select>
                  </div>
                  
                  <div className="flex items-center justify-between border-t border-white/5 pt-6">
                    <span className="text-sm text-gray-300">AI Teaching Style</span>
                    <select className="bg-transparent border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-white/40 cursor-pointer">
                      <option value="socratic">Socratic (Guiding)</option>
                      <option value="direct">Direct (Factual)</option>
                      <option value="enthusiastic">Enthusiastic</option>
                    </select>
                  </div>
                  
                  <div className="flex flex-col gap-1 border-t border-white/5 pt-6">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Avatar Animations</span>
                      <div 
                        onClick={() => setAvatarAnimations(!avatarAnimations)}
                        className={`relative inline-flex h-5 w-9 cursor-pointer items-center rounded-full transition-colors ${avatarAnimations ? 'bg-cyan-500 shadow-[0_0_10px_rgba(0,255,255,0.3)]' : 'bg-white/10'}`}
                      >
                        <span className={`${avatarAnimations ? 'translate-x-4 bg-white' : 'translate-x-1 bg-gray-400'} inline-block h-4 w-4 transform rounded-full transition`} />
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">Allow Professor Nova to use dynamic facial expressions.</span>
                  </div>
                </div>
              )}

              {/* Apps Tab */}
              {activeTab === 'Apps' && (
                <div className="space-y-6 max-w-2xl">
                  <div className="flex items-center justify-between border border-white/10 p-4 rounded-xl bg-black/20">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center font-bold text-white">GH</div>
                      <div>
                        <h4 className="text-sm font-semibold text-white">GitHub</h4>
                        <p className="text-xs text-gray-400">Sync coding experiments to your repositories.</p>
                      </div>
                    </div>
                    <button 
                      onClick={() => setConnectedGithub(!connectedGithub)}
                      className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${connectedGithub ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                    >
                      {connectedGithub ? 'Connected' : 'Connect'}
                    </button>
                  </div>

                  <div className="flex items-center justify-between border border-white/10 p-4 rounded-xl bg-black/20">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center font-bold text-white">GD</div>
                      <div>
                        <h4 className="text-sm font-semibold text-white">Google Drive</h4>
                        <p className="text-xs text-gray-400">Export lab reports automatically.</p>
                      </div>
                    </div>
                    <button 
                      onClick={() => setConnectedDrive(!connectedDrive)}
                      className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${connectedDrive ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-white/10 hover:bg-white/20 text-white'}`}
                    >
                      {connectedDrive ? 'Connected' : 'Connect'}
                    </button>
                  </div>
                </div>
              )}

              {/* Data Controls Tab */}
              {activeTab === 'Data controls' && (
                <div className="space-y-6 max-w-2xl">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Export Chat History</span>
                      <button 
                        onClick={() => pushNotification('Chat history exported successfully!', 'success')}
                        className="px-4 py-1.5 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors"
                      >
                        Export to CSV
                      </button>
                    </div>
                    <span className="text-xs text-gray-500">Download all your interactions with Professor Nova.</span>
                  </div>

                  <div className="flex flex-col gap-1 border-t border-red-500/20 pt-6 mt-6">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-red-400 font-semibold">Delete All Data</span>
                      <button 
                        onClick={() => { onClose(); navigate('/dashboard/profile'); }}
                        className="px-4 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 text-sm rounded-lg transition-colors"
                      >
                        Delete Account
                      </button>
                    </div>
                    <span className="text-xs text-red-400/60">This action is permanent and cannot be undone.</span>
                  </div>
                </div>
              )}

              {/* Security Tab */}
              {activeTab === 'Security' && (
                <div className="space-y-6 max-w-2xl">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Two-Factor Authentication (2FA)</span>
                      <button 
                        onClick={() => { onClose(); navigate('/dashboard/profile'); }}
                        className="px-4 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-sm rounded-lg transition-colors"
                      >
                        Enable
                      </button>
                    </div>
                    <span className="text-xs text-gray-500">Protect your account with an extra layer of security.</span>
                  </div>
                  
                  <div className="flex flex-col gap-1 border-t border-white/5 pt-6 mt-6">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">Active Sessions</span>
                      <button 
                        onClick={() => pushNotification('Logged out from all other devices successfully.', 'success')}
                        className="px-4 py-1.5 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors"
                      >
                        Log out all devices
                      </button>
                    </div>
                    <span className="text-xs text-gray-500">You are currently logged in on 1 device.</span>
                  </div>
                </div>
              )}

              {/* Keyboard Tab */}
              {activeTab === 'Keyboard' && (
                <div className="space-y-4 max-w-2xl">
                  <div className="flex items-center justify-between p-3 border border-white/10 rounded-lg bg-black/20">
                    <span className="text-sm text-gray-300">Open Command Palette</span>
                    <div className="flex gap-1">
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">⌘</kbd>
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">K</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 border border-white/10 rounded-lg bg-black/20">
                    <span className="text-sm text-gray-300">New Chat</span>
                    <div className="flex gap-1">
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">⌘</kbd>
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">N</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 border border-white/10 rounded-lg bg-black/20">
                    <span className="text-sm text-gray-300">Send Message</span>
                    <div className="flex gap-1">
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">Enter</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 border border-white/10 rounded-lg bg-black/20">
                    <span className="text-sm text-gray-300">Line Break</span>
                    <div className="flex gap-1">
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">Shift</kbd>
                      <kbd className="px-2 py-1 bg-white/10 rounded text-xs text-gray-400 font-mono">Enter</kbd>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
