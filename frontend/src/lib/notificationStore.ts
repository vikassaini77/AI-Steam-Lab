/**
 * notificationStore.ts
 * Lightweight real-time notification system for NeuroLab AI.
 * Any component can call `pushNotification(...)` to fire a popup
 * and add to the bell-icon notification list.
 */

export interface Notification {
  id: number;
  text: string;
  time: string;
  read: boolean;
  type: 'xp' | 'badge' | 'streak' | 'info';
  popup?: boolean; // show as floating toast popup
}

type Listener = (notifications: Notification[]) => void;
type PopupListener = (notification: Notification) => void;

let notifications: Notification[] = [
  {
    id: 1,
    text: "🎉 Congratulations! You unlocked the 'Quick Learner' badge! (+300 XP)",
    time: '2 mins ago',
    read: false,
    type: 'badge',
  },
  {
    id: 2,
    text: '🔥 Streak Alert: Maintain your 5-day streak! Log in tomorrow to secure it.',
    time: '1 hour ago',
    read: false,
    type: 'streak',
  },
  {
    id: 3,
    text: "🤖 AI Tutor: You have 1 new suggested topic: 'Newton's Laws of Motion'.",
    time: '3 hours ago',
    read: true,
    type: 'info',
  },
  {
    id: 4,
    text: '📊 Weekly Report: You gained 850 XP and completed 3 labs this week!',
    time: '1 day ago',
    read: true,
    type: 'xp',
  },
];

let nextId = 100;
const listeners: Listener[] = [];
const popupListeners: PopupListener[] = [];

function notify() {
  listeners.forEach((l) => l([...notifications]));
}

/** Subscribe to the full notification list */
export function subscribeNotifications(fn: Listener): () => void {
  listeners.push(fn);
  fn([...notifications]);
  return () => {
    const idx = listeners.indexOf(fn);
    if (idx !== -1) listeners.splice(idx, 1);
  };
}

/** Subscribe to popup-only events (floating toast) */
export function subscribePopups(fn: PopupListener): () => void {
  popupListeners.push(fn);
  return () => {
    const idx = popupListeners.indexOf(fn);
    if (idx !== -1) popupListeners.splice(idx, 1);
  };
}

/** Push a new notification — shows as popup AND adds to bell list */
export function pushNotification(
  text: string,
  type: Notification['type'] = 'info',
  showPopup = true
) {
  const n: Notification = {
    id: nextId++,
    text,
    time: 'Just now',
    read: false,
    type,
    popup: showPopup,
  };
  notifications = [n, ...notifications];
  notify();
  if (showPopup) {
    popupListeners.forEach((l) => l(n));
  }
}

export function markAllRead() {
  notifications = notifications.map((n) => ({ ...n, read: true }));
  notify();
}

export function clearAll() {
  notifications = [];
  notify();
}

export function getNotifications(): Notification[] {
  return [...notifications];
}
