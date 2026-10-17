"""Reflow the electrically checked schematic without changing any net connections."""
from pathlib import Path
import re,json,os
import pcbnew as p
ROOT=Path(__file__).parent;OUT=ROOT/'PCB_Fabrication'
os.environ['KICAD_DOCUMENTS_HOME']=str(ROOT/'tools/KiCadUser')
os.environ['KICAD_CONFIG_HOME']=str(ROOT/'tools/KiCadConfig')
# Pin and wire geometry remain unchanged; translate each complete symbol/wire group.
manifest=json.loads((OUT/'Evidence/design_manifest.json').read_text())
path=OUT/'SmartLogistics.kicad_sch';s=path.read_text()
if '(paper "A1")' in s:
    lines=s.splitlines(); result=[]
    positions={c['uuid']:(round(round(c['sch'][0]/1.27)*1.27,4),round(round(c['sch'][1]/1.27)*1.27,4)) for c in manifest}
    dx=dy=0;in_component=False
    for line in lines:
        if line.startswith('(symbol (lib_id'):
            match=re.search(r'\(uuid "([^"]+)"\)',line);ox,oy=positions[match.group(1)]
            nx=round(round(ox*.7/1.27)*1.27,4);ny=round(round(oy*.7/1.27)*1.27,4)
            dx,dy=nx-ox,ny-oy;in_component=True
        if in_component and line.startswith(('(symbol (lib_id','(wire ','(no_connect ','(label ')):
            def move(m):return '('+m[1]+' '+str(round(float(m[2])+dx,4))+' '+str(round(float(m[3])+dy,4))
            line=re.sub(r'\((at|xy) (-?[\d.]+) (-?[\d.]+)',move,line)
        elif line.startswith('(text '):
            line=re.sub(r'\(at ([\d.]+) ([\d.]+)',lambda m:f'(at {float(m[1])*.7:.3f} {float(m[2])*.7:.3f}',line)
        result.append(line.replace('(paper "A1")','(paper "A2")'))
    path.write_text('\n'.join(result),encoding='utf-8')
b=p.LoadBoard(str(OUT/'SmartLogistics.kicad_pcb'))
for f in b.GetFootprints():f.SetAttributes(f.GetAttributes() & ~p.FP_EXCLUDE_FROM_BOM)
p.SaveBoard(str(OUT/'SmartLogistics.kicad_pcb'),b)
print('Reflowed schematic to A2 and aligned board/schematic BOM attributes.')
