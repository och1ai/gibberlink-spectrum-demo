import nbformat as nbf
nb = nbf.v4.new_notebook()
C = []
def md(s): C.append(nbf.v4.new_markdown_cell(s.strip()))
def code(s): C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# GibberLink: ¿cuánto espectro usa y cómo aprovecharlo mejor?

Este cuaderno mide el audio que genera el `ggwave.wasm` incluido en el repo
[PennyroyalTea/gibberlink](https://github.com/PennyroyalTea/gibberlink) (`hackathon_demo/src/utils/audioUtils.ts`)
y prueba cuatro mejoras, primero **por separado** y luego **combinadas**:

| # | Mejora | ¿Real o simulada? |
|---|---|---|
| 1 | Pasar de `AUDIBLE_FAST` a `AUDIBLE_FASTEST` | **Real**: señales generadas y decodificadas con ggwave |
| 2 | Pasar a ultrasonido (`ULTRASOUND_*`) | **Real** |
| 3 | Dúplex por división de frecuencia (FDM): cada lado habla en su propia banda | **Real**: se mezclan señales y se decodifican con ggwave |
| 4 | Reemplazar FSK por OFDM con carga adaptativa de bits (QAM) | **Simulada** en NumPy, con canal acústico modelado |

> **Límites honestos.** Todo se prueba en canal eléctrico (ruido blanco añadido, filtros, multitrayecto simulado).
> No hay aire, altavoz ni micrófono reales. Las partes 1–3 usan el códec real, pero las cifras de la parte 4 son
> una cota optimista: no incluyen sincronismo, deriva de reloj, AGC ni no linealidades del altavoz.
""")

code("""
import numpy as np, subprocess, json, tempfile, os, shutil
import matplotlib.pyplot as plt
from scipy.signal import welch, hilbert, butter, sosfiltfilt

plt.rcParams.update({'figure.dpi': 110, 'axes.grid': True, 'grid.alpha': .25, 'axes.spines.top': False, 'axes.spines.right': False})
FS = 48000                     # igual que new AudioContext({ sampleRate: 48000 }) en el repo
NYQ = FS / 2
MSG = "AB$Hello, I would like to book a room for two nights next week please"   # prefijo ID$ como en sendAudioMessage
NB = len(MSG.encode())
HERE = os.getcwd()
TMP = tempfile.mkdtemp(prefix='gl_')
rng = np.random.default_rng(1)
print('payload:', NB, 'bytes')

def _node(*args):
    r = subprocess.run(['node', os.path.join(HERE, 'gl_tools.js'), *args], capture_output=True, text=True, timeout=300)
    return r.stdout

def enc(proto, msg=MSG):
    p = os.path.join(TMP, f'enc_{proto}.f32')
    _node('encode', proto, msg, p)
    return np.fromfile(p, dtype=np.float32).astype(np.float64)

PAD = int(0.25 * FS)
def dec_many(sigs):
    \"\"\"Decodifica varias señales con ggwave real (protocolos activos: todos). Devuelve lista de str|None.\"\"\"
    files = []
    for i, s in enumerate(sigs):
        p = os.path.join(TMP, f'd_{i}.f32')
        np.concatenate([np.zeros(PAD), s, np.zeros(PAD)]).astype(np.float32).tofile(p)
        files.append(p)
    out = [l for l in _node('decode', *files).splitlines() if l.startswith('{')][-1]
    res = json.loads(out)
    return [res[f] for f in files]

def occupied_band(x, p=0.995):
    f, P = welch(x, FS, nperseg=4096)
    c = np.cumsum(P) / P.sum()
    return f[np.searchsorted(c, (1-p)/2)], f[min(np.searchsorted(c, 1-(1-p)/2), len(f)-1)]

def stats(name, x, nbytes=NB):
    lo, hi = occupied_band(x); dur = len(x)/FS
    return dict(name=name, dur=dur, Bps=nbytes/dur, lo=lo, hi=hi, bw=hi-lo, eff=nbytes*8/dur/(hi-lo), frac=(hi-lo)/NYQ)

PROTOS = ['AUDIBLE_NORMAL','AUDIBLE_FAST','AUDIBLE_FASTEST','ULTRASOUND_NORMAL','ULTRASOUND_FAST','ULTRASOUND_FASTEST']
SIG = {p: enc(p) for p in PROTOS}
ok = dict(zip(PROTOS, [d == MSG for d in dec_many([SIG[p] for p in PROTOS])]))
print('ida y vuelta sin ruido:', ok)
""")

md("""
## 0. Línea base: lo que hace hoy el repo

La demo usa `AUDIBLE_FAST` (o `AUDIBLE_FASTEST` si se pide), a 48 kHz, volumen 10.
""")

code("""
S0 = stats('AUDIBLE_FAST (repo)', SIG['AUDIBLE_FAST'])
print(f"{S0['name']}: {S0['dur']:.2f} s, {S0['Bps']:.1f} B/s ({S0['Bps']*8:.0f} bit/s), banda {S0['lo']:.0f}–{S0['hi']:.0f} Hz "
      f"({S0['bw']:.0f} Hz = {S0['frac']*100:.0f}% de Nyquist), {S0['eff']:.3f} bit/s/Hz")

def plot_spec(ax, names, title):
    for n in names:
        f, P = welch(SIG[n], FS, nperseg=4096)
        ax.semilogy(f/1000, P/P.max(), label=n, lw=1)
    ax.set_xlim(0, 24); ax.set_ylim(1e-8, 2); ax.set_xlabel('kHz'); ax.set_ylabel('PSD relativa'); ax.set_title(title); ax.legend(fontsize=8)
fig, ax = plt.subplots(figsize=(9, 3.2)); plot_spec(ax, ['AUDIBLE_FAST'], 'Espectro del protocolo que usa el repo'); 
ax.axvspan(20, 24, color='gray', alpha=.15); ax.text(20.3, 1e-6, 'sobre 20 kHz', fontsize=8)
plt.show()

fig, ax = plt.subplots(figsize=(9, 3.2))
f, t, Z = __import__('scipy.signal', fromlist=['spectrogram']).spectrogram(SIG['AUDIBLE_FAST'], FS, nperseg=2048, noverlap=1536)
ax.pcolormesh(t, f/1000, 10*np.log10(Z+1e-12), vmin=-110, vmax=-40, shading='auto', cmap='magma')
ax.set_ylabel('kHz'); ax.set_xlabel('s'); ax.set_title('Espectrograma: una franja delgada de 4,5 kHz, resto vacío'); ax.grid(False); plt.show()
""")

md("""
## 1. Mejora 1: `AUDIBLE_FASTEST`

Es un cambio de una línea (`fastest = true`). Reduce las tramas por símbolo de 6 a 3, así que va ~1,8× más rápido
en la misma banda. El costo es menos tiempo de integración por símbolo, o sea **menos margen frente al ruido**.
Lo medimos con ruido blanco gaussiano en la banda del protocolo, subiendo el nivel hasta que el decodificador falle.
""")

code("""
def noisy(x, snr_db, seed, channel=None):
    # canal sobre la señal limpia, luego ruido blanco; SNR referido a la señal emitida en 4465 Hz
    r = np.random.default_rng(seed)
    xp = np.concatenate([np.zeros(PAD), x, np.zeros(PAD)])
    s2 = np.mean(x**2) * (NYQ/4465) / 10**(snr_db/10)
    if channel: xp = channel(xp)
    return (xp + r.normal(0, np.sqrt(s2), len(xp)))[PAD:-PAD]

def success(proto, snr_db, trials=6, channel=None):
    sigs = [noisy(SIG[proto], snr_db, 1000+t, channel) for t in range(trials)]
    return np.mean([d == MSG for d in dec_many(sigs)])

SNRS = np.arange(-12, 13, 3)
CURVE = {p: [success(p, s) for s in SNRS] for p in ['AUDIBLE_NORMAL','AUDIBLE_FAST','AUDIBLE_FASTEST']}
fig, ax = plt.subplots(figsize=(8, 3.4))
for p, v in CURVE.items(): ax.plot(SNRS, np.array(v)*100, 'o-', label=p)
ax.set_xlabel('SNR en banda (dB)'); ax.set_ylabel('% mensajes decodificados'); ax.set_title('Robustez al ruido blanco'); ax.legend(); plt.show()
def thr(v): 
    i = [k for k, x in enumerate(v) if x >= 0.99]
    return SNRS[i[0]] if i else None
rows = []
for p in ['AUDIBLE_NORMAL','AUDIBLE_FAST','AUDIBLE_FASTEST']:
    s = stats(p, SIG[p]); rows.append((p, s['dur'], s['Bps'], thr(CURVE[p])))
print(f"{'protocolo':18s} {'duración':>9s} {'B/s':>7s} {'SNR mín (dB)':>13s}")
for r in rows: print(f"{r[0]:18s} {r[1]:8.2f}s {r[2]:7.1f} {str(r[3]):>13s}")
""")

md("""
**Lectura.** `FASTEST` sube la velocidad ~1,8× y en este barrido (pasos de 3 dB, ruido blanco) el umbral de decodificación fue parecido: 0–3 dB de SNR en banda. Con ruido impulsivo o eco puede ser peor, porque los símbolos son más cortos. Es la mejora más barata,
pero **no cambia nada del uso del espectro**: sigue en la misma franja de 4,5 kHz.
""")

md("""
## 2. Mejora 2: ultrasonido

ggwave trae `ULTRASOUND_{NORMAL,FAST,FASTEST}`, que mueven la misma modulación a ~15–19,5 kHz.
La velocidad no cambia. Lo que se gana es que **no se oye** y que no compite con la voz de los agentes.
El riesgo está en el hardware: altavoces y micrófonos baratos atenúan mucho por encima de ~16 kHz.
""")

code("""
fig, ax = plt.subplots(figsize=(9, 3.2)); plot_spec(ax, ['AUDIBLE_FASTEST','ULTRASOUND_FASTEST'], 'Audible vs ultrasonido (FASTEST)'); plt.show()
for p in ['AUDIBLE_FAST', 'ULTRASOUND_FAST', 'AUDIBLE_FASTEST', 'ULTRASOUND_FASTEST']:
    s = stats(p, SIG[p]); print(f"{p:20s} {s['Bps']:5.1f} B/s  banda {s['lo']:6.0f}–{s['hi']:6.0f} Hz")

# Sensibilidad al hardware: el altavoz corta con un Butterworth pasabajos (SNR fijo = 15 dB)
cuts = [22000, 19000, 17000, 16000, 15000, 14000]
def lp(c): 
    sos = butter(4, c, 'low', fs=FS, output='sos'); return lambda y: sosfiltfilt(sos, y)
res_hw = {p: [success(p, 15, trials=4, channel=lp(c)) for c in cuts] for p in ['AUDIBLE_FASTEST', 'ULTRASOUND_FASTEST']}
fig, ax = plt.subplots(figsize=(8, 3.2))
for p, v in res_hw.items(): ax.plot(np.array(cuts)/1000, np.array(v)*100, 'o-', label=p)
print({p: [f'{c//1000}k:{int(x*100)}%' for c, x in zip(cuts, v)] for p, v in res_hw.items()})
ax.invert_xaxis(); ax.set_xlabel('frecuencia de corte del altavoz (kHz)'); ax.set_ylabel('% decodificado'); ax.legend(); ax.set_title('Ultrasonido frente a hardware con corte alto'); plt.show()
""")

md("""
**Lectura.** El ultrasonido decodificó bien con corte en 17 kHz o más y **falló por completo con corte en 16 kHz o menos** (el audible no se inmutó).
En un teléfono o portátil típico, que corta cerca de los 16 kHz, el audible es más seguro. Es una mejora de *discreción* y de
*reparto del espectro*, no de velocidad.
""")

md("""
## 3. Mejora 3: dúplex por división de frecuencia (FDM)

Hoy los dos agentes hablan por turnos (semidúplex): el tiempo de un intercambio es `t_A + t_B`.
Si cada agente usa **su propia banda**, pueden hablar a la vez y el intercambio dura `max(t_A, t_B)`.

Probamos dos formas con ggwave real:
- **Audible + ultrasonido**: A en 1,9–6,3 kHz y B en 15–19,5 kHz.
- **Solo audible**: B se desplaza +4687,5 Hz (exactamente 100 bins de ggwave) con una banda lateral única (transformada de Hilbert),
  y el receptor lo devuelve a su sitio antes de decodificar.
""")

code("""
def bp(lo, hi):
    sos = butter(8, [lo, hi], 'band', fs=FS, output='sos'); return lambda y: sosfiltfilt(sos, y)
def fshift(x, df):
    t = np.arange(len(x))/FS
    return np.real(hilbert(x) * np.exp(2j*np.pi*df*t))
def mix(*sigs):
    n = max(len(s) for s in sigs); y = np.zeros(n)
    for s in sigs: y[:len(s)] += s
    return y

mA = "AB$Hola, necesito una habitacion para dos noches"
mB = "CD$Claro, hay disponibilidad desde el viernes"
xA = enc('AUDIBLE_FASTEST', mA)
xB_us = enc('ULTRASOUND_FASTEST', mB)
xB_ssb = fshift(enc('AUDIBLE_FASTEST', mB), 4687.5)

# a) audible + ultrasonido
Y = mix(xA, xB_us)
rxA = bp(1500, 7000)(Y); rxB = bp(13000, 21000)(Y)
a_ok = dec_many([rxA, rxB]) 
print('Audible + ultrasonido ->', a_ok[0] == mA, a_ok[1] == mB)

# b) solo audible, dos canales contiguos
Y2 = mix(xA, xB_ssb)
rxA2 = bp(1500, 7000)(Y2)
rxB2 = fshift(bp(6300, 11500)(Y2), -4687.5)
b_ok = dec_many([rxA2, rxB2])
print('Dos canales audibles  ->', b_ok[0] == mA, b_ok[1] == mB)

tA, tB = len(xA)/FS, len(xB_us)/FS
print(f"Semidúplex: {tA+tB:.2f} s   |   FDM: {max(tA,tB):.2f} s   (ganancia {((tA+tB)/max(tA,tB)):.2f}×)")

fig, ax = plt.subplots(1, 2, figsize=(11, 3.2), sharey=True)
for a, (y, ttl) in zip(ax, [(Y, 'Audible + ultrasonido'), (Y2, 'Dos canales audibles (SSB)')]):
    f, P = welch(y, FS, nperseg=4096); a.semilogy(f/1000, P/P.max(), lw=1); a.set_title(ttl); a.set_xlabel('kHz'); a.set_xlim(0, 24); a.set_ylim(1e-8, 2)
plt.show()
""")

md("""
**Lectura.** Con FDM, **A→B y B→A** viajan en paralelo y el tiempo del intercambio baja a la mitad
(o menos, si los mensajes son asimétricos). Además, cada lado puede interrumpir al otro sin esperar turno.
La velocidad por canal es la misma; lo que aumenta es el **caudal agregado** y el uso del espectro.
""")

md("""
## 4. Mejora 4: OFDM con carga adaptativa de bits (simulación)

ggwave es FSK multitono: cada símbolo lleva pocos bits y la razón es siempre la misma, aunque el canal sea bueno.
OFDM divide la banda en subportadoras de 46,9 Hz (igual que ggwave) y **asigna a cada una tantos bits como su SNR permita**
(BPSK, QPSK, 16-QAM, 64-QAM), con ecualizador por piloto.

**Modelo del canal** (supuestos, ajustables en la siguiente celda):
- Altavoz+micrófono: pasaaltos de 2.º orden a 300 Hz y pasabajos de 2.º orden a `LP_CUT` (16 kHz por defecto).
- Ruido de sala que cae con la frecuencia (−20 dB/década sobre 1,5 kHz) más un piso de micrófono de −25 dB.
- Multitrayecto de hasta 2,5 ms con decaimiento exponencial (prefijo cíclico de 5,3 ms).
- **Potencia total de transmisión constante**: si se ensancha la banda, cada subportadora recibe menos potencia.
- Brecha de Shannon Γ = 9,8 dB (sin codificación de canal, BER objetivo ~10⁻⁷), estimación de canal con 8 símbolos piloto cada 50 de datos.
""")

code("""
NFFT, CP = 1024, 256
DF = FS/NFFT
TSYM = (NFFT+CP)/FS
NREF = 96              # subportadoras que usa ggwave: referencia de potencia
NPIL = 8
GAMMA = 10**0.98
ALLOWED = np.array([0, 1, 2, 4, 6])
LP_CUT = 16000

def Hdb(f, cut=None):
    cut = cut or LP_CUT
    f = np.maximum(f, 1.0)
    return 20*np.log10(1/np.sqrt(1+(300/f)**4) / np.sqrt(1+(f/cut)**4))
def Ndb(f): return 10*np.log10(1/(1+(f/1500)**2) + 10**(-2.5))
def snr_bin_db(f, snr0, nused):
    return snr0 + Hdb(f) - (Ndb(f)-Ndb(3000)) - 10*np.log10(nused/NREF)

def load_bits(snr_db):
    cap = np.log2(1 + 10**(snr_db/10)/GAMMA)
    return np.array([ALLOWED[ALLOWED <= c].max() for c in cap])

def _pam(m):
    M = 1 << m; lev = np.arange(-(M-1), M, 2).astype(float)
    g = np.array([i ^ (i >> 1) for i in range(M)]); inv = np.empty(M, int); inv[g] = np.arange(M)
    return lev, g, inv
def qam_mod(bits, b):
    if b == 1: return 2.0*bits[:, 0]-1
    m = b//2; lev, g, inv = _pam(m); w = 1 << np.arange(m-1, -1, -1)
    return (lev[inv[bits[:, :m] @ w]] + 1j*lev[inv[bits[:, m:] @ w]]) / np.sqrt(2*((1 << m)**2-1)/3)
def qam_demod(s, b):
    if b == 1: return (s.real > 0).astype(int)[:, None]
    m = b//2; lev, g, inv = _pam(m); M = 1 << m; s = s*np.sqrt(2*(M*M-1)/3)
    def ax(v):
        idx = np.clip(np.round((v+(M-1))/2), 0, M-1).astype(int)
        return (g[idx][:, None] >> np.arange(m-1, -1, -1)) & 1
    return np.hstack([ax(s.real), ax(s.imag)])

def ofdm_link(f_lo, f_hi, snr0, nsym=200, seed=0, cut=None, loading=None):
    r = np.random.default_rng(seed)
    ks = np.arange(int(np.ceil(f_lo/DF)), int(np.floor(f_hi/DF))+1); fk = ks*DF; nu = len(ks)
    snr_k = snr_bin_db(fk, snr0, nu)
    b = load_bits(snr_k) if loading is None else loading
    amp = np.sqrt(NREF/nu)                                   # potencia total constante
    # preámbulo: NPIL símbolos BPSK conocidos (se promedian para estimar el canal)
    pil = 2.0*r.integers(0, 2, (NPIL, nu))-1
    data_bits = [r.integers(0, 2, (nsym, int(bk))) for bk in b]
    tx_syms = np.zeros((NPIL+nsym, NFFT), complex)
    for i in range(NPIL): tx_syms[i, ks] = amp*pil[i]
    for j, (k, bk) in enumerate(zip(ks, b)):
        if bk: tx_syms[NPIL:, k] = amp*qam_mod(data_bits[j], int(bk))
    tx_syms[:, NFFT-ks] = np.conj(tx_syms[:, ks])
    x = np.fft.ifft(tx_syms, axis=1).real
    x = np.hstack([x[:, -CP:], x]).ravel()
    # canal: multitrayecto + respuesta altavoz/mic
    n = len(x); fr = np.fft.rfftfreq(n, 1/FS)
    h = np.zeros(int(0.0025*FS)); h[0] = 1
    dl = r.integers(1, len(h), 6); h[dl] += r.normal(0, 1, 6)*np.exp(-3*dl/len(h))*0.5
    Hc = np.fft.rfft(h, n) * 10**(Hdb(fr, cut)/20)
    y = np.fft.irfft(np.fft.rfft(x)*Hc, n)
    # ruido coloreado calibrado: SNR0 por subportadora a 3 kHz con H=1
    sig = 10**(-snr0/20)/np.sqrt(NFFT)
    shape = np.sqrt(10**((Ndb(fr)-Ndb(3000))/10))
    y = y + np.fft.irfft(np.fft.rfft(r.normal(0, sig, n))*shape, n)
    # receptor
    R = np.fft.fft(y.reshape(-1, NFFT+CP)[:, CP:], axis=1)[:, ks]
    Hest = (R[:NPIL]/(amp*pil)).mean(0)
    Z = R[NPIL:]/Hest/amp
    errs = tot = 0
    for j, bk in enumerate(b):
        if not bk: continue
        d = qam_demod(Z[:, j], int(bk)); errs += (d != data_bits[j]).sum(); tot += d.size
    rate = b.sum()/TSYM * (50/(50+NPIL))                     # bit/s, con NPIL símbolos de preámbulo cada 50 de datos
    return dict(rate=rate, ber=errs/max(tot, 1), b=b, fk=fk, snr_k=snr_k, nbits=tot)

r = ofdm_link(1875, 6328, 20)
print(f"OFDM en la misma banda que ggwave (1,9–6,3 kHz), SNR0=20 dB: {r['rate']/8:.0f} B/s, BER medida={r['ber']:.2e} sobre {r['nbits']} bits")
""")

code("""
snr0s = np.arange(0, 41, 5)
rows = [ofdm_link(1875, 6328, s, seed=3) for s in snr0s]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.4))
ax[0].plot(snr0s, [r['rate']/8 for r in rows], 'o-', label='OFDM + bit loading (misma banda)')
ax[0].axhline(S0['Bps'], color='C3', ls='--', label='ggwave FAST'); ax[0].axhline(stats('F', SIG['AUDIBLE_FASTEST'])['Bps'], color='C1', ls='--', label='ggwave FASTEST')
ax[0].set_yscale('log'); ax[0].set_xlabel('SNR0 (dB)'); ax[0].set_ylabel('B/s'); ax[0].legend(fontsize=8); ax[0].set_title('Caudal vs SNR')
r20 = rows[4]
ax[1].step(r20['fk']/1000, r20['b'], where='mid'); ax[1].set_xlabel('kHz'); ax[1].set_ylabel('bits por subportadora'); ax[1].set_title('Carga de bits a SNR0 = 20 dB')
plt.show()
print('BER medida (todas las celdas):', ['%.1e' % r['ber'] for r in rows])
print('Notar: BER = 0 significa < 1/nbits, no que sea nula.')
""")

md("""
**Lectura.** En la **misma** banda, OFDM da unos 360–1200 B/s con SNR0 de 10–20 dB, y la ganancia crece con el SNR
(ggwave se queda en 14–25 B/s sin importar cuán limpio esté el canal). A SNR muy bajo, ggwave puede ser mejor: su integración larga
decodifica a SNR donde OFDM sin codificación ya no carga bits. Se resuelve añadiendo codificación de canal (LDPC o convolucional), que se omitió aquí.
""")

md("""
## 5. Todas las mejoras juntas
### 5a. Con ggwave real: FASTEST + dúplex + tres canales a la vez

