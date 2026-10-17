"""Provisional carrier. Uses shipped KiCad library geometry; no guessed symbol pins.
Build schematic, export its actual KiCad netlist, then build PCB from that netlist.
"""
from pathlib import Path
import os, re, json, uuid, copy, math, csv, subprocess, xml.etree.ElementTree as ET
ROOT=Path(__file__).parent
OUT=ROOT/'PCB_Fabrication'
K=ROOT/'tools/KiCad'
os.environ['KICAD_DOCUMENTS_HOME']=str(ROOT/'tools/KiCadUser')
os.environ['KICAD_CONFIG_HOME']=str(ROOT/'tools/KiCadConfig')
os.environ['KICAD10_SYMBOL_DIR']=str(K/'share/kicad/symbols')
os.environ['KICAD10_FOOTPRINT_DIR']=str(K/'share/kicad/footprints')
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL,'smartlogistics/provisional/'+s))
def q(s): return json.dumps(str(s),ensure_ascii=False)
def parse(s):
    ts=re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+',s)
    stack=[]; root=None
    for t in ts:
        if t=='(':
            a=[]
            if stack: stack[-1].append(a)
            stack.append(a)
        elif t==')': root=stack.pop()
        else: stack[-1].append(json.loads(t) if t.startswith('"') else t)
    return root
def children(a,k): return [x for x in a if isinstance(x,list) and x[0]==k]
def child(a,k): return next(x for x in a if isinstance(x,list) and x[0]==k)
def dump(a):
    if isinstance(a,list): return '('+' '.join(dump(x) for x in a)+')'
    if re.fullmatch(r'-?\d+(?:\.\d+)?|[a-zA-Z_][a-zA-Z_0-9]*',str(a)): return str(a)
    return q(a)
# All strings may legally be quoted in KiCad, but atom names/numbers remain bare.
libraries={}
def symbol(lib,name):
    if lib not in libraries:
        tree=parse((K/'share/kicad/symbols'/f'{lib}.kicad_sym').read_text(encoding='utf-8'))
        libraries[lib]={x[1]:x for x in children(tree,'symbol')}
    source=copy.deepcopy(libraries[lib][name])
    ext=children(source,'extends')
    if ext:
        base=symbol(lib,ext[0][1])
        props={p[1]:p for p in children(base,'property')}
        props.update({p[1]:p for p in children(source,'property')})
        source=[x for x in base if not(isinstance(x,list) and x[0] in ('property','extends'))]
        source[1]=name
        source.extend(props.values())
    return source
def pins(sym):
    result=[]
    for s in children(sym,'symbol'):
        for p in children(s,'pin'):
            result.append((child(p,'number')[1],*[float(t) for t in child(p,'at')[1:]],p[1],child(p,'name')[1]))
    return result
components=[]
RFP='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal'
CFP='Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm'
EFP='Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'
def hdr(n,socket=False): return ('Connector_PinSocket_2.54mm:PinSocket' if socket else 'Connector_PinHeader_2.54mm:PinHeader')+f'_1x{n:02}_P2.54mm_Vertical'
def add(ref,lib,name,val,nets,sch,pcb,fp,section,dnp=False,notes=''):
    components.append(dict(ref=ref,lib=lib,name=name,value=val,nets={str(k):v for k,v in nets.items()},sch=sch,pcb=pcb,fp=fp,section=section,dnp=dnp,notes=notes,uuid=uid(ref)))
def conn(ref,val,nets,sch,pcb,section,dnp=False,notes='',socket=False):
    add(ref,'Connector_Generic',f'Conn_01x{len(nets):02}',val,dict(enumerate(nets,1)),sch,pcb,hdr(len(nets),socket),section,dnp,notes)
def resistor(ref,value,n1,n2,sch,pcb,section,dnp=False,notes=''):
    add(ref,'Device','R',value,{1:n1,2:n2},sch,pcb,RFP,section,dnp,notes)
def cap(ref,value,net,sch,pcb,section,polar=False):
    add(ref,'Device','C_Polarized' if polar else 'C',value,{1:net,2:'GND'},sch,pcb,EFP if polar else CFP,section)
