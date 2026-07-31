// ===== FocusFlow — Pomodoro Timer =====
const DURATIONS = {
  focus: 25 * 60,
  short: 5 * 60,
  long: 15 * 60,
};

const LABELS = {
  focus: 'Focus',
  short: 'Short Break',
  long: 'Long Break',
};

const STORAGE_KEY = 'focusflow-stats';

// === DOM refs ===
const els = {
  card: document.querySelector('.card'),
  time: document.getElementById('time'),
  sessionLabel: document.getElementById('sessionLabel'),
  startBtn: document.getElementById('startBtn'),
  resetBtn: document.getElementById('resetBtn'),
  tabs: [...document.querySelectorAll('.tab')],
  ringFg: document.querySelector('.ring-fg'),
  completedCount: document.getElementById('completedCount'),
  totalMinutes: document.getElementById('totalMinutes'),
  streak: document.getElementById('streak'),
  toast: document.getElementById('toast'),
};

// === State ===
let mode = 'focus';
let timeLeft = DURATIONS[mode];
let totalDuration = DURATIONS[mode];
let timerId = null;
let isRunning = false;
let endTime = null;          // wall-clock target when running
let wakeLock = null;
let completeFiredWhileHidden = false;

// === Persisted stats ===
function getStats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const stats = raw ? JSON.parse(raw) : {};
    const today = new Date().toDateString();
    if (stats.lastDay !== today) stats.streak = 0;
    return { sessions: 0, minutes: 0, lastDay: today, streak: 0, ...stats };
  } catch {
    return { sessions: 0, minutes: 0, lastDay: new Date().toDateString(), streak: 0 };
  }
}

function saveStats(stats) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stats));
  } catch {
    /* storage unavailable — fine to ignore */
  }
}

let stats = getStats();

// === Rendering ===
function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function render(updateLabel = true) {
  els.time.textContent = formatTime(timeLeft);
  const CIRC = 2 * Math.PI * 120;
  const progress = timeLeft / totalDuration;
  els.ringFg.style.strokeDashoffset = String(CIRC * (1 - progress));
  if (updateLabel) els.sessionLabel.textContent = LABELS[mode];
}

function renderStats() {
  els.completedCount.textContent = stats.sessions;
  els.totalMinutes.textContent = stats.minutes;
  els.streak.textContent = stats.streak;
}

// === Wake lock (keeps screen on while timer runs, where supported) ===
async function requestWakeLock() {
  try {
    if ('wakeLock' in navigator && !wakeLock) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    }
  } catch {
    /* wake lock unsupported or denied — non-fatal */
  }
}

function releaseWakeLock() {
  if (wakeLock) {
    try { wakeLock.release(); } catch { /* ignore */ }
    wakeLock = null;
  }
}

// Re-acquire when the tab becomes visible again (OS may auto-release)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && isRunning) {
    requestWakeLock();
  }
});

// === Accurate timer (catches up correctly even in background/locked) ===
// Uses a wall-clock endTime + setInterval. If the device suspends JS
// (background tab, or locked screen once the OS suspends the page), the
// interval stalls — but the next tick recomputes from Date.now(), so the
// displayed time is always correct when you come back.
function tick() {
  const now = Date.now();
  const remaining = Math.max(0, Math.ceil((endTime - now) / 1000));
  timeLeft = remaining;
  render(false);

  if (remaining <= 0) {
    clearInterval(timerId);
    timerId = null;
    isRunning = false;
    endTime = null;
    updateButton();
    if (document.visibilityState === 'hidden') {
      // We finished in the background: mark for completion on return.
      // (The OS usually suspends us before this, but this covers cases
      // where a background tab is still throttled-but-alive.)
      completeFiredWhileHidden = true;
      renderStats();
      return;
    }
    handleComplete();
  }
}

function startTimer() {
  if (timerId) return;
  isRunning = true;
  endTime = Date.now() + timeLeft * 1000;
  updateButton();
  requestWakeLock();
  render();
  timerId = setInterval(tick, 250);
}