Tres flujos simultáneos con `FASTEST`: A→B audible (1,9–6,3 kHz), B→A audible desplazado (6,6–11 kHz) y un tercer flujo
ultrasónico (15–19,5 kHz), por ejemplo metadatos o un segundo hilo de conversación.
""")

code("""
m1 = "AB$Necesito una habitacion doble para dos noches, desde el viernes"
m2 = "CD$Tenemos disponibilidad, son 95 euros por noche con desayuno"
m3 = "EF$ctrl: ack, lang=es, fmt=json"
x1 = enc('AUDIBLE_FASTEST', m1)
x2 = fshift(enc('AUDIBLE_FASTEST', m2), 4687.5)
x3 = enc('ULTRASOUND_FASTEST', m3)
Y3 = mix(x1, x2, x3)
rx = [bp(1500, 7000)(Y3), fshift(bp(6300, 11500)(Y3), -4687.5), bp(13000, 21000)(Y3)]
got = dec_many(rx)
print('flujo 1:', got[0] == m1, '| flujo 2:', got[1] == m2, '| flujo 3:', got[2] == m3)
nb_ = [len(m.encode()) for m in (m1, m2, m3)]
dur_seq = sum(len(x)/FS for x in (x1, x2, x3)); dur_par = max(len(x)/FS for x in (x1, x2, x3))
print(f"bytes totales {sum(nb_)} | secuencial {dur_seq:.1f} s ({sum(nb_)/dur_seq:.0f} B/s) | paralelo {dur_par:.1f} s ({sum(nb_)/dur_par:.0f} B/s)")
f, P = welch(Y3, FS, nperseg=4096)
fig, ax = plt.subplots(figsize=(9, 3)); ax.semilogy(f/1000, P/P.max(), lw=1); ax.set_xlim(0, 24); ax.set_ylim(1e-8, 2)
ax.set_xlabel('kHz'); ax.set_title('Tres canales ggwave coexistiendo'); plt.show()
""")

md("""
### 5b. Con OFDM: banda ancha y dúplex FDM

