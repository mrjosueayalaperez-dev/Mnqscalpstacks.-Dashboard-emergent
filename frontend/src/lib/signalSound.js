let ctx;

const tone = (freq, start, dur, gain = 0.12) => {
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = "sine";
  o.frequency.value = freq;
  g.gain.setValueAtTime(0, ctx.currentTime + start);
  g.gain.linearRampToValueAtTime(gain, ctx.currentTime + start + 0.02);
  g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
  o.connect(g).connect(ctx.destination);
  o.start(ctx.currentTime + start);
  o.stop(ctx.currentTime + start + dur + 0.05);
};

/** Distinct signal chime: ascending for LONG, descending for SHORT. */
export const playSignalSound = (side) => {
  try {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    const seq = side === "long" ? [660, 880, 1174] : [1174, 880, 660];
    seq.forEach((f, i) => tone(f, i * 0.14, 0.18));
  } catch { /* audio blocked until user interacts — ignore */ }
};