function pauseTimer() {
  clearInterval(timerId);
  timerId = null;
  isRunning = false;
  endTime = null;
  releaseWakeLock();
  updateButton();
}

function resetTimer() {
  pauseTimer();
  timeLeft = totalDuration;
  render();
}

function setMode(nextMode) {
  if (!DURATIONS[nextMode]) return;
  mode = nextMode;
  totalDuration = DURATIONS[mode];
  timeLeft = totalDuration;
  pauseTimer();
  render();

  els.tabs.forEach((t) => {
    const active = t.dataset.mode === mode;
    t.classList.toggle('is-active', active);
    t.setAttribute('aria-selected', active);
  });
  els.sessionLabel.textContent = LABELS[mode];
  els.card.dataset.mode = mode;
}

// === Auto-switch when we finish while the tab was hidden ===
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && completeFiredWhileHidden) {
    completeFiredWhileHidden = false;
    handleComplete();
  }
});

// === Completion ===
function handleComplete() {
  const wasFocus = mode === 'focus';
  stats.sessions += wasFocus ? 1 : 0;
  stats.minutes += Math.round(DURATIONS.focus / 60) * (wasFocus ? 1 : 0);
  const today = new Date().toDateString();
  if (wasFocus) {
    // Streak: consecutive distinct days including today
    if (stats.lastDay !== today) {
      const yesterday = new Date(Date.now() - 86400000).toDateString();
      stats.streak = stats.lastDay === yesterday ? stats.streak + 1 : 1;
      stats.lastDay = today;
    }
  }
  saveStats(stats);
  renderStats();

  const msg = wasFocus
    ? `✅ Focus session complete! Time for a break.`
    : `☕ Break over — let's focus!`;

  showToast(msg);
  playChime();
  notify(msg);
  setMode(wasFocus ? 'short' : 'focus');
}

// === Notifications + vibration (alert you even if you're in another app) ===
// Note: push/media/notifications can't run while the phone is fully locked —
// this covers switching apps / screen-on cases.
function ensureNotificationPermission() {
  try {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  } catch { /* unsupported */ }
}

function notify(msg) {
  try {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('FocusFlow', {
        body: msg,
        icon: 'apple-touch-icon.png',
        tag: 'focusflow',
      });
    }
  } catch { /* unsupported */ }
  try {
    if (typeof navigator.vibrate === 'function') {
      navigator.vibrate([200, 100, 200]);
    }
  } catch { /* unsupported */ }
}

// === Sound (Web Audio API) ===
let audioCtx = null;
function playChime() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;
    [660, 880, 990].forEach((freq, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, now + i * 0.18);
      gain.gain.linearRampToValueAtTime(0.25, now + i * 0.18 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.18 + 0.35);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + i * 0.18);
      osc.stop(now + i * 0.18 + 0.4);
    });
  } catch {
    /* audio unsupported — ignore */
  }
}

// === Toast ===
let toastTimer = null;
function showToast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove('show'), 3500);
}

// === Events ===
els.startBtn.addEventListener('click', () => (isRunning ? pauseTimer() : startTimer()));
els.resetBtn.addEventListener('click', resetTimer);

els.tabs.forEach((tab) => {
  tab.addEventListener('click', () => setMode(tab.dataset.mode));
});

document.addEventListener('keydown', (e) => {
  if (e.code === 'Space') {
    e.preventDefault();
    isRunning ? pauseTimer() : startTimer();
  } else if (e.key.toLowerCase() === 'r') {
    resetTimer();
  } else if (e.key.toLowerCase() === 't') {
    const order = ['focus', 'short', 'long'];
    setMode(order[(order.indexOf(mode) + 1) % order.length]);
  }
});

// Ask for notification permission on first start (user gesture requirement).
ensureNotificationPermission();

// === Init ===
render();
renderStats();