# POWER: candidate parts, not asserted as the user's existing hardware.
conn('J1','REGULATED 5V INPUT',['5V_IN','GND'],(55,45),(32,112,0),'POWER',notes='5V +/-5%, current-limited source >=1A required; not presently available')
add('Q1','Transistor_FET','AO3401A','AO3401A',{1:'GND',2:'5V_PROT',3:'5V_IN'},(135,45),(43,112,0),'Package_TO_SOT_SMD:SOT-23','POWER',notes='Candidate reverse-polarity MOSFET: G1 S2 D3; drain input, source output. Does not block reverse current from another supply.')
cap('C1','100u 10V','5V_PROT',(215,45),(52,112,0),'POWER',True)
cap('C2','1u X7R 10V','5V_SYS',(295,45),(63,112,0),'POWER')
add('U1','Regulator_Linear','MCP1700x-330xxTO','MCP1700-3302E/TO',{1:'GND',2:'5V_SYS',3:'3V3_AUX'},(375,45),(75,112,0),'Package_TO_SOT_THT:TO-92_Inline_Wide','POWER',notes='New candidate AUX-only LDO; 150mA design ceiling pending final loads and thermal validation')
cap('C3','1u X7R 10V','3V3_AUX',(455,45),(85,112,0),'POWER')
cap('C4','10u 10V','3V3_AUX',(535,45),(97,112,0),'POWER',True)
conn('JP1','MASTER POWER - OPEN',['5V_PROT','5V_SYS'],(615,45),(111,112,0),'POWER',True,'Fit only after identifying Blue Pill regulator. No USB or ST-LINK power while connected.')
cap('C5','100n 10V','3V3_BP',(695,45),(84,84,0),'POWER')
# Header numbering: STM32-base reference top view; pin 1 at SWD end for both rows.
h1=[None,None,None,None,None,'REED_PA1',None,None,'SD_CS_PA4','SD_SCK_PA5','SD_MISO_PA6','SD_MOSI_PA7','BUZZER_PB0','GREEN_PB1','BLUE_PB10','RED_PB11','NRST','3V3_BP','GND','GND']
h2=['3V3_BP','GND','5V_SYS',None,None,'I2C_SDA_PB7','I2C_SCL_PB6','DHT_PB5',None,None,None,None,None,'GPS_TX_PA10','GPS_RX_PA9',None,None,'BUTTON2_PB14','BUTTON1_PB13','SW420_PB12']
conn('J2','BLUE PILL H1 - NOMINAL',h1,(55,125),(74.76,30,0),'BLUE PILL',socket=True,notes='20x2.54; pin1=VBAT at SWD end. User physical fit and orientation UNVERIFIED.')
conn('J3','BLUE PILL H2 - NOMINAL',h2,(135,125),(90,30,0),'BLUE PILL',socket=True,notes='15.24mm from H1 nominal. Pin1=3V3 at SWD end. No carrier AUX rail connection.')
# Candidate module harnesses are carrier-defined, NOT module socket orientations.
conn('J4','MPU HARNESS - VERIFY',['MPU_VCC','GND','I2C_SCL_PB6','I2C_SDA_PB7','MPU_VCC'],(215,125),(118,33,0),'SENSORS',notes='Harness 1=VCC,2=GND,3=SCL,4=SDA,5=AD0. AD0=MPU_VCC (candidate 3.3V). Verify actual MPU core/VLOGIC before enabling. No plug-in footprint claimed.')
conn('JP2','MPU POWER - OPEN',['3V3_AUX','MPU_VCC'],(295,125),(108,33,0),'SENSORS',True)
cap('C6','100n 10V','MPU_VCC',(375,125),(108,41,0),'SENSORS')
conn('J5','RTC HARNESS - VERIFY',['RTC_VCC','GND','I2C_SCL_PB6','I2C_SDA_PB7'],(455,125),(118,53,0),'SENSORS',notes='Remove/disable any battery charger before a CR2032 is fitted. Verify onboard I2C pullups and battery holder underside clearance.')
conn('JP3','RTC POWER - OPEN',['3V3_AUX','RTC_VCC'],(535,125),(108,53,0),'SENSORS',True)
cap('C7','100n 10V','RTC_VCC',(615,125),(108,62,0),'SENSORS')
resistor('R1','4k7 DNP','3V3_AUX','I2C_SCL_PB6',(695,125),(106,73,0),'SENSORS',True,'Populate only if combined module pullups require it')
resistor('R2','4k7 DNP','3V3_AUX','I2C_SDA_PB7',(55,210),(106,78,0),'SENSORS',True)
conn('J6','DHT11 HARNESS - VERIFY',['DHT_VCC','GND','DHT_PB5'],(135,210),(57,65,0),'SENSORS',notes='3-pin module; verify actual pin order. 3.3V operation and module pullup destination pending.')
conn('JP4','DHT POWER - OPEN',['3V3_AUX','DHT_VCC'],(215,210),(47,65,0),'SENSORS',True)
resistor('R3','4k7 DNP','DHT_VCC','DHT_PB5',(295,210),(44,74,0),'SENSORS',True)
cap('C8','100n 10V','DHT_VCC',(375,210),(44,80,0),'SENSORS')
conn('J7','GPS HARNESS - VERIFY',['GPS_VCC','GND','GPS_TX_PA10','GPS_RX_PA9'],(455,210),(57,45,0),'SENSORS',notes='3=GPS TX to MCU RX;4=GPS RX from MCU TX. 5V applies only if actual BREAKOUT input regulator is verified; never bare NEO-6M VCC.')
conn('JP5','GPS 5V CANDIDATE - OPEN',['5V_SYS','GPS_VCC'],(535,210),(47,45,0),'SENSORS',True)
cap('C9','100n 10V','GPS_VCC',(615,210),(45,55,0),'SENSORS')
conn('J8','SD HARNESS - VERIFY',['SD_VCC','GND','SD_CS_PA4','SD_SCK_PA5','SD_MISO_PA6','SD_MOSI_PA7'],(695,210),(57,25,0),'SENSORS',notes='6-pin blue adapter. Candidate power is isolated. Buffer VIH/VIL and MISO voltage not verified. SPI traces provisional; do not energize until audited.')
conn('JP6','SD 5V CANDIDATE - OPEN',['5V_SYS','SD_VCC'],(55,290),(47,25,0),'SENSORS',True)
cap('C10','100n 10V','SD_VCC',(135,290),(44,35,0),'SENSORS')
cap('C11','100u 10V','SD_VCC',(215,290),(34,30,0),'SENSORS',True)
resistor('R4','10k','3V3_BP','SD_CS_PA4',(295,290),(61,84,0),'SENSORS')
conn('J9','SW420 HARNESS - VERIFY',['SW420_VCC','GND','SW420_PB12'],(375,290),(118,91,0),'SENSORS',notes='PB12 is proposed only; firmware previously PB15. Verify comparator operation and output pullup at 3.3V.')
conn('JP7','SW420 POWER - OPEN',['3V3_AUX','SW420_VCC'],(455,290),(108,91,0),'SENSORS',True)
cap('C12','100n 10V','SW420_VCC',(535,290),(108,100,0),'SENSORS')
conn('J10','REED TO GND',['REED_PA1','GND'],(615,290),(29,45,0),'CONTROLS')
conn('J11','BUTTON 1 TO GND',['BUTTON1_PB13','GND'],(695,290),(29,60,0),'CONTROLS')
conn('J12','BUTTON 2 TO GND',['BUTTON2_PB14','GND'],(55,370),(29,75,0),'CONTROLS')
resistor('R5','10k','3V3_BP','REED_PA1',(135,370),(35,45,90),'CONTROLS')
resistor('R6','10k','3V3_BP','BUTTON1_PB13',(215,370),(35,60,90),'CONTROLS')
resistor('R7','10k','3V3_BP','BUTTON2_PB14',(295,370),(35,75,90),'CONTROLS')
for i,(color,net) in enumerate([('GREEN','GREEN_PB1'),('BLUE','BLUE_PB10'),('RED','RED_PB11')]):
    resistor(f'R{8+i}','330',net,f'LED_{color}_A',(375+i*80,370),(46+i*15,94,90),'INDICATORS')
    add(f'D{1+i}','Device','LED',color,{1:'GND',2:f'LED_{color}_A'},(615+i*80 if i<2 else 55,370 if i<2 else 450),(46+i*15,101,0),'LED_THT:LED_D3.0mm','INDICATORS',notes='Candidate 3mm LED; pin1 cathode. Verify chosen LED forward voltage/brightness.')
