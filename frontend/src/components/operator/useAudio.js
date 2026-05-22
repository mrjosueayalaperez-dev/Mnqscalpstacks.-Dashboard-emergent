/**
 * Lightweight Web Audio synth — no assets, just oscillator beeps.
 * Different pitches encode different events so you can confirm trades by ear.
 */
let _ctx = null;
const getCtx = () => {
  if (typeof window === "undefined") return null;
  if (!_ctx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) _ctx = new Ctx();
  }
  // Resume if suspended (Chrome autoplay policy)
  if (_ctx && _ctx.state === "suspended") _ctx.resume().catch(() => {});
  return _ctx;
};

const beep = (freq, durationMs = 90, type = "sine", gain = 0.18) => {
  const ctx = getCtx();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  g.gain.value = gain;
  osc.connect(g).connect(ctx.destination);
  osc.start();
  // Quick exponential decay so it's punchy, not buzzy
  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + durationMs / 1000);
  osc.stop(ctx.currentTime + durationMs / 1000 + 0.02);
};

const sequence = (notes) => {
  const ctx = getCtx();
  if (!ctx) return;
  notes.forEach(([freq, dur, delay = 0, type = "sine", gain = 0.18], i) => {
    setTimeout(() => beep(freq, dur, type, gain), delay);
  });
};

export const sounds = {
  buy:        () => sequence([[660, 70, 0], [990, 90, 70]]),                  // up-chirp
  sell:       () => sequence([[660, 70, 0], [440, 90, 70]]),                  // down-chirp
  close:      () => beep(520, 60, "triangle"),                                // flat tap
  breakEven:  () => sequence([[700, 60, 0], [700, 60, 90]]),                  // double tick
  flatten:    () => sequence([[880, 80, 0, "square", 0.22], [440, 140, 90, "square", 0.22]]), // klaxon
  reject:     () => beep(180, 180, "sawtooth", 0.22),                         // low buzz
  killOn:     () => sequence([[300, 120, 0, "square"], [200, 160, 130, "square"]]),
  killOff:    () => sequence([[400, 90, 0], [600, 90, 90], [800, 110, 180]]),
  pause:      () => beep(440, 70, "triangle"),
  snipeOn:    () => sequence([[523, 70, 0], [659, 70, 70], [784, 90, 140], [1047, 110, 230]]),
  snipeOff:   () => sequence([[1047, 80, 0], [523, 110, 90]]),
  click:      () => beep(880, 30, "square", 0.08),
};

export const unlockAudio = () => {
  // Must be called from a user gesture — primes the AudioContext.
  getCtx();
};
