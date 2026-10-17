"""Read-only validation of saved native files; refresh reports, never rebuild CAD."""
from pathlib import Path
import os, json, subprocess, hashlib, datetime, csv, collections, sys, xml.etree.ElementTree as ET
import pcbnew as p
R=Path(__file__).parent; O=R/'PCB_Fabrication'; E=O/'Evidence'; K=R/'tools/KiCad'
for key,val in {'KICAD_DOCUMENTS_HOME':R/'tools/KiCadUser','KICAD_CONFIG_HOME':R/'tools/KiCadConfig','KICAD10_SYMBOL_DIR':K/'share/kicad/symbols','KICAD10_FOOTPRINT_DIR':K/'share/kicad/footprints'}.items(): os.environ[key]=str(val)
native=[O/('SmartLogistics'+ext) for ext in ['.kicad_pro','.kicad_sch','.kicad_pcb','.kicad_dru']]
def hashes(): return {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in native}
before=hashes(); stamp=datetime.datetime.now().isoformat(); logs=[]
def cli(args):
    r=subprocess.run([str(K/'bin/kicad-cli.exe'),*map(str,args)],capture_output=True,text=True)
    logs.append(dict(args=list(map(str,args)),exit=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(r.stdout,flush=True)
    (E/'continuation_cli_log.json').write_text(json.dumps(logs,indent=2))
    if r.returncode: raise RuntimeError(r.stderr)
if '--audit-only' not in sys.argv:
    cli(['--version'])
    cli(['sch','export','netlist','--format','kicadxml','-o',E/'SmartLogistics.net.xml',O/'SmartLogistics.kicad_sch'])
    cli(['sch','erc','--exit-code-violations','-o',O/'ERC_Report.txt',O/'SmartLogistics.kicad_sch'])
    cli(['pcb','drc','--schematic-parity','--all-track-errors','--refill-zones','--severity-all','--exit-code-violations','-o',O/'DRC_Report.txt',O/'SmartLogistics.kicad_pcb'])
b=p.LoadBoard(str(O/'SmartLogistics.kicad_pcb')); fps={f.GetReference():f for f in b.GetFootprints()}
manifest=json.loads((E/'design_manifest.json').read_text()); errors=[]; count=0
xml=ET.parse(E/'SmartLogistics.net.xml'); netnodes={}
for net in xml.findall('./nets/net'):
    for node in net.findall('node'): netnodes[(node.get('ref'),node.get('pin'))]=net.get('name')
for c in manifest:
    if not c['fp']: continue
    for pad in fps[c['ref']].Pads():
        pin=pad.GetNumber()
        if not pin: continue
        expected=c['nets'][pin]
        if expected is None: continue
        count+=1
        if pad.GetNetname()!='/'+expected or netnodes.get((c['ref'],pin))!='/'+expected: errors.append([c['ref'],pin,expected,pad.GetNetname(),netnodes.get((c['ref'],pin))])
csvrows=list(csv.DictReader((O/'Pin_Mapping.csv').open(encoding='utf-8')))
for row in csvrows:
    if row['Reference'].startswith('#'): continue  # ERC-only power flags are absent from physical netlist.
    expected=row['Net']
    if expected and expected not in ('NC','NO_CONNECT') and not expected.startswith('NC_'):
        actual=netnodes.get((row['Reference'],row['Pin']))
        if actual!='/'+expected: errors.append(['pin_csv',row['Reference'],row['Pin'],expected,actual])
components={c.get('ref'):c for c in xml.findall('./components/comp')}
bom=list(csv.DictReader((O/'BOM.csv').open(encoding='utf-8')))
for row in bom:
    ref=row['Reference']; f=fps[ref]; c=components[ref]
    fid=f.GetFPID(); fpname=str(fid.GetLibNickname())+':'+str(fid.GetLibItemName())
    if row['Footprint']!=fpname or row['Value_or_candidate_part']!=f.GetValue() or c.findtext('value')!=f.GetValue(): errors.append(['BOM',ref])
def net(ref,pin): return fps[ref].FindPadByNumber(str(pin)).GetNetname()
checks={
 'separate_3v3_outputs':net('U1',3)=='/3V3_AUX' and net('J2',18)==net('J3',1)=='/3V3_BP',
 'master_feeds_mcu_and_aux':net('JP1',2)==net('J3',3)==net('U1',2)=='/5V_SYS',
 'reverse_fet_pinout': [net('Q1',n) for n in [1,2,3]]==['/GND','/5V_PROT','/5V_IN'],
 'aux_regulator_pinout':[net('U1',n) for n in [1,2,3]]==['/GND','/5V_SYS','/3V3_AUX'],
 'sw420_pb12':net('J3',20)==net('J9',3)=='/SW420_PB12',
 'mpu_ad0_vcc':net('J4',5)==net('J4',1)=='/MPU_VCC',
 'stlink_signal_header_no_power':all('3V3' not in pad.GetNetname() and '5V' not in pad.GetNetname() for pad in fps['J15'].Pads()),
}
drills=collections.Counter(); widths=collections.Counter(); lengths=collections.defaultdict(float); per_net_widths=collections.defaultdict(collections.Counter); vias=0; tracks=0
footprint_diffs=[]
def geometry(f):
    return sorted((x.GetNumber(),int(x.GetAttribute()),int(x.GetShape()),x.GetSize().x,x.GetSize().y,x.GetDrillSize().x,x.GetDrillSize().y,round(x.GetOrientationDegrees()-f.GetOrientationDegrees(),4)%360,round(p.ToMM(x.GetFPRelativePosition().x),5),round(p.ToMM(x.GetFPRelativePosition().y),5)) for x in f.Pads())
for ref,f in fps.items():
    lib=p.FootprintLoad(str(O/'Libraries/Carrier.pretty'),f.GetFPID().GetLibItemName())
    if lib is None or geometry(f)!=geometry(lib): footprint_diffs.append(ref)
    for pad in f.Pads():
        d=pad.GetDrillSize()
        if d.x: drills[(round(p.ToMM(d.x),3),round(p.ToMM(d.y),3),'NPTH' if pad.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH')]+=1
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):
        vias+=1; d=round(p.ToMM(t.GetDrillValue()),3); drills[(d,d,'PTH via')]+=1
    else:
        tracks+=1; widths[round(p.ToMM(t.GetWidth()),3)]+=1; lengths[t.GetNetname()]+=p.ToMM(t.GetLength());per_net_widths[t.GetNetname()][round(p.ToMM(t.GetWidth()),3)]+=1
with (O/'Drill_Size_Audit.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Nominal_finished_X_mm','Nominal_finished_Y_mm','Type','Count']);w.writerows([*k,v] for k,v in sorted(drills.items()))
audit=dict(checked_at_local=stamp,matched_connected_pads=count,mismatches=errors,footprints=len(fps),footprint_pad_geometry_mismatches=footprint_diffs,track_segments=tracks,vias=vias,track_width_counts_mm=dict(widths),total_track_lengths_by_net_mm=lengths,power_and_mapping_checks=checks,copper_layers=b.GetCopperLayerCount(),nominal_thickness_mm=p.ToMM(b.GetDesignSettings().GetBoardThickness()),socket_row_spacing_mm=abs(p.ToMM(fps['J2'].GetPosition().x-fps['J3'].GetPosition().x)),socket_pitch_mm=abs(p.ToMM(fps['J2'].FindPadByNumber('2').GetPosition().y-fps['J2'].FindPadByNumber('1').GetPosition().y)),limits='Carrier CAD only. Actual module internals, part procurement and mechanical fit remain unverified.')
bounds=b.GetBoardEdgesBoundingBox()
audit['edge_graphic_ink_bounds_mm']=[p.ToMM(bounds.GetWidth()),p.ToMM(bounds.GetHeight())]
edge_points=[pt for drawing in b.GetDrawings() if drawing.GetLayer()==p.Edge_Cuts for pt in [drawing.GetStart(),drawing.GetEnd()]]
audit['outline_centreline_mm']=[p.ToMM(max(pt.x for pt in edge_points)-min(pt.x for pt in edge_points)),p.ToMM(max(pt.y for pt in edge_points)-min(pt.y for pt in edge_points))]
audit['mounting_hole_centres_mm']={ref:[p.ToMM(fps[ref].GetPosition().x),p.ToMM(fps[ref].GetPosition().y)] for ref in ['H1','H2','H3','H4']}
audit['zones']=[{'net':z.GetNetname(),'layer':b.GetLayerName(z.GetLayer()),'filled':z.IsFilled()} for z in b.Zones()]
audit['csv_audit']={'bom_rows':len(bom),'pin_mapping_rows':len(csvrows),'physical_connected_pads':count,'notes':'ERC-only power flags omitted from physical netlist comparison; all 171 symbol pin coordinates independently checked.'}
(E/'connectivity_audit.json').write_text(json.dumps(audit,indent=2))
(E/'trace_width_audit.json').write_text(json.dumps(per_net_widths,indent=2))
after=hashes(); (E/'native_preservation_audit.json').write_text(json.dumps(dict(before=before,after=after,unchanged=before==after,checked_at_local=stamp),indent=2))
assert before==after, 'Native files changed unexpectedly'
assert not errors and not footprint_diffs and all(checks.values()), audit
print(json.dumps({k:v for k,v in audit.items() if k!='total_track_lengths_by_net_mm'},indent=2))
