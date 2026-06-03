import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect, useRef } from 'react';
import {
  Home,
  FlaskConical,
  Bot,
  Atom,
  Trophy,
  Menu,
  X,
  Sparkles,
  ChevronRight,
  Search,
  Bell,
  Settings,
  LogOut,
  Shield,
  History,
} from 'lucide-react';
import { Link, useLocation, Outlet, useNavigate } from 'react-router-dom';
import { supabase } from '../../lib/supabase';
import {
  subscribeNotifications,
  subscribePopups,
  markAllRead,
  clearAll,
  Notification,
} from '../../lib/notificationStore';

const navItems = [
  { icon: Home, label: 'Home', path: '/dashboard' },
  { icon: FlaskConical, label: 'Experiments', path: '/dashboard/experiments' },
  { icon: History, label: 'Lab History', path: '/dashboard/history' },
  { icon: Bot, label: 'AI Tutor', path: '/dashboard/tutor' },
  { icon: Atom, label: 'Physics Lab', path: '/dashboard/physics' },
  { icon: Trophy, label: 'Challenges', path: '/dashboard/challenges' },
  { icon: Sparkles, label: 'Achievements', path: '/dashboard/achievements' },
  { icon: Shield, label: 'Security', path: '/dashboard/security' },
];

/* ── XP Popup Toast ────────────────────────────────── */
function XpPopup({ notification, onDismiss }: { notification: Notification; onDismiss: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 4500);
    return () => clearTimeout(t);
  }, [onDismiss]);

  const icon =
    notification.type === 'xp' ? '⚡' :
    notification.type === 'badge' ? '🏆' :
    notification.type === 'streak' ? '🔥' : '🔔';

  const borderColor =
    notification.type === 'xp' ? 'border-cyan-500/40' :
    notification.type === 'badge' ? 'border-yellow-500/40' :
    notification.type === 'streak' ? 'border-orange-500/40' : 'border-white/20';

  const glowColor =
    notification.type === 'xp' ? 'shadow-cyan-500/20' :
    notification.type === 'badge' ? 'shadow-yellow-500/20' :
    notification.type === 'streak' ? 'shadow-orange-500/20' : 'shadow-white/10';

  return (
    <motion.div
      initial={{ opacity: 0, x: 120, scale: 0.85 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 120, scale: 0.85 }}
      transition={{ type: 'spring', stiffness: 280, damping: 22 }}
      className={`flex items-start gap-3 bg-[#0d0d20]/95 backdrop-blur-xl border ${borderColor} rounded-2xl px-4 py-3.5 shadow-2xl ${glowColor} max-w-sm w-full cursor-pointer`}
      onClick={onDismiss}
    >
      {/* Animated icon */}
      <motion.div
        animate={{ scale: [1, 1.25, 1] }}
        transition={{ duration: 0.5, repeat: 2 }}
        className="text-2xl flex-shrink-0 mt-0.5"
      >
        {icon}
      </motion.div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-white leading-relaxed">{notification.text}</p>
        <p className="text-[10px] text-gray-500 mt-1">Tap to dismiss</p>
      </div>
      {/* Progress bar */}
      <motion.div
        className="absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-cyan-400 to-blue-500 rounded-b-2xl"
        initial={{ width: '100%' }}
        animate={{ width: '0%' }}
        transition={{ duration: 4.5, ease: 'linear' }}
      />
    </motion.div>
  );
}

