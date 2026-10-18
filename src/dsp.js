// ---- DSP + puente ggwave (compartido por la demo y las pruebas en node) ----
const FS = 48000, NYQ = FS / 2;
const VOICES = {
  A: { id: 'A', name: 'Voz A · Llamante',     role: 'agente que llama',     ultra: false, shift: 0,      lo: 1500,  hi: 7000,  cssVar: '--va' },
  B: { id: 'B', name: 'Voz B · Recepción',    role: 'agente del hotel',     ultra: false, shift: 4687.5, lo: 6300,  hi: 11500, cssVar: '--vb' },
  C: { id: 'C', name: 'Voz C · Control',      role: 'canal ultrasónico',    ultra: true,  shift: 0,      lo: 13000, hi: 21000, cssVar: '--vc' },
};
const SPEEDS = ['NORMAL', 'FAST', 'FASTEST'];
let G = null;                                  // módulo ggwave

const _tw = new Map();
function twiddles(n) {
  if (_tw.has(n)) return _tw.get(n);
  const c = new Float64Array(n / 2), s = new Float64Array(n / 2);
  for (let i = 0; i < n / 2; i++) { c[i] = Math.cos(2 * Math.PI * i / n); s[i] = -Math.sin(2 * Math.PI * i / n); }
  const t = { c, s }; _tw.set(n, t); return t;
}
function fft(re, im, inv) {
  const n = re.length, { c, s } = twiddles(n);
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const half = len >> 1, step = n / len;
    for (let i = 0; i < n; i += len) {
      for (let k = 0, w = 0; k < half; k++, w += step) {
        const wr = c[w], wi = inv ? -s[w] : s[w];
        const a = i + k, b = a + half;
        const xr = re[b] * wr - im[b] * wi, xi = re[b] * wi + im[b] * wr;
        re[b] = re[a] - xr; im[b] = im[a] - xi; re[a] += xr; im[a] += xi;
      }
    }
  }
  if (inv) for (let i = 0; i < n; i++) { re[i] /= n; im[i] /= n; }
}
// Filtro pasa-banda [lo,hi] y desplazamiento en frecuencia (banda lateral única) vía señal analítica
function bandShift(x, lo, hi, shiftHz) {
  let N = 256; while (N < x.length) N <<= 1;
  const re = new Float64Array(N), im = new Float64Array(N);
  re.set(x); fft(re, im, false);
  const yr = new Float64Array(N), yi = new Float64Array(N);
  const sb = Math.round(shiftHz * N / FS), k0 = Math.ceil(lo * N / FS), k1 = Math.floor(hi * N / FS);
  for (let k = k0; k <= k1; k++) { const t = k + sb; if (t >= 0 && t < N / 2) { yr[t] = 2 * re[k]; yi[t] = 2 * im[k]; } }
  fft(yr, yi, true);
  return Float32Array.from(yr.subarray(0, x.length));
}
function peak(x) { let p = 0; for (let i = 0; i < x.length; i++) { const a = Math.abs(x[i]); if (a > p) p = a; } return p; }
function scaleTo(x, p) { const k = p / (peak(x) || 1); const y = new Float32Array(x.length); for (let i = 0; i < x.length; i++) y[i] = x[i] * k; return y; }
function mixSignals(list) {
  const n = Math.max(...list.map(s => s.length)), y = new Float32Array(n);
  for (const s of list) for (let i = 0; i < s.length; i++) y[i] += s[i];
  return y;
}
function meanPower(x) { let s = 0; for (let i = 0; i < x.length; i++) s += x[i] * x[i]; return s / x.length; }
function gauss() { let u = 0, v = 0; while (!u) u = Math.random(); v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
// ruido blanco con SNR referido a una banda de 4465 Hz (la del protocolo), como en el cuaderno
function addNoise(x, snrDb, refPower) {
  if (snrDb == null) return x;
  const sigma = Math.sqrt(refPower * (NYQ / 4465) / Math.pow(10, snrDb / 10));
  const y = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) y[i] = x[i] + sigma * gauss();
  return y;
}
function asciiOnly(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\x20-\x7e]/g, '?'); }