Aquí cada dirección tiene su propia sub-banda, con su propio presupuesto de potencia (son dos transmisores distintos):
- A→B: 300–8500 Hz
- B→A: 9500–19000 Hz
""")

code("""
out = {}
for snr0 in (10, 20, 30):
    a = ofdm_link(300, 8500, snr0, seed=5); b = ofdm_link(9500, 19000, snr0, seed=6)
    w = ofdm_link(300, 19000, snr0, seed=7); n = ofdm_link(1875, 6328, snr0, seed=8)
    out[snr0] = dict(narrow=n, wide=w, A=a, B=b)
    print(f"SNR0={snr0:2d} dB | misma banda: {n['rate']/8:6.0f} B/s | ancha 1 dir: {w['rate']/8:6.0f} B/s | "
          f"dúplex A {a['rate']/8:6.0f} + B {b['rate']/8:6.0f} = {(a['rate']+b['rate'])/8:6.0f} B/s   BER(max)={max(n['ber'],w['ber'],a['ber'],b['ber']):.1e}")

r = out[20]
fig, ax = plt.subplots(figsize=(9, 3.2))
for k, c in (('A','C0'), ('B','C1')):
    ax.step(r[k]['fk']/1000, r[k]['b'], where='mid', color=c, label=f'{k}→{"B" if k=="A" else "A"}')