/* ── Avatar component — reads custom_avatar from localStorage ── */
function UserAvatar({ className = '', textClass = '' }: { className?: string; textClass?: string }) {
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null);
  const [initials, setInitials] = useState('N');

  const refresh = () => {
    try {
      const stored = localStorage.getItem('neurolab_session');
      if (stored) {
        const s = JSON.parse(stored);
        const avatar = s?.user?.user_metadata?.custom_avatar;
        const name: string = s?.user?.user_metadata?.full_name || s?.user?.email || 'N';
        const parts = name.trim().split(/\s+/);
        setInitials(parts.map((p: string) => p[0]).join('').toUpperCase().substring(0, 2));
        setAvatarSrc(avatar || null);
        return;
      }
    } catch { /* ignore */ }
    setAvatarSrc(null);
  };

  useEffect(() => {
    refresh();
    // Re-read whenever avatar changes from settings page
    const handler = () => refresh();
    window.addEventListener('neurolab-avatar-updated', handler);
    // Also poll every 2 s in case of localStorage changes
    const interval = setInterval(refresh, 2000);
    return () => {
      window.removeEventListener('neurolab-avatar-updated', handler);
      clearInterval(interval);
    };
  }, []);

  if (avatarSrc) {
    return (
      <img
        src={avatarSrc}
        alt="Avatar"
        className={`object-cover ${className}`}
      />
    );
  }

  return (
    <div className={`flex items-center justify-center bg-gradient-to-tr from-cyan-500 to-blue-600 text-white font-extrabold ${textClass} ${className}`}>
      {initials}
    </div>
  );
}