function mkInst() {
  const p = G.getDefaultParameters();
  p.sampleRateInp = FS; p.sampleRateOut = FS; p.soundMarkerThreshold = 4;
  return G.init(p);
}
function encodeVoice(v, text, speed) {
  const inst = mkInst();
  const proto = G.ProtocolId['GGWAVE_PROTOCOL_' + (v.ultra ? 'ULTRASOUND_' : 'AUDIBLE_') + speed];
  const w = G.encode(inst, text, proto, 10); G.free(inst);
  let f = new Float32Array(w.buffer.slice(w.byteOffset, w.byteOffset + w.byteLength));
  if (v.shift) f = bandShift(f, 0, NYQ, v.shift);
  return scaleTo(f, 0.3);
}
function decodeVoice(v, sig) {
  const rx = bandShift(sig, v.lo, v.hi, -v.shift);
  const pad = Math.round(0.25 * FS), buf = new Float32Array(rx.length + 2 * pad);
  buf.set(rx, pad);
  const inst = mkInst();
  const r = G.decode(inst, new Int8Array(buf.buffer)); G.free(inst);
  if (!r || !r.length) return null;
  return new TextDecoder().decode(new Uint8Array(Int8Array.from(r).buffer));
}
// banda que contiene el 99% de la energía y métricas de la señal emitida
function signalMetrics(x, nbytes) {
  let N = 256; while (N < x.length) N <<= 1;
  const re = new Float64Array(N), im = new Float64Array(N); re.set(x); fft(re, im, false);
  const half = N / 2, P = new Float64Array(half); let tot = 0;
  for (let k = 0; k < half; k++) { P[k] = re[k] * re[k] + im[k] * im[k]; tot += P[k]; }
  let c = 0, lo = 0, hi = half - 1, gotLo = false;
  for (let k = 0; k < half; k++) { c += P[k]; if (!gotLo && c >= 0.005 * tot) { lo = k; gotLo = true; } if (c >= 0.995 * tot) { hi = k; break; } }
  const f = k => k * FS / N, dur = x.length / FS, bw = f(hi) - f(lo);
  return { dur, bytes: nbytes, Bps: nbytes / dur, bps: nbytes * 8 / dur, lo: f(lo), hi: f(hi), bw, eff: nbytes * 8 / dur / bw, frac: bw / NYQ };
}