resistor('R11','680','BUZZER_PB0','BUZZER_BASE',(135,450),(86,94,0),'BUZZER')
resistor('R12','100k','BUZZER_BASE','GND',(215,450),(86,100,0),'BUZZER')
add('Q2','Transistor_BJT','Q_NPN_CBE','P2N2222AG',{1:'BUZZER_LOW',2:'BUZZER_BASE',3:'GND'},(295,450),(96,94,90),'Package_TO_SOT_THT:TO-92_Inline_Wide','BUZZER',notes='Candidate onsemi P2N2222AG C1 B2 E3, not arbitrary 2N2222 substitute. Proposed load <=20mA, verify actual buzzer before fitting link.')
conn('J13','BUZZER HARNESS',['BUZZER_VCC','BUZZER_LOW'],(375,450),(91,103,0),'BUZZER')
conn('JP8','BUZZER 5V - OPEN',['5V_SYS','BUZZER_VCC'],(455,450),(101,106,0),'BUZZER',True)
add('D4','Device','D','1N4007',{1:'BUZZER_VCC',2:'BUZZER_LOW'},(535,450),(102,85,90),'Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal','BUZZER',notes='Flyback cathode pin1 to + buzzer supply. Validate acoustic behavior for passive buzzer.')
conn('J14','TO BLUE PILL SWD CABLE',['SWDIO_PA13','SWCLK_PA14','GND'],(615,450),(79,22,90),'PROGRAMMING',notes='Short cable to existing separate Blue Pill SWD header. Carrier order is NOT Blue Pill 4-pin order. Do not wire its 3.3V power pin.')
conn('J15','STLINK SIGNALS ONLY',['SWDIO_PA13','SWCLK_PA14','GND','NRST'],(695,450),(90,22,90),'PROGRAMMING',notes='No programmer power. Power target externally before connecting signals. Identify debugger model.')
conn('J16','VTREF SENSE ONLY',['3V3_BP','GND'],(55,530),(105,22,90),'PROGRAMMING',True,'For verified genuine debugger VTref input only. Never connect clone 3.3V output. Leave unpopulated by default.')
for i,(net,px) in enumerate([('GND',32),('5V_PROT',42),('3V3_AUX',55),('3V3_BP',68)]):
    add(f'TP{i+1}','Connector','TestPoint',net,{1:net},(135+i*80,530),(px,120,0),'TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm','TEST')
