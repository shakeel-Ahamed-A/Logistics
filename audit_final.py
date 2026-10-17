from pathlib import Path
import os,json,csv,xml.etree.ElementTree as ET,collections,re,subprocess,hashlib
import pcbnew as p
R=Path(__file__).parent;O=R/'PCB_Fabrication';K=R/'tools/KiCad'
os.environ['KICAD_DOCUMENTS_HOME']=str(R/'tools/KiCadUser');os.environ['KICAD_CONFIG_HOME']=str(R/'tools/KiCadConfig')
pro=json.loads((O/'SmartLogistics.kicad_pro').read_text())
pro['net_settings']['netclass_patterns']=[{'netclass':'Power','pattern':x} for x in ['/5V*','/3V3*','/*_VCC','/GND']]
(O/'SmartLogistics.kicad_pro').write_text(json.dumps(pro,indent=2))
b=p.LoadBoard(str(O/'SmartLogistics.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()}
manifest=json.loads((O/'Evidence/design_manifest.json').read_text());errors=[];count=0
for c in manifest:
    if not c['fp']:continue
    f=fps[c['ref']]
    for pad in f.Pads():
        n=pad.GetNumber()
        if not n:continue
        expect=c['nets'][n]
        if expect is None:continue
        count+=1
        if pad.GetNetname()!='/'+expect:errors.append([c['ref'],n,expect,pad.GetNetname()])
assert not errors,errors
# Catch accidental joining of independent regulator outputs at netlist level.
assert fps['U1'].FindPadByNumber('3').GetNetCode()!=fps['J2'].FindPadByNumber('18').GetNetCode()
assert fps['J2'].FindPadByNumber('18').GetNetCode()==fps['J3'].FindPadByNumber('1').GetNetCode()
assert fps['J3'].FindPadByNumber('20').GetNetname()=='/SW420_PB12'
assert fps['J4'].FindPadByNumber('5').GetNetname()=='/MPU_VCC'
assert fps['U1'].FindPadByNumber('2').GetNetname()=='/5V_SYS'
drills=collections.Counter()
for f in b.GetFootprints():
    for pad in f.Pads():
        sz=pad.GetDrillSize()
        if sz.x:drills[(round(p.ToMM(sz.x),3),round(p.ToMM(sz.y),3),'NPTH' if pad.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH')]+=1
via=0; tracks=0; widths=collections.Counter(); lengths=collections.defaultdict(float)
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):
        via+=1; d=round(p.ToMM(t.GetDrillValue()),3);drills[(d,d,'PTH via')]+=1
    else:
        tracks+=1;widths[round(p.ToMM(t.GetWidth()),3)]+=1;lengths[t.GetNetname()]+=p.ToMM(t.GetLength())
with (O/'Drill_Size_Audit.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Nominal_finished_X_mm','Nominal_finished_Y_mm','Type','Count']);w.writerows([*k,n] for k,n in sorted(drills.items()))
(O/'Evidence/connectivity_audit.json').write_text(json.dumps({'matched_connected_pads':count,'mismatches':errors,'footprints':len(fps),'track_segments':tracks,'vias':via,'track_width_counts_mm':dict(widths),'total_track_lengths_by_net_mm':lengths,'independent_3v3_outputs_separate':True,'limits':'Checks carrier netlist only, not internal plug-in circuitry or physical hardware.'},indent=2))
# Update pin-coordinate CSV to match final A2 reflow.
rows=list(csv.DictReader((O/'Pin_Mapping.csv').open(encoding='utf-8')))
cs={c['ref']:c for c in manifest}
for row in rows:
    c=cs[row['Reference']]
    for field,axis in [('Schematic_X_mm',0),('Schematic_Y_mm',1)]:
        orig=round(round(c['sch'][axis]/1.27)*1.27,4); dest=round(round(orig*.7/1.27)*1.27,4)
        row[field]=round(float(row[field])+dest-orig,4)
with (O/'Pin_Mapping.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# Export fresh netlist after visual reflow, then rerun actual checks.
cmds=[['sch','export','netlist','--format','kicadxml','-o',str(O/'Evidence/SmartLogistics.net.xml'),str(O/'SmartLogistics.kicad_sch')],['sch','erc','-o',str(O/'ERC_Report.txt'),str(O/'SmartLogistics.kicad_sch')],['pcb','drc','--schematic-parity','--all-track-errors','-o',str(O/'DRC_Report.txt'),str(O/'SmartLogistics.kicad_pcb')]]
logs=[]
for args in cmds:
    pr=subprocess.run([str(K/'bin/kicad-cli.exe'),*args],capture_output=True,text=True); logs.append({'args':args,'exit':pr.returncode,'stdout':pr.stdout,'stderr':pr.stderr});print(pr.stdout)
(O/'Evidence/final_cli_log.json').write_text(json.dumps(logs,indent=2))
print('Connectivity audit:',count,'connected pads match manifest;',tracks,'tracks;',via,'vias;',dict(widths))
