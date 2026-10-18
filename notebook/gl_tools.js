// Puente a ggwave (el mismo ggwave.wasm que usa el repo gibberlink).
//   node gl_tools.js encode PROTOCOLO "mensaje" salida.f32
//   node gl_tools.js decode a.f32 b.f32 ...    -> JSON {archivo: texto|null}
const fs = require('fs');
const origLog = console.log;
console.log = () => {};                      // ggwave es muy ruidoso
const w = process.stdout.write.bind(process.stdout);
process.chdir(__dirname);
require('../vendor/ggwave.js')().then(g => {
  const mk = () => { const p = g.getDefaultParameters(); p.sampleRateInp = 48000; p.sampleRateOut = 48000; p.soundMarkerThreshold = 4; return g.init(p); };
  const [cmd, ...a] = process.argv.slice(2);
  if (cmd === 'encode') {
    const inst = mk();
    const o = g.encode(inst, a[1], g.ProtocolId['GGWAVE_PROTOCOL_' + a[0]], 10); g.free(inst);
    fs.writeFileSync(a[2], Buffer.from(o.buffer, o.byteOffset, o.byteLength));
  } else if (cmd === 'decode') {
    const res = {};
    for (const f of a) {
      const b = fs.readFileSync(f); const inst = mk();
      const r = g.decode(inst, new Int8Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.length))); g.free(inst);
      res[f] = r && r.length ? Buffer.from(r).toString() : null;
    }
    w(JSON.stringify(res) + '\n');
  }
});
