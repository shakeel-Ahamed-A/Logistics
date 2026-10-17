from pathlib import Path
import json, os, xml.etree.ElementTree as ET
import pcbnew as p
ROOT=Path(__file__).parent; OUT=ROOT/'PCB_Fabrication'
os.environ['KICAD_DOCUMENTS_HOME']=str(ROOT/'tools/KiCadUser')
os.environ['KICAD_CONFIG_HOME']=str(ROOT/'tools/KiCadConfig')
def mm(x):return p.FromMM(x)
def v(x,y):return p.VECTOR2I(mm(x),mm(y))
manifest=json.loads((OUT/'Evidence/design_manifest.json').read_text())
md={c['ref']:c for c in manifest if c['fp']}
for ref,pose in {'R4':(63,80,90),'Q2':(100,96,90),'R11':(85,93,0),'R12':(85,98,0),'J13':(87,105,90),'JP8':(117,107,0),'C5':(81,86,0)}.items():md[ref]['pcb']=pose
netlist=ET.parse(OUT/'Evidence/SmartLogistics.net.xml').getroot()
b=p.BOARD(); b.SetCopperLayerCount(2);b.GetDesignSettings().SetBoardThickness(mm(1.6))
ds=b.GetDesignSettings();ds.m_MinClearance=mm(.3);ds.m_TrackMinWidth=mm(.4);ds.m_CopperEdgeClearance=mm(.5);ds.m_HoleToHoleMin=mm(.3)
ds.m_SilkClearance=mm(.15)
nc=b.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
nc.SetClearance(mm(.3));nc.SetTrackWidth(mm(.4));nc.SetViaDiameter(mm(1));nc.SetViaDrill(mm(.5))
nets={}; padnet={}
for n in netlist.find('nets'):
    name=n.attrib['name'];net=p.NETINFO_ITEM(b,name);b.Add(net);nets[name]=net
    for node in n.findall('node'):padnet[(node.attrib['ref'],node.attrib['pin'])]=name
fps={}
for comp in netlist.find('components'):
    ref=comp.attrib['ref']
    if ref not in md:continue
    c=md[ref];name=comp.findtext('footprint').split(':')[1]
    f=p.FootprintLoad(str(OUT/'Libraries/Carrier.pretty'),name)
    assert f, (ref,name)
    f.SetReference(ref);f.SetValue(c['value']);f.SetFPID(p.LIB_ID('Carrier',name))

    path=comp.find('sheetpath').attrib['tstamps']+c['uuid']
    f.SetPath(p.KIID_PATH(path))
    f.SetPosition(v(*c['pcb'][:2]));f.SetOrientationDegrees(c['pcb'][2])
    f.Reference().SetTextSize(v(.8,.8));f.Reference().SetTextThickness(mm(.13));f.Reference().SetKeepUpright(True)
    f.Value().SetVisible(False)
    if c['dnp']:f.SetAttributes(f.GetAttributes()|p.FP_DNP)
    for pad in f.Pads():
        key=(ref,pad.GetNumber())
        if key in padnet:pad.SetNet(nets[padnet[key]])
        elif pad.GetNumber(): assert c['nets'].get(pad.GetNumber()) is None,key
    b.Add(f);fps[ref]=f
def line(x1,y1,x2,y2,layer,width=.05):
    s=p.PCB_SHAPE();s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(v(x1,y1));s.SetEnd(v(x2,y2));s.SetLayer(layer);s.SetWidth(mm(width));b.Add(s)
for a,z in [((20,15),(130,15)),((130,15),(130,125)),((130,125),(20,125)),((20,125),(20,15))]:line(*a,*z,p.Edge_Cuts)
def text(s,x,y,size=1,layer=p.F_SilkS):
    size=max(.8,size)
    t=p.PCB_TEXT(b);t.SetText(s);t.SetPosition(v(x,y));t.SetTextSize(v(size,size));t.SetTextThickness(mm(.15));t.SetLayer(layer);b.Add(t)
text('SMART LOGISTICS / P0',76,17,1.2)
text('PROVISIONAL - DO NOT FABRICATE',76,123,1)
text('BLUE PILL: SWD END',83,26,0.8)
text('USB / NO POWER',83,81,.8)
text('15.24mm NOMINAL',83,55,.8,p.Dwgs_User)
for a,z in [((70.9,27),(93.9,27)),((93.9,27),(93.9,82)),((93.9,82),(70.9,82)),((70.9,82),(70.9,27))]:line(*a,*z,p.Dwgs_User,.15)
text('Measure actual module / socket height',83,58,.7,p.Dwgs_User)
# Reference footprint board area is not an invented 3D model of the user's module.
for ref,label in [('J4','MPU'),('J5','RTC'),('J6','DHT'),('J7','GPS'),('J8','SD'),('J9','SW420'),('J10','REED'),('J11','BTN1'),('J12','BTN2')]:
    f=fps[ref];x,y=md[ref]['pcb'][:2];text(label,x+5,y-5,.85)
for ref in ['JP1','JP2','JP3','JP4','JP5','JP6','JP7','JP8']:fps[ref].SetLibDescription('OPEN until hardware verified')
text('5V+ GND',33,107,.8)
text('ALL JP LINKS OPEN',91,119,.8)
text('GND',32,117,.7);text('5V',42,117,.7);text('AUX',55,117,.7);text('BP',68,117,.7)
text('G',46,105,.8);text('B',61,105,.8);text('R',76,105,.8)
text('NO PWR',96,18.5,.7)
p.SaveBoard(str(OUT/'SmartLogistics.kicad_pcb'),b)
# Reload with .pro to use actual net classes in Specctra export.
b=p.LoadBoard(str(OUT/'SmartLogistics.kicad_pcb'))
assert p.ExportSpecctraDSN(b,str(OUT/'Evidence/SmartLogistics.dsn'))
# Power widths explicitly transferred into router rules; no reliance on netclass name matching.
dsnpath=OUT/'Evidence/SmartLogistics.dsn';dsn=dsnpath.read_text()
dsn=dsn.replace('(clearance 75 (type smd_smd))','(clearance 300 (type smd_smd))')
power=[name for name in nets if name.lstrip('/').startswith(('5V','3V3')) or name.endswith('_VCC') or name.lstrip('/')=='GND']
idx=dsn.index('  (wiring') if '  (wiring' in dsn else -1
# Class entries belong to network. Insert immediately before its final closing parenthesis.
start=dsn.index('  (network');depth=0;quoted=False;end=None
for i in range(start,len(dsn)):
    ch=dsn[i]
    if ch=='"':quoted=not quoted
    if quoted:continue
    if ch=='(':depth+=1
    if ch==')':
        depth-=1
        if depth==0:end=i;break
dsn=dsn[:end]+'\n    (class POWER '+ ' '.join('"'+n+'"' for n in power)+' (circuit (use_via "Via[0-1]_1000:500_um")) (rule (width 800) (clearance 300)))\n'+dsn[end:]
dsnpath.write_text(dsn)
print('PCB created from KiCad exported netlist:',len(fps),'footprints',len(nets),'nets; nominal 110x110mm, 2 layers')


