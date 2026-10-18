"""Genera ../index.html inyectando ggwave y dsp.js en la plantilla."""
import pathlib
here = pathlib.Path(__file__).parent
t = (here / 'template.html').read_text()
t = t.replace('/*GGWAVE*/', (here.parent / 'vendor' / 'ggwave.js').read_text()).replace('/*DSP*/', (here / 'dsp.js').read_text())
(here.parent / 'index.html').write_text(t)
print('index.html', len(t), 'bytes')
