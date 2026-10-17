from pathlib import Path
import pcbnew as p, json, os, collections
ROOT=Path(__file__).parent;OUT=ROOT/'PCB_Fabrication'
os.environ['KICAD_DOCUMENTS_HOME']=str(ROOT/'tools/KiCadUser')
os.environ['KICAD_CONFIG_HOME']=str(ROOT/'tools/KiCadConfig')
def mm(x):return p.FromMM(x)
def v(x,y):return p.VECTOR2I(mm(x),mm(y))
b=p.LoadBoard(str(OUT/'SmartLogistics.kicad_pcb'))
assert p.ImportSpecctraSES(b,str(OUT/'Evidence/SmartLogistics.ses'))
fps={f.GetReference():f for f in b.GetFootprints()}
for g in b.GetDrawings():
    if isinstance(g,p.PCB_TEXT) and g.GetText() in ('REED','BTN1','BTN2'):
        g.SetPosition(v(28,p.ToMM(g.GetPosition().y)-1))
fps['Q2'].Reference().SetPosition(v(102.8,94));fps['Q2'].Reference().SetTextAngle(p.EDA_ANGLE(90,p.DEGREES_T))
def text(s,x,y,size=.8):
    t=p.PCB_TEXT(b);t.SetText(s);t.SetPosition(v(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(mm(.13));t.SetLayer(p.F_SilkS);b.Add(t)
for ref,labels in {'J4':['V','G','C','D','A'],'J5':['V','G','C','D'],'J6':['V','G','D'],'J7':['V','G','TX','RX'],'J8':['V','G','CS','CK','MI','MO'],'J9':['V','G','DO']}.items():
    pos=fps[ref].GetPosition();x,y=p.ToMM(pos.x),p.ToMM(pos.y)
    for i,s in enumerate(labels):text(s,x+3.5,y+i*2.54)
# GND fill on both sides; all islands without electrical connection removed.
gn=b.FindNet('/GND')
for layer in [p.F_Cu,p.B_Cu]:
    z=p.ZONE(b);z.SetLayer(layer);z.SetNetCode(gn.GetNetCode());z.SetLocalClearance(mm(.3));z.SetMinThickness(mm(.25))
    z.SetThermalReliefGap(mm(.3));z.SetThermalReliefSpokeWidth(mm(.4));z.SetPadConnection(p.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
    o=z.Outline();o.NewOutline()
    for x,y in [(20.5,15.5),(129.5,15.5),(129.5,124.5),(20.5,124.5)]:o.Append(mm(x),mm(y))
    b.Add(z)
filler=p.ZONE_FILLER(b);filler.Fill(b.Zones())
p.SaveBoard(str(OUT/'SmartLogistics.kicad_pcb'),b)
stats=collections.defaultdict(lambda:collections.Counter())
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):continue
    stats[t.GetNetname()][str(p.ToMM(t.GetWidth()))]+=1
(OUT/'Evidence/trace_width_audit.json').write_text(json.dumps(dict(stats),indent=2))
positions={f.GetReference():{'x_mm':p.ToMM(f.GetPosition().x),'y_mm':p.ToMM(f.GetPosition().y),'rotation_deg':f.GetOrientationDegrees()} for f in b.GetFootprints()}
(OUT/'Evidence/final_positions.json').write_text(json.dumps(positions,indent=2))
print('Imported routing and filled GND planes. Tracks/vias:',len(b.GetTracks()))
