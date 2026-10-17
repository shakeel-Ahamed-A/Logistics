from pathlib import Path
import re,json
root=Path(__file__).parent/'PCB_Fabrication';path=root/'SmartLogistics.kicad_sch'
manifest={c['ref']:c for c in json.loads((root/'Evidence/design_manifest.json').read_text())}
lines=path.read_text().splitlines();out=[]
for line in lines:
    if line.startswith('(text "P0 REVIEW ONLY'):
        line=re.sub(r'\(at [\d.]+ [\d.]+ 0\)','(at 14 13.2 0)',line)
    elif line.startswith('(text "POWER:'):
        line=re.sub(r'\(at [\d.]+ [\d.]+ 0\)','(at 14 46 0)',line)
    if line.startswith('(symbol (lib_id'):
        ref=re.search(r'\(property "Reference" "([^"]+)"',line)[1];c=manifest[ref]
        xy=re.search(r'\(at (-?[\d.]+) (-?[\d.]+) 0\)',line);x,y=float(xy[1]),float(xy[2])
        if c['name'] in ['R','C','C_Polarized','AO3401A','Q_NPN_CBE']:
            dx=6 if c['name'] in ['R','C','C_Polarized'] else 9
            for name,yy in [('Reference',y-1.8),('Value',y+1.8)]:
                pat=r'(\(property "'+name+r'" "[^"]+" \(at )[-\d.]+ [-\d.]+ 0\)( \(effects \(font \(size [\d.]+ [\d.]+\)\))\)'
                line=re.sub(pat,lambda m:f'{m[1]}{x+dx:.4f} {yy:.4f} 0){m[2]} (justify left))',line)
        elif c['ref']=='U1':
            for name,yy in [('Reference',y+6),('Value',y+9)]:
                line=re.sub(r'(\(property "'+name+r'" "[^"]+" \(at )[-\d.]+ [-\d.]+ 0\)',lambda m:f'{m[1]}{x} {yy} 0)',line)
    out.append(line)
path.write_text('\n'.join(out),encoding='utf-8')
print('Repositioned component fields clear of vertical net labels.')
