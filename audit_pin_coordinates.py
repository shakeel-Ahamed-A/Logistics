"""Check CSV pin coordinates against embedded KiCad library geometry and wires."""
from pathlib import Path
import re,json,csv,math
R=Path(__file__).parent/'PCB_Fabrication';E=R/'Evidence'
tokens=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',(R/'SmartLogistics.kicad_sch').read_text(encoding='utf-8'))
stack=[];root=None
for t in tokens:
    if t=='(':
        node=[]
        if stack: stack[-1].append(node)
        stack.append(node)
    elif t==')': root=stack.pop()
    else:stack[-1].append(json.loads(t) if t.startswith('"') else t)
def children(node,name):return [v for v in node if isinstance(v,list) and v and v[0]==name]
def first(node,name):return children(node,name)[0]
lib={s[1]:s for s in children(first(root,'lib_symbols'),'symbol')}
symbols={first(s,'property')[2]:s for s in children(root,'symbol')}
ends=set()
for w in children(root,'wire'):
    for pt in children(first(w,'pts'),'xy'):ends.add(tuple(round(float(x),4) for x in pt[1:3]))
nc={tuple(round(float(x),4) for x in first(n,'at')[1:3]) for n in children(root,'no_connect')}
rows=list(csv.DictReader((R/'Pin_Mapping.csv').open(encoding='utf-8')));errors=[];checked=0
for row in rows:
    sym=symbols[row['Reference']];definition=lib[first(sym,'lib_id')[1]]
    pins=[pin for sub in children(definition,'symbol') for pin in children(sub,'pin')]
    pin=next(q for q in pins if first(q,'number')[1]==row['Pin'])
    at=list(map(float,first(sym,'at')[1:]));pa=list(map(float,first(pin,'at')[1:]));theta=math.radians(at[2])
    assert not children(sym,'mirror'), 'Mirror handling requires explicit implementation'
    x=round(at[0]+pa[0]*math.cos(theta)-pa[1]*math.sin(theta),4)
    y=round(at[1]-pa[0]*math.sin(theta)-pa[1]*math.cos(theta),4)
    coord=(x,y);csvcoord=(round(float(row['Schematic_X_mm']),4),round(float(row['Schematic_Y_mm']),4))
    if coord!=csvcoord:errors.append([row['Reference'],row['Pin'],'coordinate',coord,csvcoord])
    if coord not in ends and coord not in nc:errors.append([row['Reference'],row['Pin'],'neither wire endpoint nor NC marker',coord])
    checked+=1
(E/'pin_coordinate_audit.json').write_text(json.dumps(dict(checked_symbol_pins=checked,mismatches=errors,method='Embedded KiCad library pin geometry transformed by actual symbol placement; compared with CSV and wire endpoints/NC flags.'),indent=2))
assert not errors,errors
print('PASS:',checked,'symbol pin coordinates and wire/NC endpoints')
