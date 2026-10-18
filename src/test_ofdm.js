const fs=require('fs'); const D=__dirname;
const src=fs.readFileSync(D+'/dsp.js','utf8')+"\nmodule.exports={VOICES,ofdmEncode,ofdmDecode,mixSignals,addNoise,meanPower,roomEcho,signalMetrics,encodeVoice,decodeVoice,set:g=>{G=g}};";
const m={exports:{}}; new Function('module','TextDecoder','TextEncoder',src)(m,TextDecoder,TextEncoder); const T=m.exports, V=T.VOICES;
const msg='Hola, soy un asistente de IA. Quiero reservar una habitacion doble.';
const x=T.ofdmEncode(V.A,msg,null); const sm=T.signalMetrics(x,msg.length);
console.log('limpio:',T.ofdmDecode(V.A,x)===msg,x.info.label,sm.dur.toFixed(3)+'s',sm.Bps.toFixed(0)+' B/s',Math.round(sm.lo)+'-'+Math.round(sm.hi));
for(const echo of [false,true]){
 const row=[];
 for(const snr of [30,24,18,12,8,4,0,-3,-5,-7]){
  let ok=0; const n=6, xs=T.ofdmEncode(V.A,msg,snr);
  for(let i=0;i<n;i++){ let y=xs; if(echo) y=T.roomEcho(y); y=T.addNoise(y,snr,T.meanPower(xs)); if(T.ofdmDecode(V.A,y)===msg) ok++; }
  row.push(snr+'dB['+xs.info.mode+']:'+ok+'/'+n);
 }
 console.log('eco',echo,row.join(' '));
}
// dúplex 3 voces OFDM
const ms={A:'Necesito cambiar la reserva al sabado.',B:'Te ofrezco ademas late checkout a las 14:00.',C:'ctrl: sync t=1729 seq=42'};
const sg={}; for(const k in V) sg[k]=T.ofdmEncode(V[k],ms[k],20);
const mix=T.mixSignals(Object.values(sg)); const rx=T.roomEcho(mix);
console.log('dúplex OFDM',Object.keys(V).map(k=>k+':'+(T.ofdmDecode(V[k],rx)===ms[k])).join(' '));
