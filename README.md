# gibberlink-spectrum-demo

Analysis of how much of the audible spectrum [GibberLink](https://github.com/PennyroyalTea/gibberlink) uses, plus a browser demo of possible improvements. GibberLink is built on [ggwave](https://github.com/ggerganov/ggwave) (data over sound).

**Live demo:** https://och1ai.github.io/gibberlink-spectrum-demo/ (UI in Spanish; click a button first so the browser allows audio)

## What is here

- `index.html`: single-file demo. Three "voices" share the air in separate bands (audible, audible shifted +4687.5 Hz, ultrasound), with a spectrogram, the decoded text and metrics per message. It runs the real ggwave WebAssembly build in the browser and also has a simulated OFDM codec with adaptive bit loading (64-QAM down to repeated BPSK) to compare against ggwave.
- `notebook/gibberlink_espectro.ipynb`: the measurements behind it. It generates signals with the same ggwave settings GibberLink uses (48 kHz, `AUDIBLE_FAST`) and tests four improvements one by one and then together: `FASTEST`, ultrasound, frequency-division duplex, and OFDM. An HTML export is next to it.
- `src/`: DSP and OFDM code (`dsp.js`), the page template, `build.py` to regenerate `index.html`, and a Node test for the OFDM codec.

## Findings

- GibberLink's default protocol puts 99% of its energy in about 4.5 kHz (1.9 to 6.3 kHz) of the 24 kHz available and reaches about 14 B/s, roughly 0.025 bit/s/Hz.
- `FASTEST`, a second band and duplex give about 1.8x to 5x. OFDM with adaptive bit loading is far faster in simulation.

## Limits

Everything runs over an electrical channel model (added white noise, filters, simulated multipath). There is no real speaker or microphone, and the OFDM numbers leave out clock drift, AGC and speaker nonlinearity, so treat them as optimistic.

## Run

```
python3 src/build.py          # rebuild index.html
node src/test_ofdm.js         # OFDM codec test
cd notebook && jupyter nbconvert --to notebook --execute gibberlink_espectro.ipynb
```

The notebook needs `numpy`, `scipy`, `matplotlib` and Node.js.

## License

MIT, see `LICENSE`. Third-party code and licenses are listed in `THIRD_PARTY_NOTICES.md`.