for i,xy in enumerate([(25,20),(125,20),(25,120),(125,120)]):
    add(f'H{i+1}','Mechanical','MountingHole','M3 3.2mm',{},(455+i*80,530),(*xy,0),'MountingHole:MountingHole_3.2mm_M3','MECHANICAL')
for i,net in enumerate(['5V_SYS','GND']):
    add(f'#FLG0{i+1}','power','PWR_FLAG','PWR_FLAG',{1:net},(755,45+i*40),(0,0,0),'','ERC',notes='Source declaration for ERC only, not hardware validation.')
OUT.mkdir(exist_ok=True)
(OUT/'Libraries').mkdir(exist_ok=True)
# Build compact project-specific symbol library from exact installed originals, flatten inheritance.
libdefs={}
for c in components:
    key=c['lib']+'__'+c['name']
    if key not in libdefs:
        s=symbol(c['lib'],c['name']); old=s[1]; s[1]=key
        for sub in children(s,'symbol'):
            suffix=re.search(r'(_\d+_\d+)$',sub[1]).group(1)
            sub[1]=key+suffix
        libdefs[key]=s
    c['key']=key
    assert set(c['nets'])=={p[0] for p in pins(libdefs[key])}, (c['ref'],c['nets'],pins(libdefs[key]))
# Use exact serialization of library structure with required string fields quoted.
STRING_FIELDS={'symbol','property','name','number','lib_id','uuid','footprint','value','reference','path','project','description'}
def emit(a):
    if not isinstance(a,list): return str(a)
    vals=[]
    for i,x in enumerate(a):
        if isinstance(x,list): vals.append(emit(x))
        elif i>0 and (a[0] in STRING_FIELDS or a[0]=='extends'): vals.append(q(x))
        else: vals.append(str(x))
    return '('+' '.join(vals)+')'