export default function DashboardLayout({ children }: { children?: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  const [isDesktop, setIsDesktop] = useState(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true);
  const [globalSearch, setGlobalSearch] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [popupQueue, setPopupQueue] = useState<Notification[]>([]);
  const popupRef = useRef<Notification[]>([]);
  popupRef.current = popupQueue;

  const unreadCount = notifications.filter((n) => !n.read).length;

  // Subscribe to notification store
  useEffect(() => {
    const unsub = subscribeNotifications(setNotifications);
    const unsubPopup = subscribePopups((n) => {
      setPopupQueue((prev) => [...prev, n]);
    });
    return () => { unsub(); unsubPopup(); };
  }, []);

  const dismissPopup = (id: number) => {
    setPopupQueue((prev) => prev.filter((n) => n.id !== id));
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    setGlobalSearch('');
  }, [location.pathname]);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    navigate('/');
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setGlobalSearch(val);
    window.dispatchEvent(new CustomEvent('dashboard-search', { detail: val }));
  };

  const getHeaderInfo = () => {
    const path = location.pathname;
    if (path === '/dashboard') return { title: 'AI Laboratory', subtitle: 'Real-time STEM experiments powered by AI' };
    if (path.startsWith('/dashboard/experiments')) return { title: 'Experiments', subtitle: 'Explore hands-on STEM experiments' };
    if (path.startsWith('/dashboard/history')) return { title: 'Lab History', subtitle: 'Browse saved telemetry and AI roundtable debates' };
    if (path.startsWith('/dashboard/tutor')) return { title: 'AI Tutor', subtitle: 'Your personal AI learning assistant' };
    if (path.startsWith('/dashboard/physics')) return { title: 'Physics Lab', subtitle: 'Interactive physics simulations' };
    if (path.startsWith('/dashboard/challenges')) return { title: 'Challenges', subtitle: 'Complete quests to level up your rank' };
    if (path.startsWith('/dashboard/achievements')) return { title: 'Achievements', subtitle: 'Track your progress and badges' };
    if (path.startsWith('/dashboard/profile')) return { title: 'Settings', subtitle: 'Customize your experience' };
    if (path.startsWith('/dashboard/security')) return { title: 'Cyber Security Center', subtitle: 'Production-grade session safety controls' };
    return { title: 'AI Laboratory', subtitle: 'Real-time STEM experiments powered by AI' };
  };

  const headerInfo = getHeaderInfo();

  return (
    <div className="min-h-screen bg-[#0a0a1a] relative overflow-hidden">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-[#0a0a1a] via-[#0d0d25] to-[#0a0a1a] z-0" />
      <div className="fixed top-0 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* ── Real-time XP/Badge Popup Stack (bottom-right) ── */}
      <div className="fixed bottom-6 right-6 z-[200] flex flex-col gap-3 items-end pointer-events-none">
        <AnimatePresence>
          {popupQueue.map((n) => (
            <div key={n.id} className="pointer-events-auto relative">
              <XpPopup notification={n} onDismiss={() => dismissPopup(n.id)} />
            </div>
          ))}
        </AnimatePresence>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{ x: isDesktop ? 0 : (sidebarOpen ? 0 : '-100%') }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="fixed top-0 left-0 h-full w-72 bg-[#0d0d20]/95 backdrop-blur-xl border-r border-white/10 z-50 lg:translate-x-0 lg:w-80 flex flex-col justify-between"
      >
        <div className="flex flex-col flex-1 overflow-y-auto">
          {/* Logo */}
          <div className="flex items-center justify-between p-6 border-b border-white/10">
            <Link to="/" className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <span className="text-2xl font-bold text-white">N</span>
              </div>
              <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-400">
                NeuroLab
              </span>
            </Link>
            <button onClick={() => setSidebarOpen(false)} className="lg:hidden text-gray-400 hover:text-white transition-colors">
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onMouseEnter={() => setHoveredItem(item.path)}
                  onMouseLeave={() => setHoveredItem(null)}
                  onClick={() => setSidebarOpen(false)}
                  className="relative block"
                >
                  <motion.div
                    className={`relative flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-300 ${
                      isActive
                        ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 text-white'
                        : 'text-gray-300 hover:bg-white/5 hover:text-white'
                    }`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="activeIndicator"
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-gradient-to-b from-cyan-400 to-blue-500 rounded-r-full"
                      />
                    )}
                    <item.icon className={`w-5 h-5 ${isActive ? 'text-cyan-400' : 'text-gray-400'}`} />
                    <span className="font-medium">{item.label}</span>
                    {hoveredItem === item.path && !isActive && (
                      <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="absolute right-3">
                        <ChevronRight className="w-4 h-4 text-gray-500" />
                      </motion.div>
                    )}
                  </motion.div>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom Controls */}
        <div className="p-4 border-t border-white/10 space-y-1.5 bg-black/10">
          <Link to="/dashboard/profile" className="block" onClick={() => setSidebarOpen(false)}>
            <motion.div
              whileHover={{ scale: 1.02 }}
              className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-300 ${
                location.pathname === '/dashboard/profile'
                  ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 text-white font-bold'
                  : 'text-gray-300 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Settings className={`w-5 h-5 ${location.pathname === '/dashboard/profile' ? 'text-cyan-400' : 'text-gray-400'}`} />
              <span className="font-medium">Settings</span>
            </motion.div>
          </Link>
          <button onClick={handleSignOut} className="w-full block text-left">
            <motion.div
              whileHover={{ scale: 1.02 }}
              className="flex items-center gap-4 px-4 py-3 rounded-xl text-gray-300 hover:bg-red-500/10 hover:text-red-400 transition-all duration-300 cursor-pointer"
            >
              <LogOut className="w-5 h-5 text-gray-400" />
              <span className="font-medium">Sign Out</span>
            </motion.div>
          </button>
        </div>
      </motion.aside>

      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-[#0d0d20]/95 backdrop-blur-xl border-b border-white/10 z-30 flex items-center justify-between px-4">
        <button onClick={() => setSidebarOpen(true)} className="text-gray-400 hover:text-white">
          <Menu className="w-6 h-6" />
        </button>
        <span className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 flex items-center justify-center">
            <span className="text-sm font-bold text-white">N</span>
          </div>
          <span className="font-semibold text-white">NeuroLab</span>
        </span>
        <Link to="/dashboard/profile">
          <UserAvatar className="w-8 h-8 rounded-full border border-white/10" textClass="text-xs" />
        </Link>
      </div>

      {/* Main content */}
      <main className="lg:ml-80 min-h-screen relative z-10 p-6 lg:p-8 space-y-6 pt-20 lg:pt-8">
        {/* Global Header Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-white/5 pb-6">
          <div>
            <h1 className="text-3xl font-extrabold text-white tracking-wide">{headerInfo.title}</h1>
            <p className="text-xs text-gray-400 mt-1">{headerInfo.subtitle}</p>
          </div>

          <div className="flex items-center gap-4 w-full sm:w-auto self-end sm:self-auto justify-end">
            {/* Search */}
            <div className="relative w-full sm:w-64 max-w-xs">
              <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search..."
                value={globalSearch}
                onChange={handleSearchChange}
                className="w-full pl-9 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20 transition-all"
              />
            </div>

            {/* Notification Bell */}
            <div className="relative">
              <button
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="relative w-10 h-10 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl flex items-center justify-center text-gray-400 hover:text-white transition-all flex-shrink-0"
              >
                <Bell className="w-4 h-4" />
                {unreadCount > 0 && (
                  <motion.span
                    initial={{ scale: 0 }} animate={{ scale: 1 }}
                    className="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-gradient-to-r from-cyan-500 to-blue-600 rounded-full text-[9px] font-black text-white flex items-center justify-center px-1 shadow-lg shadow-cyan-500/30"
                  >
                    {unreadCount}
                  </motion.span>
                )}
              </button>

              <AnimatePresence>
                {notificationsOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setNotificationsOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, y: 10, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 5, scale: 0.95 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 mt-2 w-80 sm:w-96 bg-[#0d0d20]/95 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl p-4 space-y-3 z-50 text-left"
                    >
                      <div className="flex justify-between items-center border-b border-white/5 pb-2">
                        <div className="flex items-center gap-2">
                          <Bell className="w-3.5 h-3.5 text-cyan-400" />
                          <span className="text-xs font-bold text-white uppercase tracking-wider">Notifications</span>
                          {unreadCount > 0 && (
                            <span className="px-1.5 py-0.5 bg-cyan-500/20 text-cyan-400 text-[9px] font-black rounded-full">
                              {unreadCount} new
                            </span>
                          )}
                        </div>
                        <div className="flex gap-2.5">
                          {unreadCount > 0 && (
                            <button type="button" onClick={markAllRead} className="text-[10px] text-cyan-400 hover:text-cyan-300 font-bold">
                              Mark read
                            </button>
                          )}
                          {notifications.length > 0 && (
                            <button type="button" onClick={clearAll} className="text-[10px] text-gray-500 hover:text-gray-400 font-bold">
                              Clear
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
                        {notifications.length === 0 ? (
                          <div className="py-8 text-center space-y-2">
                            <span className="text-2xl">🌟</span>
                            <p className="text-xs text-gray-500 font-medium">All caught up! No notifications.</p>
                          </div>
                        ) : (
                          <AnimatePresence>
                            {notifications.map((n) => (
                              <motion.div
                                key={n.id}
                                initial={{ opacity: 0, y: -8 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, height: 0, margin: 0, padding: 0 }}
                                className={`p-3 rounded-xl border text-xs leading-relaxed transition-all ${
                                  n.read
                                    ? 'bg-white/[0.01] border-white/5 text-gray-400'
                                    : 'bg-cyan-500/5 border-cyan-500/15 text-white font-medium shadow-inner'
                                }`}
                              >
                                <p>{n.text}</p>
                                <div className="flex justify-between items-center mt-2 text-[10px] text-gray-500">
                                  <span>{n.time}</span>
                                  {!n.read && <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full" />}
                                </div>
                              </motion.div>
                            ))}
                          </AnimatePresence>
                        )}
                      </div>

                      <Link
                        to="/dashboard/profile"
                        onClick={() => {
                          setNotificationsOpen(false);
                          localStorage.setItem('settings_active_tab', 'notifications');
                        }}
                        className="block text-center text-xs text-cyan-400 hover:text-cyan-300 font-bold border-t border-white/5 pt-3 mt-2"
                      >
                        Manage Notification Settings ⚙️
                      </Link>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>

            {/* Avatar — reads real profile picture */}
            <Link to="/dashboard/profile" className="flex-shrink-0">
              <UserAvatar
                className="w-10 h-10 rounded-xl border border-white/10 shadow-lg shadow-blue-500/15 hover:brightness-110 transition-all"
                textClass="text-xs"
              />
            </Link>
          </div>
        </div>

        {/* Page Content */}
        <div className="w-full">
          {children || <Outlet />}
        </div>
      </main>
    </div>
  );
}
