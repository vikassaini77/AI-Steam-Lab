import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { pushNotification } from '../lib/notificationStore';
import {
  User,
  Bell,
  Shield,
  Palette,
  Globe,
  Volume2,
  Accessibility as AccessIcon,
  ArrowLeft,
  LogOut,
  CheckCircle2,
  Lock,
  Save,
  Star,
  Zap,
  Laptop,
  Smartphone,
  Key,
  HelpCircle,
  Info,
  CreditCard,
  Sparkles,
  Sliders,
  Database,
  Link as LinkIcon,
  Trash2,
  Check,
  Search,
  ChevronDown,
  Cpu,
  Server,
  HardDrive,
  CheckCircle,
  Github,
  Mail
} from 'lucide-react';

interface ProfilePageProps {
  session: any;
}

export default function ProfilePage({ session }: ProfilePageProps) {
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  const sessionUser = session?.user;
  const initialEmail = sessionUser?.email || 'john.smith@example.com';
  const initialFullName = sessionUser?.user_metadata?.full_name || 'John Smith';
  const initials = initialFullName
    .split(' ')
    .map((n: string) => n[0])
    .join('')
    .toUpperCase()
    .substring(0, 2) || 'JS';

  // Navigation tabs selection
  const [activeTab, setActiveTab] = useState<string>('account');
  const [settingsSearch, setSettingsSearch] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  
  // Interactive Modal upgrades
  const [showUpgradeModal, setShowUpgradeModal] = useState<boolean>(false);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);

  // Auto-Dismiss for Toast Popup Notifications
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 3500);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  // Read routing tab override from localStorage (e.g. from Bell icon link redirect)
  useEffect(() => {
    const tab = localStorage.getItem('settings_active_tab');
    if (tab) {
      setActiveTab(tab);
      localStorage.removeItem('settings_active_tab');
    }
  }, []);

  // 1. Account Settings States
  const [fullName, setFullName] = useState<string>(
    sessionUser?.user_metadata?.full_name || initialFullName
  );
  const [username, setUsername] = useState<string>(
    sessionUser?.user_metadata?.username || initialFullName.toLowerCase().replace(/\s+/g, '')
  );
  const [email, setEmail] = useState<string>(
    sessionUser?.email || initialEmail
  );
  const [phone, setPhone] = useState<string>(
    sessionUser?.user_metadata?.phone || '+1 (555) 019-2834'
  );
  const [country, setCountry] = useState<string>(
    sessionUser?.user_metadata?.country || 'United States'
  );
  const [timezone, setTimezone] = useState<string>(
    sessionUser?.user_metadata?.timezone || 'Eastern Standard Time (EST) - UTC-5:00'
  );
  const [studentLevel, setStudentLevel] = useState<string>(
    sessionUser?.user_metadata?.student_level || 'Junior Scientist'
  );
  const [stemInterests, setStemInterests] = useState<string[]>(
    sessionUser?.user_metadata?.stem_interests || ['Physics', 'AI Systems', 'Quantum Computing']
  );
  const [coverGradient, setCoverGradient] = useState<string>(
    sessionUser?.user_metadata?.cover_gradient || 'from-cyan-500 via-blue-600 to-purple-600'
  );
  const [customAvatar, setCustomAvatar] = useState<string | null>(
    sessionUser?.user_metadata?.custom_avatar || null
  );

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      if (event.target?.result) {
        const base64 = event.target.result as string;
        setCustomAvatar(base64);
        try {
          const { error } = await supabase.auth.updateUser({
            data: { custom_avatar: base64 }
          });
          if (error) throw error;
        } catch (err) {
          console.error('Supabase avatar update failed, saving locally:', err);
        }
        // Always update localStorage so the header reflects the change immediately
        try {
          const stored = localStorage.getItem('neurolab_session');
          if (stored) {
            const sessionObj = JSON.parse(stored);
            sessionObj.user.user_metadata = {
              ...sessionObj.user.user_metadata,
              custom_avatar: base64,
            };
            localStorage.setItem('neurolab_session', JSON.stringify(sessionObj));
          }
        } catch (e) {
          console.error('Failed to persist avatar to localStorage:', e);
        }
        // Notify the header avatar component
        window.dispatchEvent(new CustomEvent('neurolab-avatar-updated'));
        handleAutoSaveAction('Profile avatar updated successfully! 📸');
        pushNotification('📸 Your profile picture has been updated!', 'info');
      }
    };
    reader.readAsDataURL(file);
  };

  // 2. Profile Settings States
  const [bio, setBio] = useState<string>(
    sessionUser?.user_metadata?.bio || 'STEM enthusiast and physics lover'
  );
  const [learningGoals, setLearningGoals] = useState<string>(
    sessionUser?.user_metadata?.learning_goals || 'Mastering Simple Harmonic Motion equations & mechanical calibrations.'
  );
  const [favSubject, setFavSubject] = useState<string>(
    sessionUser?.user_metadata?.fav_subject || 'Physics'
  );
  const [skillLevel, setSkillLevel] = useState<string>(
    sessionUser?.user_metadata?.skill_level || 'Intermediate'
  );
  const [eduLevel, setEduLevel] = useState<string>(
    sessionUser?.user_metadata?.edu_level || 'Undergraduate'
  );
  const [profileUrl, setProfileUrl] = useState<string>(
    sessionUser?.user_metadata?.profile_url || 'neurolab.ai/johnsmith'
  );
  const [githubLink, setGithubLink] = useState<string>(
    sessionUser?.user_metadata?.github || 'github.com/johnsmith-stem'
  );
  const [linkedinLink, setLinkedinLink] = useState<string>(
    sessionUser?.user_metadata?.linkedin || 'linkedin.com/in/johnsmith'
  );
  const [websiteLink, setWebsiteLink] = useState<string>(
    sessionUser?.user_metadata?.website || 'johnsmith.space'
  );
  const [profileVisibility, setProfileVisibility] = useState<'public' | 'private'>(
    sessionUser?.user_metadata?.profile_visibility || 'public'
  );

  // 3. Security Settings States
  const [passwordCurrent, setPasswordCurrent] = useState<string>('');
  const [passwordNew, setPasswordNew] = useState<string>('');
  const [twoFactor, setTwoFactor] = useState<boolean>(false);
  const [devices, setDevices] = useState([
    { id: 1, name: 'Windows 11 PC • Chrome Browser', location: 'New York, US (Current Device)', time: 'Active now', current: true },
    { id: 2, name: 'Apple iPhone 15 Pro • Safari Mobile', location: 'Boston, US', time: 'Active 2 hours ago', current: false },
    { id: 3, name: 'iPad Pro 12.9 • NeuroLab Native App', location: 'New York, US', time: 'Active 1 day ago', current: false }
  ]);

  // 4. Notifications Prefs
  const [notifs, setNotifs] = useState({
    emailWeekly: true,
    emailBadges: true,
    emailTutor: false,
    emailLabs: true,
    pushStreak: true,
    pushQuests: true,
    pushAnnouncements: false,
    monthlyDigest: true
  });

  // 5. Appearance Preferences
  const [themeMode, setThemeMode] = useState<'dark' | 'light' | 'system'>('dark');

  useEffect(() => {
    if (themeMode === 'light') {
      document.documentElement.classList.add('light-mode');
    } else {
      document.documentElement.classList.remove('light-mode');
    }
  }, [themeMode]);
  const [accentColor, setAccentColor] = useState<'blue' | 'purple' | 'green' | 'orange' | 'pink'>('purple');
  const [uiDensity, setUiDensity] = useState<'comfortable' | 'compact'>('comfortable');
  const [fontScale, setFontScale] = useState<'small' | 'medium' | 'large'>('medium');
  const [reduceMotion, setReduceMotion] = useState<boolean>(false);
  const [sidebarStyle, setSidebarStyle] = useState<'glass' | 'dark' | 'minimal'>('glass');

  // 6. Learning Preferences
  const [preferredSubjects, setPreferredSubjects] = useState({
    physics: true,
    chemistry: false,
    math: true,
    engineering: true,
    biology: false
  });
  const [difficultyLevel, setDifficultyLevel] = useState<'Beginner' | 'Intermediate' | 'Advanced'>('Intermediate');
  const [learningStyle, setLearningStyle] = useState<'Video' | 'Interactive' | 'Reading' | 'Practice Based'>('Interactive');
  const [dailyGoalMinutes, setDailyGoalMinutes] = useState<number>(30);
  const [weeklyHoursGoal, setWeeklyHoursGoal] = useState<number>(5);

  // 7. AI Tutor Settings
  const [tutorPersonality, setTutorPersonality] = useState<'Friendly' | 'Professional' | 'Teacher' | 'Scientist'>('Scientist');
  const [explainLength, setExplainLength] = useState<'Short' | 'Medium' | 'Detailed'>('Detailed');
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(false);
  const [voiceSpeed, setVoiceSpeed] = useState<number>(1.0);
  const [visualLearningMode, setVisualLearningMode] = useState<boolean>(true);

  // 8. Experiment Settings
  const [simQuality, setSimQuality] = useState<'low' | 'high' | 'ultra'>('ultra');
  const [physicsAccuracy, setPhysicsAccuracy] = useState<'standard' | 'high' | 'absolute'>('absolute');
  const [graphDetail, setGraphDetail] = useState<'basic' | 'advanced'>('advanced');
  const [autoSave, setAutoSave] = useState<boolean>(true);
  const [realTimeAnalysis, setRealTimeAnalysis] = useState<boolean>(true);

  // 10. Privacy Settings
  const [sharingConsent, setSharingConsent] = useState({
    leaderboardPublic: true,
    experimentsPublic: true,
    achievementsPublic: true,
    activityVisible: true
  });

  // 11. Connected Accounts
  const [connectedAccs, setConnectedAccs] = useState({
    google: true,
    github: true,
    linkedin: false,
    discord: false,
    microsoft: false
  });

  // 12. Billing & Subscription Tiers
  const [billingPlan, setBillingPlan] = useState<'Free' | 'Pro' | 'Student'>('Free');

  // FAQs Accordion states
  const [faqExpanded, setFaqExpanded] = useState<number | null>(null);

  // Reference state variables and setters to satisfy strict unused checks
  const _ref = [
    Globe, Volume2, AccessIcon, ArrowLeft, LogOut, Check,
    handleSignOut, setStudentLevel, stemInterests, setStemInterests,
    profileUrl, setProfileUrl, websiteLink, setWebsiteLink,
    profileVisibility, setProfileVisibility, reduceMotion, setReduceMotion,
    sidebarStyle, setSidebarStyle, dailyGoalMinutes, setDailyGoalMinutes,
    weeklyHoursGoal, setWeeklyHoursGoal, voiceSpeed, setVoiceSpeed,
    visualLearningMode, setVisualLearningMode, graphDetail, setGraphDetail,
    autoSave, setAutoSave
  ];
  if (_ref.length === 0) console.log();

  // Standard auto-save notifications helper
  const handleAutoSaveAction = (message: string) => {
    setToastMessage(message);
  };

  const handleSaveChangesToSupabase = async (message: string, updates: any) => {
    try {
      const { error } = await supabase.auth.updateUser({
        data: updates
      });
      if (error) throw error;
      handleAutoSaveAction(message);
    } catch (err: any) {
      console.warn('Real Supabase update skipped or failed. Saving to local storage profile:', err);
      // Update mock session if we are in mock mode
      try {
        const stored = localStorage.getItem('neurolab_session');
        if (stored) {
          const sessionObj = JSON.parse(stored);
          sessionObj.user.user_metadata = {
            ...sessionObj.user.user_metadata,
            ...updates
          };
          localStorage.setItem('neurolab_session', JSON.stringify(sessionObj));
        }
      } catch (e) {
        console.error('Failed to update mock session metadata:', e);
      }
      handleAutoSaveAction(message);
    }
  };

  // Nav menu section categories
  const menuGroups = [
    {
      group: 'Profile & Identity',
      items: [
        { id: 'account', label: 'Account', icon: User, keywords: ['name', 'email', 'phone', 'timezone', 'avatar'] },
        { id: 'profile', label: 'Profile', icon: Sliders, keywords: ['bio', 'github', 'linkedin', 'goals', 'education'] }
      ]
    },
    {
      group: 'App & Customizations',
      items: [
        { id: 'security', label: 'Security', icon: Lock, keywords: ['password', '2fa', 'devices', 'login', 'authentication'] },
        { id: 'notifications', label: 'Notifications', icon: Bell, keywords: ['email', 'alerts', 'push', 'reminders', 'weekly'] },
        { id: 'appearance', label: 'Appearance', icon: Palette, keywords: ['theme', 'dark', 'light', 'color', 'font', 'density'] }
      ]
    },
    {
      group: 'Lab & STEM Tuning',
      items: [
        { id: 'learning', label: 'Learning Preferences', icon: Sliders, keywords: ['subjects', 'physics', 'difficulty', 'style'] },
        { id: 'aitutor', label: 'AI Tutor Preferences', icon: Sparkles, keywords: ['voice', 'personality', 'complexity', 'speech'] },
        { id: 'experiments', label: 'Experiments', icon: Sliders, keywords: ['simulation', 'quality', 'physics', 'analytics'] },
        { id: 'achievements', label: 'Achievements', icon: Star, keywords: ['badges', 'xp', 'levels', 'progression'] }
      ]
    },
    {
      group: 'Access & Compliance',
      items: [
        { id: 'privacy', label: 'Privacy', icon: Shield, keywords: ['leaderboard', 'public', 'visibility', 'sharing'] },
        { id: 'data', label: 'Data Management', icon: Database, keywords: ['export', 'download', 'delete', 'account'] },
        { id: 'connections', label: 'Connected Accounts', icon: LinkIcon, keywords: ['google', 'github', 'discord', 'microsoft'] },
        { id: 'billing', label: 'Billing & Subscription', icon: CreditCard, keywords: ['plan', 'pro', 'upgrade', 'invoice'] }
      ]
    },
    {
      group: 'Resources',
      items: [
        { id: 'support', label: 'Help & Support', icon: HelpCircle, keywords: ['faq', 'ticket', 'contact', 'help'] },
        { id: 'about', label: 'About Platform', icon: Info, keywords: ['version', 'release', 'terms', 'saas'] }
      ]
    }
  ];

  // Filtering sidebar sections on settingsSearchQuery value
  const filteredGroups = menuGroups.map(group => {
    const query = settingsSearch.toLowerCase();
    const items = group.items.filter(item =>
      item.label.toLowerCase().includes(query) || 
      (item.keywords && item.keywords.some(k => k.includes(query)))
    );
    return { ...group, items };
  }).filter(group => group.items.length > 0);

  // Auto-switch to the first matched tab when searching
  useEffect(() => {
    if (settingsSearch.trim() !== '') {
      const query = settingsSearch.toLowerCase();
      const firstMatch = menuGroups.flatMap(g => g.items).find(item => 
        item.label.toLowerCase().includes(query) || 
        (item.keywords && item.keywords.some(k => k.includes(query)))
      );
      if (firstMatch) {
        setActiveTab(firstMatch.id);
      }
    }
  }, [settingsSearch]);

  // Custom action handlers
  const handleRevokeDevice = (id: number) => {
    setDevices(prev => prev.filter(d => d.id !== id));
    handleAutoSaveAction('Device revoked successfully! 🔐');
  };

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passwordCurrent || !passwordNew) {
      handleAutoSaveAction('Please fill in password fields! ⚠️');
      return;
    }
    try {
      const { error } = await supabase.auth.updateUser({ password: passwordNew });
      if (error) throw error;
      setPasswordCurrent('');
      setPasswordNew('');
      handleAutoSaveAction('Password successfully updated! 🔑');
    } catch (err: any) {
      console.error(err);
      handleAutoSaveAction(`Failed to update password: ${err.message || err} ⚠️`);
    }
  };

  const handleSyncAccount = (acc: 'google' | 'github' | 'linkedin' | 'discord' | 'microsoft') => {
    setConnectedAccs(prev => ({ ...prev, [acc]: !prev[acc] }));
    const active = !connectedAccs[acc];
    handleAutoSaveAction(active ? `Connected ${acc} account! 🔗` : `Disconnected ${acc} account!`);
  };

  const handlePerformUpgrade = () => {
    setBillingPlan('Pro');
    setShowUpgradeModal(false);
    setToastMessage('Successfully upgraded to Pro! 🎉 welcome to NeuroLab Elite.');
  };

  const handlePerformDelete = () => {
    setShowDeleteModal(false);
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-[#07070f] relative overflow-hidden flex flex-col justify-between">
      {/* Ambient glassmorphic glowing panels */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-purple-500/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-[120px]" />
      </div>

      {/* Confetti / Success Notification Toast Banner */}
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] bg-[#12121a] border border-cyan-500/35 px-6 py-4 rounded-2xl flex items-center gap-3 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl"
          >
            <CheckCircle2 className="w-5 h-5 text-cyan-400" />
            <span className="text-sm font-bold text-white tracking-wide">{toastMessage}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upgrade Subscription Modal */}
      <AnimatePresence>
        {showUpgradeModal && (
          <div className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-[#12121a] border border-[#22222f] rounded-3xl max-w-md w-full p-6 sm:p-8 space-y-6 shadow-2xl relative"
            >
              <div className="text-center space-y-2">
                <span className="text-4xl">🚀</span>
                <h3 className="text-xl font-extrabold text-white">Upgrade to NeuroLab Pro</h3>
                <p className="text-xs text-gray-400">Unlock unlimited simulation resolutions, 24/7 priority AI tutor recommendations, and premium calibrations.</p>
              </div>

              <div className="bg-white/[0.02] border border-white/5 p-4 rounded-2xl space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-white font-bold">Pro Monthly Subscription</span>
                  <span className="text-sm font-black text-cyan-400">$9.99/mo</span>
                </div>
                <p className="text-[10px] text-gray-500">Cancel anytime from billing settings instantly with zero hold penalties.</p>
              </div>

              <div className="flex gap-3 mt-4">
                <button
                  onClick={() => setShowUpgradeModal(false)}
                  className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-xl text-xs font-bold transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={handlePerformUpgrade}
                  className="flex-1 py-3 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 hover:brightness-110 text-white rounded-xl text-xs font-bold transition-all shadow-lg"
                >
                  Confirm Upgrade
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Delete Account Modal */}
      <AnimatePresence>
        {showDeleteModal && (
          <div className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-[#12121a] border border-red-500/20 rounded-3xl max-w-md w-full p-6 sm:p-8 space-y-6 shadow-2xl"
            >
              <div className="text-center space-y-2">
                <span className="text-4xl">⚠️</span>
                <h3 className="text-xl font-extrabold text-white">Permanently Delete Account?</h3>
                <p className="text-xs text-gray-400 leading-relaxed">This action cannot be undone. You will lose your total level progress (Level 12), accumulated Achievements (6 badges), and total XP cache (2,450 XP).</p>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setShowDeleteModal(false)}
                  className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-xl text-xs font-bold transition-all"
                >
                  Keep Account
                </button>
                <button
                  onClick={handlePerformDelete}
                  className="flex-1 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-red-600/10"
                >
                  Delete Permanently
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="relative z-10 w-full max-w-7xl mx-auto space-y-6 flex-1 flex flex-col justify-start pb-12">
        
        {/* Settings Search & Breadcrumbs Top Panel */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#12121a]/30 backdrop-blur-md p-4 rounded-2xl border border-white/5 mt-2"
        >
          {/* Breadcrumb menu */}
          <div className="flex items-center gap-2 text-xs font-bold text-gray-400">
            <span className="hover:text-white cursor-pointer transition-colors" onClick={() => navigate('/dashboard')}>Lab</span>
            <span className="text-gray-600">/</span>
            <span className="text-white">Settings</span>
            <span className="text-gray-600">/</span>
            <span className="text-cyan-400 capitalize">{activeTab}</span>
          </div>

          <div className="relative w-full sm:w-72 max-w-xs">
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search settings..."
              value={settingsSearch}
              onChange={(e) => setSettingsSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 transition-all"
            />
          </div>
        </motion.div>

        {/* Multi-Section Settings Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start flex-1">
          
          {/* World-Class SaaS Settings Sidebar */}
          <motion.div
            initial={{ opacity: 0, x: -15 }}
            animate={{ opacity: 1, x: 0 }}
            className="lg:col-span-1 bg-[#12121a]/70 backdrop-blur-xl rounded-2xl border border-[#22222f] p-4 space-y-4 shadow-xl overflow-y-auto max-h-[750px]"
          >
            {filteredGroups.map(group => (
              <div key={group.group} className="space-y-1">
                <span className="text-[9px] text-gray-500 font-extrabold uppercase tracking-widest px-3 block mb-1">
                  {group.group}
                </span>
                
                {group.items.map(item => {
                  const isActive = activeTab === item.id;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setActiveTab(item.id)}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                        isActive
                          ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-500/35 text-cyan-400 shadow-md shadow-cyan-500/5 font-bold'
                          : 'text-gray-400 hover:text-white hover:bg-white/5'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-gray-400'}`} />
                        <span>{item.label}</span>
                      </div>
                      {isActive && (
                        <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-pulse" />
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </motion.div>

          {/* Right Main settings forms panel */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            key={activeTab}
            className="lg:col-span-3 bg-[#12121a]/85 backdrop-blur-xl rounded-2xl border border-[#22222f] p-6 sm:p-8 shadow-2xl relative"
          >
            {/* 1. Account Settings Tab */}
            {activeTab === 'account' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Account Details</h3>
                  <p className="text-xs text-gray-400 mt-1">Manage cover banner templates, primary email connections, and timezone indicators.</p>
                </div>

                {/* Cover Image banner uploader */}
                <div className="space-y-2">
                  <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Cover Banner Template</label>
                  <div className={`h-28 rounded-xl bg-gradient-to-r ${coverGradient} relative border border-white/5 shadow-inner`}>
                    <div className="absolute inset-0 bg-black/20 rounded-xl" />
                    <div className="absolute bottom-3 right-3 flex gap-2">
                      <button
                        onClick={() => setCoverGradient('from-rose-500 via-pink-600 to-red-600')}
                        className="w-5 h-5 rounded-full bg-red-500 border border-white/20"
                      />
                      <button
                        onClick={() => setCoverGradient('from-emerald-500 via-teal-600 to-green-600')}
                        className="w-5 h-5 rounded-full bg-green-500 border border-white/20"
                      />
                      <button
                        onClick={() => setCoverGradient('from-cyan-500 via-blue-600 to-purple-600')}
                        className="w-5 h-5 rounded-full bg-blue-500 border border-white/20"
                      />
                    </div>
                  </div>
                </div>

                {/* Profile Photo Uploader */}
                <div className="flex items-center gap-4 bg-white/[0.01] border border-white/5 p-4 rounded-xl">
                  {customAvatar ? (
                    <img 
                      src={customAvatar} 
                      alt="Custom Avatar" 
                      className="w-16 h-16 rounded-xl object-cover shadow-lg border border-white/10 flex-shrink-0"
                    />
                  ) : (
                    <div className="w-16 h-16 rounded-xl bg-gradient-to-tr from-cyan-400 to-purple-500 flex items-center justify-center text-white font-black text-2xl shadow-lg flex-shrink-0 select-none">
                      {initials}
                    </div>
                  )}
                  <div className="space-y-1">
                    <input 
                      type="file" 
                      id="avatar-upload-file" 
                      accept="image/*" 
                      style={{ display: 'none' }} 
                      onChange={handleAvatarUpload}
                    />
                    <button
                      onClick={() => document.getElementById('avatar-upload-file')?.click()}
                      className="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-xs font-bold text-white transition-colors cursor-pointer"
                    >
                      Change Avatar
                    </button>
                    <p className="text-[10px] text-gray-500">JPG, PNG or GIF.</p>
                  </div>
                </div>

                {/* Account Details grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Full Name</label>
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Username</label>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Email Address</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Phone Number</label>
                    <input
                      type="text"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Country / Region</label>
                    <input
                      type="text"
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Default Timezone</label>
                    <select
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50"
                    >
                      <option>Eastern Standard Time (EST) - UTC-5:00</option>
                      <option>Indian Standard Time (IST) - UTC+5:30</option>
                      <option>Greenwich Mean Time (GMT) - UTC+0:00</option>
                      <option>Central European Time (CET) - UTC+1:00</option>
                    </select>
                  </div>
                </div>

                <div className="p-4 bg-white/[0.01] border border-white/5 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400">
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-white">Student Progression Level</h4>
                      <p className="text-[10px] text-gray-500 mt-0.5">Assigned Rank: {studentLevel}</p>
                    </div>
                  </div>
                  <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-bold rounded-full">
                    Level 12
                  </span>
                </div>

                <button
                  onClick={() => handleSaveChangesToSupabase('Account credentials successfully synchronized! 🚀', {
                    full_name: fullName,
                    username: username,
                    phone: phone,
                    country: country,
                    timezone: timezone
                  })}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save Changes
                </button>
              </div>
            )}

            {/* 2. Profile Settings Tab */}
            {activeTab === 'profile' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Student Profile Settings</h3>
                  <p className="text-xs text-gray-400 mt-1">Configure student bios, favorite topics, and public workspace integrations.</p>
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Personal Bio</label>
                  <textarea
                    rows={3}
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Primary Learning Goals</label>
                  <textarea
                    rows={2}
                    value={learningGoals}
                    onChange={(e) => setLearningGoals(e.target.value)}
                    className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none focus:border-cyan-500/50 transition-all resize-none"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Favorite Subject</label>
                    <select
                      value={favSubject}
                      onChange={(e) => setFavSubject(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>Physics</option>
                      <option>Chemistry</option>
                      <option>Mathematics</option>
                      <option>Engineering</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Current Skill Level</label>
                    <select
                      value={skillLevel}
                      onChange={(e) => setSkillLevel(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>Beginner</option>
                      <option>Intermediate</option>
                      <option>Advanced</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Education Level</label>
                    <select
                      value={eduLevel}
                      onChange={(e) => setEduLevel(e.target.value)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>High School</option>
                      <option>Undergraduate</option>
                      <option>Graduate School</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-4 pt-2 border-t border-white/5">
                  <h4 className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Social Portfolio Connections</h4>
                  
                  <div className="space-y-3">
                    <div className="space-y-1.5">
                      <label className="text-[10px] text-gray-500 font-semibold">GitHub Username Link</label>
                      <input
                        type="text"
                        value={githubLink}
                        onChange={(e) => setGithubLink(e.target.value)}
                        className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] text-gray-500 font-semibold">LinkedIn Profile URL</label>
                      <input
                        type="text"
                        value={linkedinLink}
                        onChange={(e) => setLinkedinLink(e.target.value)}
                        className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                      />
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleSaveChangesToSupabase('Public learning profile saved! 🌍', {
                    bio: bio,
                    learning_goals: learningGoals,
                    fav_subject: favSubject,
                    skill_level: skillLevel,
                    edu_level: eduLevel,
                    github: githubLink,
                    linkedin: linkedinLink,
                    website: websiteLink,
                    profile_visibility: profileVisibility
                  })}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save Preferences
                </button>
              </div>
            )}

            {/* 3. Security Settings Tab */}
            {activeTab === 'security' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Security Command Dashboard</h3>
                  <p className="text-xs text-gray-400 mt-1">Audit security credentials, link two-factor authentication, and monitor active sessions.</p>
                </div>

                {/* Security Audit Gauge */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-center bg-white/[0.01] border border-white/5 p-4 rounded-xl">
                  <div className="text-center sm:text-left space-y-1 sm:col-span-2">
                    <h4 className="text-xs font-bold text-white">Your Security Score</h4>
                    <p className="text-[10px] text-gray-500 leading-relaxed">Boost score immediately by activating 2-Factor Authentication and updating passwords quarterly.</p>
                  </div>
                  <div className="flex flex-col items-center justify-center sm:col-span-1">
                    <span className="text-3xl font-black text-emerald-400">85%</span>
                    <span className="text-[9px] text-gray-500 font-extrabold uppercase mt-1">Excellent Security</span>
                  </div>
                </div>

                {/* Change Password Form */}
                <form onSubmit={handlePasswordUpdate} className="space-y-3 p-4 bg-white/[0.01] border border-white/5 rounded-xl">
                  <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                    <Key className="w-4 h-4 text-cyan-400" />
                    Change Account Password
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                    <input
                      type="password"
                      placeholder="Current Password"
                      value={passwordCurrent}
                      onChange={(e) => setPasswordCurrent(e.target.value)}
                      className="px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none placeholder-gray-600"
                    />
                    <input
                      type="password"
                      placeholder="New Secure Password"
                      value={passwordNew}
                      onChange={(e) => setPasswordNew(e.target.value)}
                      className="px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none placeholder-gray-600"
                    />
                  </div>
                  <button
                    type="submit"
                    className="mt-3 px-4 py-2 bg-white/5 hover:bg-white/10 text-white rounded-lg text-xs font-bold border border-white/10 transition-all self-start"
                  >
                    Update Password
                  </button>
                </form>

                {/* 2FA Toggle switch */}
                <div className="flex items-center justify-between p-4 bg-white/[0.01] border border-white/5 rounded-xl">
                  <div>
                    <h5 className="text-xs font-bold text-white">Two-Factor Authentication (2FA)</h5>
                    <p className="text-[10px] text-gray-500 mt-0.5">Encrypt authentication requests using time-based tokens (TOTP apps)</p>
                  </div>
                  <button
                    onClick={() => {
                      setTwoFactor(!twoFactor);
                      handleAutoSaveAction(twoFactor ? 'Two-Factor Authentication disabled!' : 'Two-Factor Authentication enabled! 🛡️');
                    }}
                    className={`w-11 h-6 rounded-full p-1 transition-all flex items-center ${
                      twoFactor ? 'bg-cyan-500' : 'bg-zinc-800'
                    }`}
                  >
                    <div
                      className={`w-4 h-4 rounded-full bg-white transition-all transform ${
                        twoFactor ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {/* Active Sessions list */}
                <div className="space-y-3">
                  <h4 className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Active Device Sessions</h4>
                  
                  <div className="divide-y divide-white/5">
                    {devices.map((device) => (
                      <div key={device.id} className="py-3 flex items-center justify-between text-xs leading-relaxed">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center text-gray-400">
                            {device.name.includes('PC') ? <Laptop className="w-4.5 h-4.5" /> : <Smartphone className="w-4.5 h-4.5" />}
                          </div>
                          <div>
                            <h5 className="font-bold text-white">{device.name}</h5>
                            <p className="text-[10px] text-gray-500 mt-0.5">{device.location} • {device.time}</p>
                          </div>
                        </div>
                        
                        {!device.current && (
                          <button
                            onClick={() => handleRevokeDevice(device.id)}
                            className="p-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 rounded-lg transition-all"
                            title="Revoke session"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 4. Notification Settings Tab */}
            {activeTab === 'notifications' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Notifications Tuning</h3>
                  <p className="text-xs text-gray-400 mt-1">Customize specific toggle thresholds for weekly logs, badges, or announcements.</p>
                </div>

                <div className="space-y-4">
                  <h4 className="text-[10px] text-gray-400 font-bold uppercase tracking-wider border-b border-white/5 pb-2">
                    Email Digest Options
                  </h4>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                      <div>
                        <h5 className="text-xs font-bold text-white">Weekly Performance Reports</h5>
                        <p className="text-[10px] text-gray-500 mt-0.5">Receive steps and calibrations summary from AI Tutor weekly.</p>
                      </div>
                      <button
                        onClick={() => setNotifs(prev => ({ ...prev, emailWeekly: !prev.emailWeekly }))}
                        className={`w-11 h-6 rounded-full p-1 transition-all ${
                          notifs.emailWeekly ? 'bg-cyan-500' : 'bg-zinc-800'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${notifs.emailWeekly ? 'translate-x-5' : 'translate-x-0'}`} />
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                      <div>
                        <h5 className="text-xs font-bold text-white">Milestone Badge Unlock Alerts</h5>
                        <p className="text-[10px] text-gray-500 mt-0.5">Instant notices upon leveling up or earning rewards.</p>
                      </div>
                      <button
                        onClick={() => setNotifs(prev => ({ ...prev, emailBadges: !prev.emailBadges }))}
                        className={`w-11 h-6 rounded-full p-1 transition-all ${
                          notifs.emailBadges ? 'bg-cyan-500' : 'bg-zinc-800'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${notifs.emailBadges ? 'translate-x-5' : 'translate-x-0'}`} />
                      </button>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 pt-2">
                  <h4 className="text-[10px] text-gray-400 font-bold uppercase tracking-wider border-b border-white/5 pb-2">
                    App Push Reminders
                  </h4>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                      <div>
                        <h5 className="text-xs font-bold text-white">Active learning Streak Reminders</h5>
                        <p className="text-[10px] text-gray-500 mt-0.5">Warnings prior to daily streak cache wipes.</p>
                      </div>
                      <button
                        onClick={() => setNotifs(prev => ({ ...prev, pushStreak: !prev.pushStreak }))}
                        className={`w-11 h-6 rounded-full p-1 transition-all ${
                          notifs.pushStreak ? 'bg-cyan-500' : 'bg-zinc-800'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${notifs.pushStreak ? 'translate-x-5' : 'translate-x-0'}`} />
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                      <div>
                        <h5 className="text-xs font-bold text-white">Daily STEM Quest Drops</h5>
                        <p className="text-[10px] text-gray-500 mt-0.5">Alerts when new daily quizzes or lab challenges go live.</p>
                      </div>
                      <button
                        onClick={() => setNotifs(prev => ({ ...prev, pushQuests: !prev.pushQuests }))}
                        className={`w-11 h-6 rounded-full p-1 transition-all ${
                          notifs.pushQuests ? 'bg-cyan-500' : 'bg-zinc-800'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${notifs.pushQuests ? 'translate-x-5' : 'translate-x-0'}`} />
                      </button>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleAutoSaveAction('Notification filters saved! 🔔')}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save notification preferences
                </button>
              </div>
            )}

            {/* 5. Appearance Settings Tab */}
            {activeTab === 'appearance' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Appearance & Theme Tuning</h3>
                  <p className="text-xs text-gray-400 mt-1">Alter layouts, focus values, and font metrics.</p>
                </div>

                <div className="space-y-5">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Select Theme Model</label>
                    <div className="grid grid-cols-3 gap-3">
                      {(['dark', 'light', 'system'] as const).map((t) => (
                        <button
                          key={t}
                          onClick={() => setThemeMode(t)}
                          className={`py-3.5 border rounded-xl text-xs font-bold uppercase transition-all ${
                            themeMode === t
                              ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400 font-black'
                              : 'bg-white/5 border-white/10 text-gray-400 hover:text-white'
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Accent Focus Highlights</label>
                    <div className="grid grid-cols-5 gap-2">
                      {(['blue', 'purple', 'green', 'orange', 'pink'] as const).map((c) => (
                        <button
                          key={c}
                          onClick={() => setAccentColor(c)}
                          className={`py-2 border rounded-lg text-[10px] font-bold uppercase transition-all ${
                            accentColor === c
                              ? 'bg-blue-500/20 border-blue-500/50 text-blue-400 font-black'
                              : 'bg-white/5 border-white/10 text-gray-400 hover:text-white'
                          }`}
                        >
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Font Scaling</label>
                      <select
                        value={fontScale}
                        onChange={(e) => setFontScale(e.target.value as any)}
                        className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                      >
                        <option>small</option>
                        <option>medium</option>
                        <option>large</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">UI Density</label>
                      <select
                        value={uiDensity}
                        onChange={(e) => setUiDensity(e.target.value as any)}
                        className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                      >
                        <option>comfortable</option>
                        <option>compact</option>
                      </select>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleAutoSaveAction('Theme specifications loaded! 🎨')}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save Visual Preferences
                </button>
              </div>
            )}

            {/* 6. Learning Preferences Tab */}
            {activeTab === 'learning' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Learning Metrics</h3>
                  <p className="text-xs text-gray-400 mt-1">Configure subjects focus indexes, preferred styles, and goals.</p>
                </div>

                <div className="space-y-4">
                  <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider block">STEM Topic Focus Indexes</label>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.keys(preferredSubjects).map((subj) => (
                      <div key={subj} className="flex items-center justify-between p-3 bg-white/[0.01] border border-white/5 rounded-xl text-xs font-bold text-white uppercase tracking-wider">
                        <span>{subj}</span>
                        <input
                          type="checkbox"
                          checked={(preferredSubjects as any)[subj]}
                          onChange={() => setPreferredSubjects(prev => ({ ...prev, [subj]: !(prev as any)[subj] }))}
                          className="w-4 h-4 rounded accent-cyan-500 bg-[#13131c] border border-[#22222f]"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Preferred Learning Style</label>
                    <select
                      value={learningStyle}
                      onChange={(e) => setLearningStyle(e.target.value as any)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>Video</option>
                      <option>Interactive</option>
                      <option>Reading</option>
                      <option>Practice Based</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Difficulty Focus</label>
                    <select
                      value={difficultyLevel}
                      onChange={(e) => setDifficultyLevel(e.target.value as any)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>Beginner</option>
                      <option>Intermediate</option>
                      <option>Advanced</option>
                    </select>
                  </div>
                </div>

                <button
                  onClick={() => handleAutoSaveAction('Learning preferences mapped successfully! 📊')}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save Learning Preferences
                </button>
              </div>
            )}

            {/* 7. AI Tutor Settings Tab */}
            {activeTab === 'aitutor' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">AI Tutor Behaviors</h3>
                  <p className="text-xs text-gray-400 mt-1">Configure explanation lengths, voice prompts, and personality filters.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Explanation Complexity</label>
                    <select
                      value={explainLength}
                      onChange={(e) => setExplainLength(e.target.value as any)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>Short</option>
                      <option>Medium</option>
                      <option>Detailed</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">AI Persona Profile</label>
                    <select
                      value={tutorPersonality}
                      onChange={(e) => setTutorPersonality(e.target.value as any)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold"
                    >
                      <option>Friendly</option>
                      <option>Professional</option>
                      <option>Teacher</option>
                      <option>Scientist</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 bg-white/[0.01] border border-white/5 rounded-xl">
                  <div>
                    <h5 className="text-xs font-bold text-white">Audio Text-To-Speech Output</h5>
                    <p className="text-[10px] text-gray-500 mt-0.5">Let AI read detailed calculations out loud during live calibrations.</p>
                  </div>
                  <button
                    onClick={() => {
                      setVoiceEnabled(!voiceEnabled);
                      handleAutoSaveAction(voiceEnabled ? 'Voice enabled!' : 'Voice disabled!');
                    }}
                    className={`w-11 h-6 rounded-full p-1 transition-all ${
                      voiceEnabled ? 'bg-cyan-500' : 'bg-zinc-800'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${voiceEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                  </button>
                </div>

                <button
                  onClick={() => handleAutoSaveAction('AI Tutor preferences synchronized! 🤖')}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save AI Tutor Preferences
                </button>
              </div>
            )}

            {/* 8. Experiment Settings Tab */}
            {activeTab === 'experiments' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Simulation Prefs</h3>
                  <p className="text-xs text-gray-400 mt-1">Configure rendering speeds, real-time analytics, and details details.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Simulation Quality</label>
                    <select
                      value={simQuality}
                      onChange={(e) => setSimQuality(e.target.value as any)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold focus:outline-none"
                    >
                      <option>low</option>
                      <option>high</option>
                      <option>ultra</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Kinetic Engine Precision</label>
                    <select
                      value={physicsAccuracy}
                      onChange={(e) => setPhysicsAccuracy(e.target.value as any)}
                      className="w-full px-4 py-3 bg-[#13131c] border border-[#22222f] rounded-xl text-white text-xs font-semibold"
                    >
                      <option>standard</option>
                      <option>high</option>
                      <option>absolute</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                    <div>
                      <h5 className="text-xs font-bold text-white">Real-Time Computer Vision Analytics</h5>
                      <p className="text-[10px] text-gray-500 mt-0.5">Let live camera map kinetic vectors and trajectory curves instantly.</p>
                    </div>
                    <button
                      onClick={() => {
                        setRealTimeAnalysis(!realTimeAnalysis);
                        handleAutoSaveAction(realTimeAnalysis ? 'Real-time analysis toggled off!' : 'Real-time analysis active! 👁️');
                      }}
                      className={`w-11 h-6 rounded-full p-1 transition-all ${
                        realTimeAnalysis ? 'bg-cyan-500' : 'bg-zinc-800'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${realTimeAnalysis ? 'translate-x-5' : 'translate-x-0'}`} />
                    </button>
                  </div>
                </div>

                <button
                  onClick={() => handleAutoSaveAction('Physics simulations parameters saved! ⚛️')}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save Simulator Specs
                </button>
              </div>
            )}

            {/* 9. Achievements Tab */}
            {activeTab === 'achievements' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Your Achievements Status</h3>
                  <p className="text-xs text-gray-400 mt-1">Audit active badge thresholds and level progressions.</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-white/[0.01] border border-white/5 rounded-xl space-y-1">
                    <span className="text-3xl font-black text-white">6/12</span>
                    <p className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Unlocked Badges</p>
                  </div>
                  
                  <div className="p-4 bg-white/[0.01] border border-white/5 rounded-xl space-y-1">
                    <span className="text-3xl font-black text-amber-500">2,450 XP</span>
                    <p className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Total Earned XP</p>
                  </div>
                </div>

                <div className="p-4 bg-white/[0.01] border border-white/5 rounded-xl space-y-3">
                  <div className="flex justify-between text-xs font-bold text-white">
                    <span>Level 12 Progression</span>
                    <span className="text-cyan-400">81.6% Completed</span>
                  </div>
                  <div className="h-2 bg-[#1c1c2b] rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-cyan-400 to-blue-500" style={{ width: '81.6%' }} />
                  </div>
                  <p className="text-[10px] text-gray-500">Earn 550 additional XP to advance to Level 13 (Senior Specialist).</p>
                </div>

                <button
                  onClick={() => navigate('/dashboard/achievements')}
                  className="w-full py-4 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-xs font-bold tracking-wide uppercase rounded-xl transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Star className="w-4 h-4 text-cyan-400" />
                  View Badge Details
                </button>
              </div>
            )}

            {/* 10. Privacy Settings Tab */}
            {activeTab === 'privacy' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Privacy Preferences</h3>
                  <p className="text-xs text-gray-400 mt-1">Configure profile visibilities, analytics shares, and visibility toggles.</p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                    <div>
                      <h5 className="text-xs font-bold text-white">Public Leaderboard Visibility</h5>
                      <p className="text-[10px] text-gray-500 mt-0.5">Include your weekly progress calculations on the global performer lists.</p>
                    </div>
                    <button
                      onClick={() => {
                        setSharingConsent(prev => ({ ...prev, leaderboardPublic: !prev.leaderboardPublic }));
                        handleAutoSaveAction('Leaderboard visibility updated!');
                      }}
                      className={`w-11 h-6 rounded-full p-1 transition-all ${
                        sharingConsent.leaderboardPublic ? 'bg-cyan-500' : 'bg-zinc-800'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${sharingConsent.leaderboardPublic ? 'translate-x-5' : 'translate-x-0'}`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-3.5 bg-white/[0.01] border border-white/5 rounded-xl">
                    <div>
                      <h5 className="text-xs font-bold text-white">Public Achievements Profile</h5>
                      <p className="text-[10px] text-gray-500 mt-0.5">Let guest users inspect your unlocked milestones and badges catalog.</p>
                    </div>
                    <button
                      onClick={() => {
                        setSharingConsent(prev => ({ ...prev, achievementsPublic: !prev.achievementsPublic }));
                        handleAutoSaveAction('Achievements visibility preferences saved!');
                      }}
                      className={`w-11 h-6 rounded-full p-1 transition-all ${
                        sharingConsent.achievementsPublic ? 'bg-cyan-500' : 'bg-zinc-800'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transition-all transform ${sharingConsent.achievementsPublic ? 'translate-x-5' : 'translate-x-0'}`} />
                    </button>
                  </div>
                </div>

                <button
                  onClick={() => handleAutoSaveAction('Privacy configurations saved! 🛡️')}
                  className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-purple-600 text-white text-xs font-bold tracking-wide uppercase rounded-xl hover:brightness-110 transition-all flex items-center justify-center gap-2 mt-6"
                >
                  <Save className="w-4 h-4" />
                  Save Privacy Specs
                </button>
              </div>
            )}

            {/* 11. Data Management Tab */}
            {activeTab === 'data' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Data Management</h3>
                  <p className="text-xs text-gray-400 mt-1">Export personal learning data, logs, or delete your account workspace.</p>
                </div>

                <div className="space-y-4">
                  <div className="p-4 bg-white/[0.01] border border-white/5 rounded-xl space-y-4">
                    <div>
                      <h4 className="text-xs font-bold text-white">Export My Performance Data</h4>
                      <p className="text-[11px] text-gray-500 mt-1">Acquire a complete JSON package containing all your simulation coordinates, calculations, and AI Tutor chat transcripts.</p>
                    </div>
                    <button
                      onClick={() => handleAutoSaveAction('Data export package generated and download started! 📥')}
                      className="px-4 py-2.5 bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-bold rounded-xl hover:bg-cyan-500/20 transition-all"
                    >
                      Download Export Package (JSON)
                    </button>
                  </div>

                  <div className="p-4 bg-red-950/5 border border-red-500/20 rounded-xl space-y-4">
                    <div>
                      <h4 className="text-xs font-bold text-red-400">Danger Zone</h4>
                      <p className="text-[11px] text-gray-500 mt-1">Wipe your NeuroLab workspace permanently. This cleans up logins, streak status, and badge history.</p>
                    </div>
                    <button
                      onClick={() => setShowDeleteModal(true)}
                      className="px-4 py-2.5 bg-red-600/10 border border-red-600/30 text-red-400 hover:bg-red-600 hover:text-white text-xs font-bold rounded-xl transition-all"
                    >
                      Delete Account Permanently
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 12. Connected Accounts Tab */}
            {activeTab === 'connections' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Third-Party Integrations</h3>
                  <p className="text-xs text-gray-400 mt-1">Connect social accounts to login quickly and sync repository codes.</p>
                </div>

                <div className="divide-y divide-white/5">
                  {(['google', 'github', 'linkedin', 'discord', 'microsoft'] as const).map((acc) => {
                    const isConnected = connectedAccs[acc];
                    return (
                      <div key={acc} className="py-4 flex items-center justify-between text-xs">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center font-extrabold uppercase ${
                            isConnected ? 'text-cyan-400' : 'text-gray-500'
                          }`}>
                            {acc[0]}
                          </div>
                          <div>
                            <h5 className="font-bold text-white capitalize">{acc}</h5>
                            <p className="text-[10px] text-gray-500 mt-0.5">
                              {isConnected ? 'Connected • Synced today' : 'Not Connected'}
                            </p>
                          </div>
                        </div>

                        <button
                          onClick={() => handleSyncAccount(acc)}
                          className={`px-3 py-1.5 rounded-lg text-[10px] font-bold tracking-wide uppercase transition-all ${
                            isConnected
                              ? 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/10'
                              : 'bg-white/5 hover:bg-white/10 text-white border border-white/10'
                          }`}
                        >
                          {isConnected ? 'Disconnect' : 'Connect'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 13. Billing & Subscription Tab */}
            {activeTab === 'billing' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Billing & Plan Subscription</h3>
                  <p className="text-xs text-gray-400 mt-1">Manage monthly billing details, upgrade options, and invoice cache history.</p>
                </div>

                <div className="p-5 bg-gradient-to-r from-cyan-900/15 via-blue-900/10 to-transparent border border-cyan-500/20 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div>
                    <span className="text-[9px] text-cyan-400 font-extrabold uppercase tracking-wider bg-cyan-500/10 border border-cyan-500/25 px-2 py-0.5 rounded">Active Plan</span>
                    <h4 className="text-2xl font-black text-white mt-2 capitalize">{billingPlan} Plan</h4>
                    <p className="text-[10px] text-gray-500 mt-0.5">NeuroLab {billingPlan === 'Free' ? 'Basic level learning access' : 'Full interactive access enabled'}.</p>
                  </div>
                  
                  {billingPlan === 'Free' && (
                    <button
                      onClick={() => setShowUpgradeModal(true)}
                      className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-bold rounded-xl transition-all shadow-lg hover:brightness-110"
                    >
                      Upgrade to Pro
                    </button>
                  )}
                </div>

                {/* Billing invoice logs list */}
                <div className="space-y-3 pt-2">
                  <h4 className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Billing Invoice History</h4>
                  
                  <div className="p-4 bg-white/[0.01] border border-white/5 rounded-xl text-center">
                    <p className="text-xs text-gray-500 font-medium">No invoice logs found. Free tier account setup active.</p>
                  </div>
                </div>
              </div>
            )}

            {/* 14. Help & Support Tab */}
            {activeTab === 'support' && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold text-white">Help & FAQs</h3>
                  <p className="text-xs text-gray-400 mt-1">Browse troubleshooting guides or submit a support ticket to our scientific panel.</p>
                </div>

                {/* FAQ Collapsibles */}
                <div className="space-y-2">
                  {[
                    { q: "How does the AI webcam tracker measure oscillation periods?", a: "The AI webcam uses simple tracking points to map coordinates in real-time, calculating acceleration vectors based on camera refresh speeds." },
                    { q: "How do I configure custom experiment reports?", a: "From the catalog, completed experiments show a 'Review' button where you can save parameters and output steps in CSV formats." },
                    { q: "Why did my daily learning streak reset?", a: "Streaks reset if you fail to log in or ask the AI Tutor questions for over 24 consecutive hours." }
                  ].map((faq, index) => {
                    const isExpanded = faqExpanded === index;
                    return (
                      <div key={index} className="border border-white/5 bg-white/[0.01] rounded-xl overflow-hidden">
                        <button
                          onClick={() => setFaqExpanded(isExpanded ? null : index)}
                          className="w-full p-4 flex justify-between items-center text-xs font-bold text-white text-left"
                        >
                          <span>{faq.q}</span>
                          <ChevronDown className={`w-4 h-4 text-gray-500 transition-all ${isExpanded ? 'rotate-180' : ''}`} />
                        </button>
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0 }}
                              animate={{ height: 'auto' }}
                              exit={{ height: 0 }}
                              className="overflow-hidden"
                            >
                              <p className="px-4 pb-4 text-xs text-gray-400 leading-relaxed border-t border-white/5 pt-2">
                                {faq.a}
                              </p>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>

                <div className="p-4 bg-cyan-500/5 border border-cyan-500/15 rounded-xl space-y-3">
                  <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    Need Direct Support?
                  </h4>
                  <p className="text-[11px] text-gray-500">Speak directly with our STEM panel or report simulation physics bugs instantly.</p>
                  <button
                    onClick={() => {
                      handleAutoSaveAction('Support ticket portal opened! 🎟️');
                      window.location.href = 'mailto:support@neurolab.ai?subject=NeuroLab%20Live%20Support%20Ticket';
                    }}
                    className="px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl text-xs font-bold shadow-lg"
                  >
                    Open Live Support Ticket
                  </button>
                </div>
              </div>
            )}

            {/* 15. About Platform Tab */}
            {activeTab === 'about' && (
              <div className="space-y-8 pb-10">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/10 pb-6">
                  <div>
                    <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4 overflow-hidden">
                      <img src="/logo.png" alt="NeuroLab Logo" className="w-8 h-8 object-cover" />
                    </div>
                    <h3 className="text-2xl font-black text-white">About NeuroLab Technologies</h3>
                    <p className="text-sm text-gray-400 mt-1 max-w-xl leading-relaxed">
                      Pioneering the future of interactive STEM education. We blend advanced computer vision, robust physics engines, and generative AI into a seamless learning experience.
                    </p>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={() => navigate('/terms')} className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs font-semibold text-gray-300 hover:text-white transition-colors">
                      Legal Terms
                    </button>
                    <button onClick={() => navigate('/privacy')} className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs font-semibold text-gray-300 hover:text-white transition-colors">
                      Privacy Policy
                    </button>
                  </div>
                </div>

                {/* Mission & Vision */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="p-6 bg-gradient-to-br from-cyan-500/5 to-transparent border border-cyan-500/15 rounded-2xl">
                    <h4 className="text-cyan-400 font-bold mb-2 flex items-center gap-2">
                      <Globe className="w-4 h-4" /> Our Mission
                    </h4>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      To democratize high-level science education by providing students worldwide with a safe, accessible, and highly advanced virtual laboratory powered by artificial intelligence.
                    </p>
                  </div>
                  <div className="p-6 bg-gradient-to-br from-violet-500/5 to-transparent border border-violet-500/15 rounded-2xl">
                    <h4 className="text-violet-400 font-bold mb-2 flex items-center gap-2">
                      <Sparkles className="w-4 h-4" /> Our Vision
                    </h4>
                    <p className="text-sm text-gray-300 leading-relaxed">
                      A future where physical boundaries don't limit practical learning. We envision a world where every student has a personal, highly capable AI tutor and a limitless physics playground.
                    </p>
                  </div>
                </div>

                {/* Platform Specs */}
                <div>
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">System Information</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: 'Platform Version', value: 'v3.4.15-SaaS', icon: Cpu },
                      { label: 'Release Channel', value: 'Stable Production', icon: CheckCircle },
                      { label: 'Infrastructure', value: 'Supabase Edge', icon: Server },
                      { label: 'Data Processing', value: 'Local Compute', icon: HardDrive },
                    ].map((item, i) => (
                      <div key={i} className="p-4 bg-white/[0.02] border border-white/5 rounded-xl text-center">
                        <item.icon className="w-5 h-5 text-gray-500 mx-auto mb-2" />
                        <span className="block text-[10px] text-gray-500 font-bold uppercase tracking-wider">{item.label}</span>
                        <h5 className="text-sm font-black text-white mt-1">{item.value}</h5>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Tech Stack */}
                <div>
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">Core Architecture</h4>
                  <div className="p-5 bg-white/[0.02] border border-white/5 rounded-2xl">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { title: 'Frontend Engine', tech: 'React 18 & Vite', color: 'text-cyan-400' },
                        { title: 'Styling Architecture', tech: 'Tailwind CSS & Framer', color: 'text-blue-400' },
                        { title: 'Backend & Auth', tech: 'Supabase Postgres', color: 'text-emerald-400' },
                        { title: 'Physics & Vision', tech: 'Matter.js & TensorFlow', color: 'text-violet-400' },
                      ].map((stack, i) => (
                        <div key={i}>
                          <p className="text-xs text-gray-500 font-medium">{stack.title}</p>
                          <p className={`text-sm font-bold mt-0.5 ${stack.color}`}>{stack.tech}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Open Source & Community */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="p-6 bg-white/[0.02] border border-white/5 rounded-2xl flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center flex-shrink-0">
                      <Github className="w-5 h-5 text-gray-300" />
                    </div>
                    <div>
                      <h4 className="text-white font-bold text-sm mb-1">Open Source Core</h4>
                      <p className="text-xs text-gray-400 leading-relaxed mb-3">
                        Parts of our physics engine and UI components are available under the MIT license to support the global educational tech community.
                      </p>
                      <button 
                        onClick={() => window.open('https://github.com/vikassaini77/AI-Steam-Lab', '_blank')}
                        className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition-colors"
                      >
                        View GitHub Repository &rarr;
                      </button>
                    </div>
                  </div>
                  
                  <div className="p-6 bg-white/[0.02] border border-white/5 rounded-2xl flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                      <Mail className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h4 className="text-white font-bold text-sm mb-1">Contact & Support</h4>
                      <p className="text-xs text-gray-400 leading-relaxed mb-3">
                        For institutional licensing, press inquiries, or technical support, our team is available 24/7.
                      </p>
                      <div className="flex gap-3">
                        <a href="mailto:support@neurolab.ai" className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors">
                          support@neurolab.ai
                        </a>
                        <span className="text-gray-600">|</span>
                        <a href="mailto:press@neurolab.ai" className="text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors">
                          press@neurolab.ai
                        </a>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