// ---- OFDM con carga adaptativa de bits (misma banda de 96 subportadoras que cada voz de ggwave) ----
const O = { NFFT: 1024, CP: 256, NB: 96, NPIL: 4, NHDR: 4, BACK: 16, GAMMA: Math.pow(10, 0.98), MARGIN: 2, START: { A: 40, B: 140, C: 320 } };
O.SYM = O.NFFT + O.CP;
const OMODES = [
  { bits: 6, rep: 1, label: '64-QAM' }, { bits: 4, rep: 1, label: '16-QAM' }, { bits: 2, rep: 1, label: 'QPSK' }, { bits: 1, rep: 1, label: 'BPSK' },
  { bits: 1, rep: 2, label: 'BPSK ×2' }, { bits: 1, rep: 4, label: 'BPSK ×4' }, { bits: 1, rep: 8, label: 'BPSK ×8' },
  { bits: 1, rep: 16, label: 'BPSK ×16' }, { bits: 1, rep: 32, label: 'BPSK ×32' },
];
function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function pnSigns(seed, n) { const r = mulberry32(seed), o = new Float64Array(n); for (let i = 0; i < n; i++) o[i] = r() < 0.5 ? -1 : 1; return o; }
const vseed = id => ({ A: 11, B: 22, C: 33 }[id] || 44);
function crc16(bytes) { let c = 0xFFFF; for (const b of bytes) { c ^= b << 8; for (let i = 0; i < 8; i++) c = (c & 0x8000) ? ((c << 1) ^ 0x1021) & 0xFFFF : (c << 1) & 0xFFFF; } return c; }
function ofdmPickMode(snrDb) {
  const need = m => 10 * Math.log10(O.GAMMA * (Math.pow(2, m.bits) - 1)) - 10 * Math.log10(m.rep) + O.MARGIN;
  for (let i = 0; i < OMODES.length; i++) if (need(OMODES[i]) <= snrDb) return i;
  return OMODES.length - 1;
}
const _pam = {};
function pam(m) {
  if (_pam[m]) return _pam[m];
  const M = 1 << m, lev = [], gray = [], inv = [];
  for (let i = 0; i < M; i++) { lev.push(-(M - 1) + 2 * i); gray.push(i ^ (i >> 1)); inv[i ^ (i >> 1)] = i; }
  return _pam[m] = { M, lev, gray, inv, sc: Math.sqrt(2 * (M * M - 1) / 3) };
}
function qamMod(bits, o, b) {
  if (b === 1) return [bits[o] ? 1 : -1, 0];
  const m = b / 2, t = pam(m); let gi = 0, gq = 0;
  for (let i = 0; i < m; i++) { gi = (gi << 1) | bits[o + i]; gq = (gq << 1) | bits[o + m + i]; }
  return [t.lev[t.inv[gi]] / t.sc, t.lev[t.inv[gq]] / t.sc];
}
function qamDemod(re, im, b, out, o) {
  if (b === 1) { out[o] = re > 0 ? 1 : 0; return; }
  const m = b / 2, t = pam(m);
  const ax = (v, off) => { const idx = Math.max(0, Math.min(t.M - 1, Math.round((v * t.sc + (t.M - 1)) / 2))), g = t.gray[idx]; for (let i = 0; i < m; i++) out[off + i] = (g >> (m - 1 - i)) & 1; };
  ax(re, o); ax(im, o + m);
}
// símbolo OFDM en el tiempo (con prefijo cíclico) a partir de NB valores complejos
function ofdmSymbolTime(vid, vals) {
  const re = new Float64Array(O.NFFT), im = new Float64Array(O.NFFT), k0 = O.START[vid];
  for (let j = 0; j < O.NB; j++) { const k = k0 + j; re[k] = vals[2 * j]; im[k] = vals[2 * j + 1]; re[O.NFFT - k] = vals[2 * j]; im[O.NFFT - k] = -vals[2 * j + 1]; }
  fft(re, im, true);
  const out = new Float32Array(O.SYM);
  for (let n = 0; n < O.CP; n++) out[n] = re[O.NFFT - O.CP + n];
  for (let n = 0; n < O.NFFT; n++) out[O.CP + n] = re[n];
  return out;
}
const pilotVals = (vid, i) => { const s = pnSigns(vseed(vid) * 1000 + i, O.NB), v = new Float64Array(2 * O.NB); for (let j = 0; j < O.NB; j++) v[2 * j] = s[j]; return v; };
function ofdmEncode(v, text, snrDb) {
  const bytes = new TextEncoder().encode(text); if (bytes.length > 255) throw new Error('mensaje demasiado largo para OFDM (máx. 255 B)');
  const mi = ofdmPickMode(snrDb == null ? 30 : snrDb), mode = OMODES[mi], bps = O.NB * mode.bits / mode.rep;
  const bits = []; for (const b of bytes) for (let i = 7; i >= 0; i--) bits.push((b >> i) & 1);
  const nS = Math.max(1, Math.ceil(bits.length / bps)); while (bits.length < nS * bps) bits.push(0);
  // cabecera de 32 bits: modo(4) | largo(8) | crc16(16) | 4 ceros
  const hb = [], push = (x, n) => { for (let i = n - 1; i >= 0; i--) hb.push((x >> i) & 1); };
  push(mi, 4); push(bytes.length, 8); push(crc16(bytes), 16); push(0, 4);
  const total = O.NPIL + O.NHDR + nS, out = new Float32Array(total * O.SYM); let si = 0;
  const put = vals => { out.set(ofdmSymbolTime(v.id, vals), si * O.SYM); si++; };
  for (let i = 0; i < O.NPIL; i++) put(pilotVals(v.id, i));
  for (let h = 0; h < O.NHDR; h++) {
    const scr = pnSigns(vseed(v.id) * 1000 + 100 + h, O.NB), vals = new Float64Array(2 * O.NB);
    for (let j = 0; j < O.NB; j++) vals[2 * j] = (hb[j % 32] ? 1 : -1) * scr[j];
    put(vals);
  }
  for (let s = 0; s < nS; s++) {
    const scr = pnSigns(vseed(v.id) * 1000 + 200 + s, O.NB), vals = new Float64Array(2 * O.NB), base = s * bps;
    if (mode.rep === 1) for (let j = 0; j < O.NB; j++) { const [a, b] = qamMod(bits, base + j * mode.bits, mode.bits); vals[2 * j] = a * scr[j]; vals[2 * j + 1] = b * scr[j]; }
    else { const G = O.NB / mode.rep; for (let i = 0; i < G; i++) for (let g = 0; g < mode.rep; g++) { const j = i + g * G; vals[2 * j] = (bits[base + i] ? 1 : -1) * scr[j]; } }
    put(vals);
  }
  const sig = scaleTo(out, 0.3);
  sig.info = { label: `OFDM · ${mode.label} · ${O.NB} subportadoras · ${nS + O.NPIL + O.NHDR} símbolos`, mode: mode.label, symbols: total };
  return sig;
}
function ofdmDecode(v, sig) {
  const rx = bandShift(sig, v.lo, v.hi, 0), L = rx.length;
  // sincronismo: correlación cruzada con el primer símbolo piloto
  const tpl = ofdmSymbolTime(v.id, pilotVals(v.id, 0));
  let N = 256; while (N < L + tpl.length) N <<= 1;
  const ar = new Float64Array(N), ai = new Float64Array(N), br = new Float64Array(N), bi = new Float64Array(N);
  ar.set(rx); br.set(tpl); fft(ar, ai, false); fft(br, bi, false);
  for (let k = 0; k < N; k++) { const xr = ar[k] * br[k] + ai[k] * bi[k], xi = ai[k] * br[k] - ar[k] * bi[k]; ar[k] = xr; ai[k] = xi; }
  fft(ar, ai, true);
  let n0 = 0, best = -1; for (let n = 0; n < L; n++) { const a = Math.abs(ar[n]); if (a > best) { best = a; n0 = n; } }
  const k0 = O.START[v.id], need = n0 + (O.NPIL + O.NHDR + 1) * O.SYM;
  if (need > L) return null;
  const sym = i => { const re = new Float64Array(O.NFFT), im = new Float64Array(O.NFFT), st = n0 + i * O.SYM + O.CP - O.BACK;
    for (let n = 0; n < O.NFFT; n++) re[n] = rx[st + n] || 0; fft(re, im, false);
    const y = new Float64Array(2 * O.NB); for (let j = 0; j < O.NB; j++) { y[2 * j] = re[k0 + j]; y[2 * j + 1] = im[k0 + j]; } return y; };
  const H = new Float64Array(2 * O.NB);
  for (let i = 0; i < O.NPIL; i++) { const y = sym(i), p = pilotVals(v.id, i); for (let j = 0; j < O.NB; j++) { H[2 * j] += y[2 * j] * p[2 * j] / O.NPIL; H[2 * j + 1] += y[2 * j + 1] * p[2 * j] / O.NPIL; } }
  const eq = (y, scr) => { const z = new Float64Array(2 * O.NB); for (let j = 0; j < O.NB; j++) { const a = H[2 * j], b = H[2 * j + 1], d = a * a + b * b + 1e-18, yr = y[2 * j], yi = y[2 * j + 1];
    z[2 * j] = (yr * a + yi * b) / d * scr[j]; z[2 * j + 1] = (yi * a - yr * b) / d * scr[j]; } return z; };
  // cabecera: combinación suave de 3 copias × NHDR símbolos
  const acc = new Float64Array(32);
  for (let h = 0; h < O.NHDR; h++) { const z = eq(sym(O.NPIL + h), pnSigns(vseed(v.id) * 1000 + 100 + h, O.NB)); for (let j = 0; j < O.NB; j++) acc[j % 32] += z[2 * j]; }
  const hb = Array.from(acc, x => x > 0 ? 1 : 0), rd = (o, n) => { let x = 0; for (let i = 0; i < n; i++) x = (x << 1) | hb[o + i]; return x; };
  const mi = rd(0, 4), len = rd(4, 8), crc = rd(12, 16);
  if (mi >= OMODES.length || len === 0) return null;
  const mode = OMODES[mi], bps = O.NB * mode.bits / mode.rep, nS = Math.ceil(len * 8 / bps);
  if (n0 + (O.NPIL + O.NHDR + nS) * O.SYM > L + O.SYM) return null;
  const bits = new Uint8Array(nS * bps);
  for (let s = 0; s < nS; s++) {
    const z = eq(sym(O.NPIL + O.NHDR + s), pnSigns(vseed(v.id) * 1000 + 200 + s, O.NB)), base = s * bps;
    if (mode.rep === 1) for (let j = 0; j < O.NB; j++) qamDemod(z[2 * j], z[2 * j + 1], mode.bits, bits, base + j * mode.bits);
    else { const G = O.NB / mode.rep; for (let i = 0; i < G; i++) { let acc2 = 0; for (let g = 0; g < mode.rep; g++) acc2 += z[2 * (i + g * G)]; bits[base + i] = acc2 > 0 ? 1 : 0; } }
  }
  const bytes = new Uint8Array(len); for (let i = 0; i < len; i++) { let b = 0; for (let k = 0; k < 8; k++) b = (b << 1) | bits[i * 8 + k]; bytes[i] = b; }
  if (crc16(bytes) !== crc) return null;
  return new TextDecoder().decode(bytes);
}
// eco de sala: la señal más unas pocas reflexiones de hasta 2,5 ms
function roomEcho(x) {
  const y = Float32Array.from(x), taps = [];
  for (let i = 0; i < 4; i++) { const d = 1 + Math.floor(Math.random() * 119); taps.push([d, gauss() * 0.25 * Math.exp(-3 * d / 120)]); }
  for (const [d, a] of taps) for (let n = d; n < x.length; n++) y[n] += a * x[n - d];
  return y;
}