ax.set_xlabel('kHz'); ax.set_ylabel('bits por subportadora'); ax.set_xlim(0, 24); ax.legend(); ax.set_title('Carga de bits en dúplex FDM (SNR0 = 20 dB)'); plt.show()
""")

md("""
## 6. Resumen comparativo
""")

code("""
S_fast = stats('F', SIG['AUDIBLE_FAST']); S_fst = stats('FS', SIG['AUDIBLE_FASTEST'])
S_us = stats('U', SIG['ULTRASOUND_FAST'])
o = out[20]
rows = [
 ('Base: ggwave FAST, semidúplex',                    S_fast['Bps'],               S_fast['bw'], 'audible'),
 ('1. FASTEST',                                       S_fst['Bps'],                S_fst['bw'], 'audible'),
 ('2. Ultrasonido FAST',                              S_us['Bps'],                 S_us['bw'],  'inaudible'),
 ('3. FDM dúplex (FAST audible + ultrasonido)',       S_fast['Bps']+S_us['Bps'],   S_fast['bw']+S_us['bw'], 'ambos'),
 ('4. OFDM + QAM adaptativa (misma banda, 20 dB)',    o['narrow']['rate']/8,       4453, 'audible'),
 ('Combinado real: 3 canales FASTEST',                3*S_fst['Bps'],              3*S_fst['bw'], 'mixto'),
 ('Combinado OFDM dúplex 0,3–19 kHz (20 dB)',         (o['A']['rate']+o['B']['rate'])/8, 18700, 'mixto'),
]
names = [r[0] for r in rows]; Bps = np.array([r[1] for r in rows]); bw = np.array([r[2] for r in rows])
fig, ax = plt.subplots(1, 2, figsize=(12, 3.8))
y = np.arange(len(rows))[::-1]
ax[0].barh(y, Bps, color=['#888']+['C0']*4+['C2']*2); ax[0].set_yticks(y); ax[0].set_yticklabels(names, fontsize=8); ax[0].set_xscale('log'); ax[0].set_xlabel('caudal agregado (B/s, log)')
for yy, v in zip(y, Bps): ax[0].text(v*1.05, yy, f'{v:.0f}', va='center', fontsize=8)
ax[1].barh(y, bw/NYQ*100, color=['#888']+['C0']*4+['C2']*2); ax[1].set_yticks(y); ax[1].set_yticklabels([]); ax[1].set_xlabel('% del espectro 0–24 kHz ocupado')
plt.tight_layout(); plt.show()
print(f"{'configuración':52s} {'B/s':>7s} {'× base':>8s}")
for n_, v in zip(names, Bps): print(f"{n_:52s} {v:7.0f} {v/Bps[0]:7.1f}×")
""")

md("""
## Conclusiones