libhead='(kicad_symbol_lib (version 20251024) (generator kicad_symbol_editor)\n'
(OUT/'Libraries/Carrier.kicad_sym').write_text(libhead+'\n'.join(emit(v) for v in libdefs.values())+'\n)',encoding='utf-8')
(OUT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Carrier") (type "KiCad") (uri "${KIPRJMOD}/Libraries/Carrier.kicad_sym") (options "") (descr "Exact KiCad 10.0.7 library symbols; inheritance flattened")))')
rootid=uid('root')
parts=[f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(rootid)}) (paper "A1")',
 '(title_block (title "Smart Logistics - PROVISIONAL / DO NOT FABRICATE") (date "2026-10-16") (rev "P0") (company "Blue Pill carrier - module identities and mechanics pending"))',
 '(lib_symbols '+'\n'.join(emit([s[0],'Carrier:'+s[1],*s[2:]]) for s in libdefs.values())+')']
audit=[]
def note(text,x,y,size=1.4):
    parts.append(f'(text {q(text)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {q(uid(text))}))')
note('P0 REVIEW ONLY | Power links JP1-JP8 OPEN | No OLED footprint | Module harness order defined here; verify module end separately.',20,15,2)
note('POWER: 5V source -> reverse polarity FET -> Blue Pill onboard regulator + independent AUX regulator. NEVER JOIN 3V3_BP AND 3V3_AUX.',20,22,1.6)
note('Blue Pill nominal rows: 20 pins, pitch 2.54mm, row spacing 15.24mm. J2/J3 pin 1 at SWD end. Actual board measurement required.',20,75,1.6)
note('I2C: MPU AD0 high, address 0x69; RTC 0x68. Pullups R1/R2 DNP until module pullups audited. Failed MPU/SD tests remain unresolved.',20,165,1.6)
note('Sensor supply links are isolated by default. SD/GPS candidate 5V must NOT be connected until breakout regulators / logic are identified.',20,245,1.6)
note('PB12 SW420 is proposed, not hardware-tested. Older firmware PIN_SW420=PB15; synchronize before bring-up.',20,325,1.6)
note('LEDs have 330-ohm resistors. Buzzer has transistor + flyback diode; candidate load <=20mA / 5V pending actual buzzer specifications.',20,405,1.6)
note('SWD requires J14 cable to the separate Blue Pill SWD header. J15 has NO power output. J16 is unpopulated VTref SENSE ONLY.',20,485,1.6)
for c in components:
    x,y=[round(round(v/1.27)*1.27,4) for v in c['sch']]; pp=pins(libdefs[c['key']]); top=min([y-p[2] for p in pp]+[y])-7
    fpname='Carrier:'+c['fp'].split(':')[1] if c['fp'] else ''
    parts.append(f'(symbol (lib_id {q("Carrier:"+c["key"])}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp {"yes" if c["dnp"] else "no"}) (uuid {q(c["uuid"])})'
       f'(property "Reference" {q(c["ref"])} (at {x} {top} 0) (effects (font (size 1.27 1.27))))'
       f'(property "Value" {q(c["value"])} (at {x} {top-3} 0) (effects (font (size 1.1 1.1))))'
       f'(property "Footprint" {q(fpname)} (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))'
       f'(instances (project "SmartLogistics" (path {q("/"+rootid)} (reference {q(c["ref"])}) (unit 1)))))')
    for num,dx,dy,ang,ptype,pname in pp:
        px,py=round(x+dx,4),round(y-dy,4)
        net=c['nets'][num]
        audit.append([c['ref'],num,pname,ptype,px,py,net or 'NC',c['fp'],c['notes']])
        if net is None:
            parts.append(f'(no_connect (at {px} {py}) (uuid {q(uid(c["ref"]+num+"nc"))}))'); continue
        rad=math.radians(ang); ex,ey=round(px-6.35*math.cos(rad),4),round(py+6.35*math.sin(rad),4)
        parts.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {q(uid(c["ref"]+num+"wire"))}))')
        # Local named nets connect all occurrences on this single-sheet design.
        la=0 if ang in (0,180) else 90
        justify='right' if ang==0 else 'left'
        parts.append(f'(label {q(net)} (at {ex} {ey} {la}) (effects (font (size 1.0 1.0)) (justify {justify} bottom)) (uuid {q(uid(c["ref"]+num+"label"))}))')
