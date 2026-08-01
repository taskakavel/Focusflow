// ===== FocusFlow — Pomodoro Timer (v4, defensive) =====
const DURATIONS = {
  focus: 25 * 60,
  short: 5 * 60,
  long: 15 * 60,
};

const LABELS = {
  focus: '⏳ Focus',
  short: 'Short Break',
  long: 'Long Break',
};

const STORAGE_KEY = 'focusflow-stats';
const SESSION_KEY = 'focusflow-session'; // persisted running session

// === State ===
let mode = 'focus';
let timeLeft = DURATIONS[mode];
let totalDuration = DURATIONS[mode];
let timerId = null;
let isRunning = false;
let endTime = null;      // wall-clock target when running
let wakeLock = null;
let wakeLockHintTimer = null;

// === DOM refs (nullable-safe) ===
const $ = (sel) => document.querySelector(sel);
const els = {
  card: $('.card'),
  time: $('#time'),
  sessionLabel: $('#sessionLabel'),
  startBtn: $('#startBtn'),
  resetBtn: $('#resetBtn'),
  tabs: Array.prototype.slice.call(document.querySelectorAll('.tab')),
  timerWrap: $('.timer-wrap'),
  timeDisplay: $('.timer-display'),
  ringFg: $('.ring-fg'),
  completedCount: $('#completedCount'),
  totalMinutes: $('#totalMinutes'),
  streak: $('#streak'),
  toast: $('#toast'),
  wakeHint: $('#wakeHint'),
};

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
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(stats)); } catch { /* ignore */ }
}

let stats = getStats();

// === Persisted running session (accuracy across tab close / relaunch) ===
function saveSession() {
  try {
    if (isRunning && endTime) {
      localStorage.setItem(SESSION_KEY, JSON.stringify({ endTime, mode, totalDuration }));
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  } catch { /* ignore */ }
}

function restoreSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (!s || !s.endTime || s.endTime <= Date.now()) {
      // Session finished while we were away — start fresh.
      localStorage.removeItem(SESSION_KEY);
      return;
    }
    if (!DURATIONS[s.mode]) return;
    mode = s.mode;
    totalDuration = DURATIONS[s.mode] || s.totalDuration;
    timeLeft = Math.max(0, Math.ceil((s.endTime - Date.now()) / 1000));
    endTime = s.endTime;
    isRunning = true;
    syncUI();
    requestWakeLock();
    timerId = setInterval(tick, 250);
  } catch { /* ignore */ }
}

// === Rendering ===
function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function render(updateLabel = true) {
  if (els.time) els.time.textContent = formatTime(timeLeft);
  if (els.ringFg) {
    const CIRC = 2 * Math.PI * 120;
    const progress = totalDuration > 0 ? timeLeft / totalDuration : 0;
    els.ringFg.style.strokeDashoffset = String(CIRC * (1 - progress));
  }
  if (updateLabel && els.sessionLabel) els.sessionLabel.textContent = LABELS[mode];
}

function renderStats() {
  if (els.completedCount) els.completedCount.textContent = stats.sessions;
  if (els.totalMinutes) els.totalMinutes.textContent = stats.minutes;
  if (els.streak) els.streak.textContent = stats.streak;
}

// === UI sync ===
function syncUI() {
  if (els.startBtn) els.startBtn.textContent = isRunning ? '⏸ Pause' : '▶ Start';
  if (els.startBtn) els.startBtn.classList.toggle('running', isRunning);
  if (els.card) els.card.classList.toggle('running', isRunning);
  if (els.card) els.card.dataset.mode = mode;

  els.tabs.forEach((t) => {
    const active = t.dataset.mode === mode;
    t.classList.toggle('is-active', active);
    t.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  render();
}

// === Wake lock (keeps the SCREEN ON while the app is visible & running) ===
async function requestWakeLock() {
  try {
    if ('wakeLock' in navigator && !wakeLock) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
      showWakeHint(true);
    }
  } catch { /* unsupported / denied — the timer still runs anyway */ }
}

function releaseWakeLock() {
  if (wakeLock) {
    try { wakeLock.release(); } catch { /* ignore */ }
    wakeLock = null;
  }
  showWakeHint(false);
}

function showWakeHint(on) {
  if (!els.wakeHint) return;
  els.wakeHint.textContent = on ? '🌞 Screen stays on while running' : '';
  clearTimeout(wakeLockHintTimer);
  if (on) {
    wakeLockHintTimer = setTimeout(() => { if (els.wakeHint) els.wakeHint.textContent = ''; }, 4000);
  }
}

// Re-acquire if the OS released it (e.g. after locking/unlocking)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && isRunning) {
    render(false);
    requestWakeLock();
  }
});