1. **`FASTEST`** es gratis y da ~1,8× sin pérdida apreciable de robustez frente a ruido blanco.
2. **Ultrasonido** no acelera nada: mueve la señal a una banda inaudible y libre. Solo es fiable si el hardware llega a ~17 kHz o más.
3. **FDM dúplex** (audible + ultrasonido, o dos canales audibles) deja hablar a los dos agentes a la vez: el intercambio dura `max(tA, tB)` en vez de `tA + tB`, y el caudal agregado se multiplica por el número de canales.
4. **OFDM con carga de bits** es el único cambio que ataca la causa de fondo: ggwave usa unos pocos tonos a un régimen fijo, mientras que el canal admite varios bits por subportadora. Da un orden de magnitud o más, a costa de implementar sincronismo, estimación de canal y codificación (no simulados aquí).
5. **Juntas**, las mejoras de ggwave real (FASTEST + 3 canales FDM) llegan a ~5× el caudal agregado de la base. Añadir OFDM en banda ancha y dúplex lleva el modelo a ~360× (SNR0 = 20 dB), con las reservas del primer apartado: es una cota optimista.

Si lo que importa es el efecto de demostración (el "sonido de módem"), lo más barato es 1 y 3. Si importa de verdad el caudal, hay que reemplazar el códec (4).
""")

nb['cells'] = C
nb.metadata['kernelspec'] = {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'}
nbf.write(nb, 'gibberlink_espectro.ipynb')