parts.append('(embedded_fonts no))')
(OUT/'SmartLogistics.kicad_sch').write_text('\n'.join(parts),encoding='utf-8')
# Copy only the actual used footprints for a self-contained editable project.
fdir=OUT/'Libraries/Carrier.pretty'; fdir.mkdir(exist_ok=True)
for c in components:
    if not c['fp']: continue
    lib,fp=c['fp'].split(':')
    src=K/'share/kicad/footprints'/f'{lib}.pretty'/f'{fp}.kicad_mod'
    assert src.exists(), src
    (fdir/src.name).write_bytes(src.read_bytes())
(OUT/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "Carrier") (type "KiCad") (uri "${KIPRJMOD}/Libraries/Carrier.pretty") (options "") (descr "KiCad 10.0.7 footprints copied without pad geometry changes")))')
project={'meta':{'filename':'SmartLogistics.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_clearance':0.3,'min_track_width':0.4,'min_via_diameter':1.0,'min_through_hole_diameter':0.3,'min_hole_clearance':0.3,'min_copper_edge_clearance':0.5},'defaults':{'board_outline_line_width':0.05}}},'net_settings':{'classes':[{'name':'Default','clearance':0.3,'track_width':0.4,'via_diameter':1.0,'via_drill':0.5,'microvia_diameter':0.3,'microvia_drill':0.1,'diff_pair_width':0.4,'diff_pair_gap':0.3,'diff_pair_via_gap':0.3},{'name':'Power','clearance':0.3,'track_width':0.8,'via_diameter':1.2,'via_drill':0.6,'microvia_diameter':0.3,'microvia_drill':0.1,'diff_pair_width':0.4,'diff_pair_gap':0.3,'diff_pair_via_gap':0.3}],'netclass_patterns':[{'netclass':'Power','pattern':x} for x in ['5V*','3V3*','*_VCC','GND']]}}
(OUT/'SmartLogistics.kicad_pro').write_text(json.dumps(project,indent=2))
with (OUT/'Pin_Mapping.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f); w.writerow(['Reference','Pin','Library_pin_name','Electrical_type','Schematic_X_mm','Schematic_Y_mm','Net','Source_footprint','Notes']);w.writerows(audit)
with (OUT/'BOM.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['Reference','Value_or_candidate_part','Quantity','Footprint','Populate','Status','Notes'])
    for c in components:
        if c['fp']: w.writerow([c['ref'],c['value'],1,'Carrier:'+c['fp'].split(':')[1],'NO / OPEN' if c['dnp'] else 'PROVISIONAL','NOT PURCHASE/ASSEMBLY APPROVED',c['notes']])
(OUT/'Evidence/design_manifest.json').write_text(json.dumps(components,indent=2))
def cli(*args):
    p=subprocess.run([str(K/'bin/kicad-cli.exe'),*map(str,args)],capture_output=True,text=True)
    print(p.stdout,p.stderr);return p
if __name__=='__main__':
    result=cli('sch','export','netlist','--format','kicadxml','--output',OUT/'Evidence/SmartLogistics.net.xml',OUT/'SmartLogistics.kicad_sch')
    if result.returncode: raise SystemExit(result.returncode)
    print('Schematic generated from real symbols; netlist exported by KiCad. Components:',len(components))