// === Accurate timer using wall-clock endTime ===
function tick() {
  if (!endTime) return;
  const now = Date.now();
  const remaining = Math.max(0, Math.ceil((endTime - now) / 1000));
  timeLeft = remaining;
  render(false);

  if (remaining <= 0) {
    clearInterval(timerId);
    timerId = null;
    isRunning = false;
    endTime = null;
    saveSession();
    syncUI();
    handleComplete();
  }
}

function startTimer() {
  // Permission prompt needs a user gesture — do it here, once.
  ensureNotificationPermission();
  // Unlock audio within this user gesture so the alarm can ring later.
  unlockAudio();

  if (timerId) return;
  if (timeLeft <= 0) timeLeft = totalDuration;

  isRunning = true;
  endTime = Date.now() + timeLeft * 1000;
  syncUI();
  saveSession();
  requestWakeLock();
  timerId = setInterval(tick, 250);
}

function pauseTimer() {
  clearInterval(timerId);
  timerId = null;
  isRunning = false;
  endTime = null;
  releaseWakeLock();
  saveSession();
  syncUI();
}

function resetTimer() {
  pauseTimer();
  timeLeft = totalDuration;
  syncUI();
}

function setMode(nextMode) {
  if (!DURATIONS[nextMode]) return;
  mode = nextMode;
  totalDuration = DURATIONS[mode];
  timeLeft = totalDuration;
  pauseTimer();
  syncUI();
}

// === Completion ===
function handleComplete() {
  const wasFocus = mode === 'focus';
  stats.sessions += wasFocus ? 1 : 0;
  stats.minutes += Math.round(DURATIONS.focus / 60) * (wasFocus ? 1 : 0);
  const today = new Date().toDateString();
  if (wasFocus) {
    if (stats.lastDay !== today) {
      const yesterday = new Date(Date.now() - 86400000).toDateString();
      stats.streak = stats.lastDay === yesterday ? stats.streak + 1 : 1;
      stats.lastDay = today;
    }
  }
  saveStats(stats);
  renderStats();

  const msg = wasFocus
    ? '✅ Focus session complete! Time for a break.'
    : '☕ Break over — let\'s focus!';

  showToast(msg);
  playAlarm();
  notify(msg);
  setMode(wasFocus ? 'short' : 'focus');
}

// === Notifications + vibration (screen-on / other-app scenarios) ===
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

// Unlock/resume the AudioContext inside a user gesture (e.g. pressing Start).
// iOS suspends audio until it's resumed in a tap handler — calling this in
// startTimer() guarantees the alarm can actually ring at completion.
function unlockAudio() {
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
  } catch { /* audio unsupported */ }
}

// One ringing burst: a warble between two frequencies (classic ring tone)
function ringBurst(start, dur) {
  if (!audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = 'sine';
  for (let t = 0; t < dur; t += 0.12) {
    osc.frequency.setValueAtTime(t % 0.24 < 0.12 ? 880 : 1046, start + t);
  }
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(0.35, start + 0.02);
  gain.gain.setValueAtTime(0.35, start + dur - 0.06);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
  osc.connect(gain).connect(audioCtx.destination);
  osc.start(start);
  osc.stop(start + dur + 0.05);
}

// Ringing alarm when a session finishes: "ring-ring … ring-ring … ring-ring"
function playAlarm() {
  try {
    unlockAudio();
    if (!audioCtx || audioCtx.state !== 'running') return;
    const now = audioCtx.currentTime + 0.05;
    const DUR = 0.75;   // length of one ring
    const GAP = 0.25;   // gap between the two rings
    const PAUSE = 0.6;  // pause between cycles
    for (let cycle = 0; cycle < 3; cycle++) {
      const base = now + cycle * (2 * DUR + GAP + PAUSE);
      ringBurst(base, DUR);              // ring ring
      ringBurst(base + DUR + GAP, DUR);  // ring ring
    }
  } catch { /* audio unsupported */ }
}

// === Toast ===
let toastTimer = null;
function showToast(msg) {
  if (!els.toast) return;
  els.toast.textContent = msg;
  els.toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove('show'), 3500);
}

// === Wiring ===
function bindEvents() {
  if (els.startBtn) {
    els.startBtn.addEventListener('click', () => (isRunning ? pauseTimer() : startTimer()));
  }
  if (els.resetBtn) {
    els.resetBtn.addEventListener('click', resetTimer);
  }
  els.tabs.forEach((tab) => {
    tab.addEventListener('click', () => setMode(tab.dataset.mode));
  });
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space') {
      e.preventDefault();
      if (isRunning) pauseTimer(); else startTimer();
    } else if (e.key && e.key.toLowerCase() === 'r') {
      resetTimer();
    } else if (e.key && e.key.toLowerCase() === 't') {
      const order = ['focus', 'short', 'long'];
      setMode(order[(order.indexOf(mode) + 1) % order.length]);
    }
  });
}

// === Init ===
function init() {
  render();
  renderStats();
  syncUI();
  bindEvents();
  restoreSession(); // may set the timer running again from a stored endTime
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}