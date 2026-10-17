from pathlib import Path
import csv,json,hashlib,xml.etree.ElementTree as ET
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.units import mm
from pypdf import PdfReader,PdfWriter
ROOT=Path(__file__).parent;OUT=ROOT/'PCB_Fabrication'
def write(name,text): (OUT/name).write_text(text.strip()+'\n',encoding='utf-8')
write('README_FIRST.md','''# PROVISIONAL DESIGN P0 - DO NOT FABRICATE

Evidence-Grounded Smart Package Monitoring and Handling-Event Reconstruction System
Prepared 16 October 2026 for the 21-22 October college review.

This is an editable, electrically connected KiCad carrier project, not an SVG substitute. The board has two 20-pin Blue Pill sockets, carrier-defined sensor harness connectors, a proposed power circuit, transistor buzzer driver, indicators, and test points. Plug-in modules other than the Blue Pill are mounted externally with short secured harnesses. Their physical plug-in/socket orientations and mounting holes are NOT represented as verified.

The user's original September project was read, copied into Evidence, and left untouched. DeepSeek/Gemini reviews, hardware photographs, the earlier SVG and preliminary PCB package have NOT been supplied or inspected. No present hardware was tested. MPU communication and SD initialization failures remain unresolved.

Open SmartLogistics.kicad_pro in KiCad 10.0.7 or later. Libraries are local and portable. The 3D rendering shows generic carrier components only; it cannot prove Blue Pill/module clearance. JP1 is the master supply link. JP2-JP8 are module supply commissioning links. All are OPEN/unpopulated in P0. R1/R2/R3 pull-ups and J16 VTref are also unpopulated pending identification. These links disconnect VCC only, not signal pins: keep modules disconnected while their supply links are open. Never hot-plug or change links with power applied.

ERC_Report.txt and DRC_Report.txt are actual KiCad outputs. DRC was run with schematic parity. See Validation_Summary.txt for the final checked state and limitations. Passing these checks does not resolve module voltage thresholds, real mechanical fit, source selection or prior failed sensor tests.

Gerbers/, Drill_Files/ and PCB_Fabrication_SHOP.zip are intentionally withheld until release gates pass. Do not send the native PCB or preview images to a shop for manufacture. Fabrication_Instructions.txt is a QUOTATION/REVIEW specification only.

Review Power_Design.md and Verification_Required.csv first. Assembly_Drawing.pdf includes the actual layout, a 1:1 Blue Pill socket-fit coupon and a carrier harness table. Print the fit coupon at 100% with scaling disabled and verify its 50 mm calibration bar before comparing hardware.
''')
write('Power_Design.md','''# Proposed power circuit - analysis only, not electrical approval

No suitable regulated 5V source is currently identified. ST-LINK 3.3V output and a nominal 3.7V lithium cell are not the design's power source. Never connect the lithium cell directly to a 3.3V net, or assume a charger board provides a regulated 5V output.

## Topology and candidate new parts
J1 accepts a regulated, current-limited 5.0V +/-5% source. Procurement target: at least 1A continuous with sufficient SD inrush capability. Identify the actual source, wiring polarity, short-circuit protection and measured load regulation before adoption. A bench supply is appropriate for controlled bring-up; no purchase or battery converter choice is approved here.

Q1 is proposed AO3401A reverse-polarity protection: pin 3 D to 5V_IN, pin 2 S to 5V_PROT, pin 1 G to GND. Its body diode initially conducts from input to output in the correct polarity. JP1 then feeds 5V_SYS, which supplies both the Blue Pill 5V pin and U1, plus the candidate GPS/SD/buzzer links. A single P-channel reverse-polarity FET does NOT isolate another power source driving backward. Blue Pill USB power, debugger power and separate module supplies must remain disconnected. The external source must provide current limiting; there is no carrier fuse or battery charger.

U1 is a new candidate MCP1700-3302E/TO, not an identification of the existing Blue Pill regulator. TO-92 pins are 1 GND, 2 VIN, 3 VOUT. U1 powers 3V3_AUX only. The Blue Pill's onboard regulator powers 3V3_BP and MCU loads only. The two regulator outputs are never joined. The Blue Pill regulator's identity, input range, dropout and thermal capability remain a release blocker. See the original chip manufacturer's datasheet, not a clone-board sales title.

Sources: [AO3401A manufacturer datasheet](https://www.aosmd.com/sites/default/files/res/data_sheets/AO3401A.pdf), [MCP1700 manufacturer datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/MCP1700-Data-Sheet-20001826F.pdf).

## Preliminary load allocations
These are engineering allowances, NOT measured currents or guaranteed maxima of unidentified modules. Recalculate with actual parts and card peak current.

| Load | Proposed branch | Reserved current |
|---|---|---:|
| Blue Pill, MCU, onboard loads, three LEDs, GPIO loads | 5V_SYS -> onboard LDO | 100 mA |
| NEO-6M breakout including antenna/indicator allowance | candidate 5V_SYS | 80 mA |
| Blue SD adapter plus selected card, write/startup allowance | candidate 5V_SYS | 400 mA |
| MPU6050 breakout | AUX | 20 mA |
| RTC breakout | AUX | 10 mA |
| DHT11 module | candidate AUX | 5 mA |
| SW420 comparator module | candidate AUX | 20 mA |
| Buzzer | candidate 5V_SYS | 20 mA |
| **Sum** | | **655 mA** |
| 25% sizing allowance | | **819 mA** |

ST's MCU table gives 50.3mA at 72MHz, all peripherals enabled, 105C characterization condition; this is a chip figure, not total Blue Pill current. u-blox lists 67mA for supply sizing of the receiver; the complete breakout and antenna can add load. SD's 400mA allowance requires the actual card and interface specifications; it is not proof that 1A is sufficient under all transient conditions.
[STM32F103 datasheet](https://www.st.com/resource/en/datasheet/stm32f103c8.pdf), [NEO-6 datasheet](https://content.u-blox.com/sites/default/files/products/documents/NEO-6_DataSheet_(GPS.G6-HW-09005).pdf).

## Regulator and distribution calculations
AUX budget is 55mA. U1 has a 250mA rated output, but this draft imposes a 150mA planning ceiling pending enclosure temperature and final loads. Nominal AUX dissipation: (5.0-3.3)*0.055 = 0.0935W. Conservative ceiling example: (5.25-3.201)*0.150 = 0.307W. Using the datasheet's 92C/W TO-92 test-board value gives 28.3C rise, or 78.3C junction at an ASSUMED 50C ambient. That value was characterized on a 4-layer test board; it does not validate this 2-layer board or a sealed package. Measure temperatures and retain margin below 125C operating junction limit. If effective thermal resistance were 200C/W, the same ceiling would give 111.5C at 50C ambient; reduce load or change regulator if necessary.

MCP1700 maximum specified dropout is 350mV at its rated load for this voltage class. A preliminary 4.6V minimum at U1 leaves 4.6-3.399-0.350 = 0.851V headroom. Confirm actual minimum rail during SD writes and source transients. This calculation does not verify the SD or Blue Pill onboard LDOs.

Q1 has a manufacturer maximum RDS(on) of 85 milliohms at -2.5V gate drive, 25C. At 0.819A, its calculated drop is 70mV and loss 57mW using that bound; hot resistance and actual copper thermal performance still require verification. At 1A the corresponding values are 85mV/85mW. Correct-polarity steady-state gate drive is near -5V, inside its +/-12V gate limit.

For 1oz copper (35um nominal), a 100mm long 0.8mm trace has roughly R = 1.724e-8*0.1/(0.0008*35e-6) = 0.0616 ohm at 20C. At 0.819A that is 50mV drop / 41mW distributed heat. This supports short 0.8mm power routing as a preliminary choice, not a certified ampacity or thermal result. Include connector, jumper, cable and hot-copper resistance in the final budget. Confirm SD adapter minimum VIN against the measured voltage at J8, not just the source rating.

C2/C3 are proposed 1uF X7R 10V local input/output bypasses, following U1's datasheet application. Select real radial capacitors whose effective capacitance and lead/body geometry meet the requirement; nominal capacitance alone is insufficient. C1 and C11 provide proposed 100uF bulk storage; C4 adds 10uF on AUX, and C5-C10/C12 provide local 100nF bypassing. Actual capacitance, ESR, inrush and SD rail droop remain to be validated. Capacitor body/lead dimensions are BOM release gates.

## Module electrical gates
- MPU: previous communication failed. Verify HW-123B/GY-521 regulator, actual core/VLOGIC voltage and pull-ups. JP2 proposes 3.3V at the module VCC. J4 pin 5 AD0 is tied to MPU_VCC, so the intended AD0 high is 3.3V after JP2 is fitted. Confirm that the resulting AD0 voltage is allowed by that breakout's actual VLOGIC. Address 0x69 is intended, not observed.
- RTC: run the DS3231 chip at 3.3V so its 0.7*VCC input-high requirement is compatible with the 3.3V I2C bus. The chip supports 2.3-5.5V; the breakout battery charger, EEPROM and pullups are not established. Identify CR2032 versus rechargeable battery. Disable any charging path before using a primary cell; do not charge it. Verify holder underside clearance. [DS3231 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf).
- DHT11: this is a three-pin MODULE, not a bare four-pin footprint. Manufacturer documentation for one DHT11 revision specifies 3.3-5.5V. A nominal 3.3V regulator can fall below 3.3V at tolerance; therefore JP4's candidate 3.3V supply is NOT yet guaranteed. Identify the sensor revision and module pull-up circuitry; a changed supply/interface circuit may be required. R3, if needed, pulls DATA to DHT_VCC. Do not move it to 5V without an interface audit. [Aosong DHT11 manual](https://www.aosong.com/userfiles/files/media/DHT11-V1_3%E8%AF%B4%E6%98%8E%E4%B9%A6%EF%BC%88%E8%AF%A6%E7%BB%86%E7%89%88%EF%BC%89.pdf).
- GPS: the receiver itself is not a 5V part. JP5 proposes 5V only to a verified breakout regulator input. Its UART must remain compatible with 3.3V STM32 GPIO. Identify antenna/backup circuitry and any UART translation.
- SD: identify both regulator and interface IC, VCC limits, buffer supply, VIH/VIL for CS/SCK/MOSI, and MISO VOH at STM32 PA6. A module failing at 3.3V may lack regulator headroom, but that is not a diagnosis. Some 5V-powered buffers do not reliably accept 3.3V highs. Neither a 5V jumper nor additional level shifting is approved until this is checked.
- SW420: establish comparator operation at 3.3V and where DO is pulled up. PB12 is proposed, not tested. Do not power an unknown 5V-output module into the board.
- OLED: omitted. Firmware found uses LiquidCrystal_I2C at 0x27. User reports possible SSD1306 I2C, but supply and physical pin order are unconfirmed. No four-pin orientation has been inferred.

## Pull-ups, outputs and programming
R1/R2 are DNP until all existing I2C pullups are measured. Use parallel resistance, not the value on a single module: at 3.399V, Rmin approximately (3.399-0.4)/3mA = 1.00kohm for a 3mA sink budget. With 200pF assumed bus capacitance and 100kHz operation, a 4.7kohm pullup gives tr approximately 0.8473*4700*200pF = 0.80us. Actual capacitance and rise time need measurement. The old firmware sets 100kHz. No pullup may reach 5V. Keep the MCU and all connected modules powered together; open supply links are for unpowered assembly configuration, not live isolation.

R5/R6/R7 provide 10kohm pullups to the MCU rail for reed/buttons. The LEDs each have 330ohm. Illustrative red LED worst-case calculation with 3.6V supply, 1.6V VF and 1% low resistance: 2.0/326.7 = 6.12mA, below an 8mA GPIO drive design target. Verify actual LED VF and brightness, especially blue/green at 3.3V. 3.6V is a conservative calculation limit, not the intended rail setting.

Q2 is candidate onsemi P2N2222AG, pins 1 C, 2 B, 3 E. Do not substitute a differently pinned 2N2222. R11=680ohm limits base current; R12=100kohm holds it off at reset. Assuming MCU VOH >=2.9V and VBE <=1.2V, base current >=(2.9-1.2)/686.8 = 2.48mA. Forced beta 10 supports a proposed <=20mA buzzer design target; this is a design assumption pending measurement. D4 cathode goes to BUZZER_VCC and anode to BUZZER_LOW. Confirm buzzer type, voltage, current and acoustic behavior; the old passive-buzzer test does not establish safe direct GPIO drive. [P2N2222A datasheet](https://www.onsemi.com/pdf/datasheet/p2n2222a-d.pdf).

J14 must cable to the Blue Pill's separate SWD header, since PA13/PA14 are absent from its two 20-pin rows. J15 carries SWDIO, SWCLK, GND, NRST, with no power output. J16 is unpopulated and for a verified VTref INPUT only; an ST-LINK clone's 3.3V OUTPUT is not VTref. Power the complete target before connecting debugger signals and disconnect debugger signals before removing target power. No live USB power or external sensor power. This avoids intentional supply backfeed; startup/power-off behavior still requires a scope check. [ST-LINK/V2 manual](https://www.st.com/resource/en/user_manual/um1075-stlink-v2-in-circuit-debugger-stlink-v2-1-stlink-v2-ct-stlink-v3-pg00061083.pdf).
''')
write('Fabrication_Instructions.txt','''STATUS: PROVISIONAL P0 - QUOTATION ONLY - DO NOT FABRICATE
Project: Smart Logistics Blue Pill carrier
Target college review: 21-22 October 2026

Proposed shop specification (not a manufacturing order):
- Quantity: 2 prototype boards, one assembled and one spare.
- Outline: 110.00 x 110.00 mm rectangle.
- Layers: 2 copper, plated-through holes required.
- Material/thickness: FR-4, nominal 1.6 mm.
- Copper: proposed 1 oz / 35 um both sides.
- Mask: green solder mask both sides, untented component holes; confirm via tenting policy.
- Legend: white top silkscreen; smallest present text 0.8 mm, stroke 0.13 mm. Confirm readability/capability.
- Finish: proposed lead-free HASL; quote alternatives if unavailable.
- Track widths: 0.4 mm signals, 0.8 mm power in current layout.
- Copper clearance: minimum 0.3 mm; copper to board edge minimum 0.5 mm.
- Vias: 1.0 mm copper diameter / 0.5 mm finished drill in current routing.
- Header/socket holes: 1.0 mm nominal with 1.7 mm pads (0.35 mm nominal radial annulus).
- Other component holes: see Drill_Size_Audit.csv; actual component leads still require confirmation.
- Mounting: four 3.2 mm non-plated holes, centres 5 mm from each edge; hole spacing 100 x 100 mm.
- No internal slots or castellations. No fine-pitch MCU assembly.
- Assembly mainly through-hole; one AO3401A SOT-23 candidate requires surface-mount hand soldering.

Ask the shop to confirm: two-sided copper WITH plated-through holes; 0.3 mm clearance;
0.4 mm signal tracks; 0.5 mm finished via drill; annular-ring tolerance;
all finished component hole sizes; mask and silk capability; material/copper tolerances;
electrical bare-board testing; price for two boards; and committed urgent turnaround.
Do not convert this to a non-plated board without redesigning and reviewing all vias and top-side solder access.

Release gate:
Resolve every BLOCKED item in Verification_Required.csv, confirm the real power and module
interfaces, verify a 1:1 mechanical fit, revise the design as needed, and repeat ERC, full DRC
with schematic parity, 2D/3D, connectivity and Gerber/drill review on that final revision.
Only then export standard RS-274X Gerbers (F.Cu/B.Cu/F.Mask/B.Mask/F.Silkscreen/Edge.Cuts)
and Excellon PTH + NPTH drills into Gerbers/ and Drill_Files/.
Inspect board outline, drill registration, scale, layer alignment and polarity in a Gerber viewer.
Create PCB_Fabrication_SHOP.zip from ONLY the reviewed Gerber/drill files and final shop notes.
P0 has no approved Gerber, Excellon or shop ZIP. Native files and images are not fabrication approval.
''')
write('Firmware_Required_Changes.txt','''Firmware synchronization only; original firmware was NOT modified.
Source: Evidence/SmartLogistics_2026-09-16.ino
1. Line 33: change #define PIN_SW420 PB15 to #define PIN_SW420 PB12.
   PB12 is proposed and has NOT passed hardware testing. Verify SW420 polarity/output level.
2. Line 22: use #define USE_LCD 0 for this carrier; no character LCD is provided.
   Do not substitute an OLED driver/address until exact display hardware is confirmed.
3. Line 499 already selects PB7 SDA/PB6 SCL and 100 kHz. Keep for initial validation.
4. Preserve PA4..PA7 SPI; verify actual SD module interface before retrying initialization.
5. Buzzer uses a low-side transistor: high PB0 enables it. Actual active/passive type still pending.
No firmware compilation, programming or hardware sensor pass was performed in this task.
''')
checks=[
('B01','BLOCKED','Blue Pill mechanical','Measure row-centre spacing; 19 pitch intervals end-to-end; board W/L; socket height; protruding pins; USB and SWD projection.','Nominal 15.24mm rows; 2.54mm pitch; actual unmeasured'),
('B02','BLOCKED','Blue Pill orientation/pinout','Verify VBAT at J2 pin1 and 3V3 at J3 pin1 at SWD end; verify all 40 pin labels and 5V/3V3/GND continuity with power OFF.','Generic reference only; not user board'),
('B03','BLOCKED','Blue Pill regulator','Read full regulator marking; obtain actual datasheet and board circuit; validate 5V input and 100mA reserved load thermal/dropout.','No AMS1117 assumption'),
('B04','BLOCKED','5V source','Identify source model, regulation, current limit, connector/cable polarity and >=1A capability; measure voltage/inrush/transients at load.','No regulated 5V source presently confirmed'),
('B05','BLOCKED','microSD','Read regulator/interface IC markings; document all six physical pins; get adapter schematic and card peak-current spec; verify input VIH and MISO voltage.','Initialization previously failed at 3.3V; no diagnosed cause'),
('B06','BLOCKED','MPU6050','Identify regulator/core VLOGIC and all 8 header pins; verify allowed VCC/AD0; measure pullups; confirm 0x69 with actual hardware.','Communication previously failed'),
('B07','BLOCKED','DS3231','Identify exact breakout, VCC range, header order, pullups, EEPROM, battery type and charging circuit.','No primary-cell charging permitted'),
('B08','BLOCKED','DHT11 module','Identify 3-pin order, actual minimum supply and DATA pullup destination; resolve 3.3V regulator tolerance versus sensor minimum.','May require changed supply/level interface'),
('B09','BLOCKED','GPS','Identify breakout regulator/VCC range; UART thresholds/voltages; connector order; current including antenna.','Bare NEO-6M cannot receive 5V'),
('B10','BLOCKED','SW420','Identify comparator and pullup source; confirm operation at candidate 3.3V and DO voltage; document three-pin order.','PB12 proposed; no hardware pass'),
('B11','BLOCKED','Buzzer','Measure/rate operating voltage and current; identify active/passive and piezo/magnetic; confirm <=20mA candidate load or redesign driver.','Earlier PB0 operation is not an electrical rating'),
('B12','BLOCKED','Purchased components','Verify exact socket/header, capacitor body/lead sizes, transistor orientation, and AO3401A package before BOM release.','Library footprint is real; purchased component fit not yet proven'),
('B13','BLOCKED','Shop capability','Confirm 2-layer plated holes, 0.3mm clearance, all finished drill sizes, annular rings, mask/silk, copper weight and turnaround.','Two-board quantity proposed'),
('P01','PENDING','OLED','Identify exact display, controller/interface, supply and physical pin order; then add a connector if required.','Intentionally omitted'),
('P02','PENDING','Firmware','Synchronize PB15->PB12 and disable character LCD; validate integrated firmware after electrical checks.','No extensive firmware edits'),
('P03','PENDING','Mechanical retention','Choose enclosure and standoffs; secure external modules/cables; rigidly fix MPU orientation for event interpretation.','Only carrier mounting holes are designed'),
('P04','PENDING','Power sequencing and I2C','Verify all modules powered with MCU, no pullup >3.3V, no phantom powering at startup/shutdown, equivalent pullup resistance and rise time.','JP links are not signal isolation'),
('P05','PENDING','ST-LINK','Identify exact debugger; distinguish 3.3V output from VTref input; leave J16 unpopulated for clone.','Use external target supply plus SWD/GND only'),
('P06','PENDING','Hardware validation','Measure rails and currents with current limiting; test SD writes, MPU, GPS, RTC, DHT and SW420 independently; record real results.','No present hardware access'),
('P07','PENDING','Manufacturing export','After blockers resolved: final checks, export/inspect Gerber and Excellon, then create SHOP.zip.','Withheld for P0'),
]
with (OUT/'Verification_Required.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['ID','Status','Item','Exact evidence required','Current evidence']);w.writerows(checks)
write('Libraries/README.md','''Symbols and footprints originate from the official KiCad 10.0.7 Windows package, SHA256 CE3881B6A9188EB34AC1EBAAEC7651149E8A025206410ADDFB11A1A9656ECF95, signature validated as KICAD SERVICES CORPORATION.
Symbol inheritance was flattened; pin types, numbering and coordinates retained. Footprint pad and drill geometry retained. Local 3D paths replace standard install paths. Generic 3D models do not represent the user's plug-in modules.
KiCad library license: https://www.kicad.org/libraries/license/
Original libraries: https://gitlab.com/kicad/libraries
Blue Pill reference pin orientation: https://stm32-base.org/boards/STM32F103C8T6-Blue-Pill.html
The nominal 15.24mm spacing comes from the user's provisional specification, not a verified measurement.
''')
# Native layout is the first page. Append actual-scale coupon and explicit harness mapping.
extra=OUT/'Evidence/Assembly_notes.pdf';c=canvas.Canvas(str(extra),pagesize=landscape(A4));W,H=landscape(A4)
def title(t):
    c.setFont('Helvetica-Bold',15);c.drawString(18*mm,H-17*mm,t)
    c.setFont('Helvetica',9);c.drawString(18*mm,H-24*mm,'P0 - PROVISIONAL / DO NOT FABRICATE - 16 October 2026')
title('Blue Pill socket fit check - print at 100%')
c.setFont('Helvetica',10)
lines=['Check the 50 mm bar with a ruler before using this page.',
       'Two rows: 20 pins, 2.54 mm pitch; proposed row spacing 15.24 mm.',
       'Pitch span pin 1 to pin 20 = 48.26 mm. Actual board still unmeasured.',
       'Top view: SWD end above; USB end below. Check actual pin labels.',
       'J2 is the VBAT row; J3 is the 3V3/5V row. Do not mirror the carrier.',
       'Measure module width/length/height, socket height and SWD/USB overhang.',
       '3D rendering excludes the real Blue Pill and sensors: clearance is PENDING.']
for i,line in enumerate(lines):c.drawString(18*mm,H-(38+i*7)*mm,line)
x=200*mm;y=H-45*mm
for row,label in [(0,'J2 / VBAT'),(15.24,'J3 / 3V3')]:
    c.drawString(x+(-23 if row==0 else 19)*mm,y+6*mm,label)
    for n in range(20):
        cx,cy=x+row*mm,y-n*2.54*mm
        if n==0:c.rect(cx-.85*mm,cy-.85*mm,1.7*mm,1.7*mm)
        else:c.circle(cx,cy,.85*mm)
        c.circle(cx,cy,.5*mm)
c.drawString(x-2*mm,y-55*mm,'USB end')
c.line(x,y+12*mm,x+15.24*mm,y+12*mm);c.drawString(x,y+15*mm,'15.24 mm')
c.line(20*mm,35*mm,70*mm,35*mm);c.line(20*mm,33*mm,20*mm,37*mm);c.line(70*mm,33*mm,70*mm,37*mm)
c.drawString(20*mm,27*mm,'50.00 mm calibration bar')
c.setFont('Helvetica-Bold',10);c.drawString(18*mm,15*mm,'FIT NOT APPROVED: compare this coupon with your actual board before fabrication.')
c.showPage();title('Carrier connector pinout - module end must be verified')
manifest=json.loads((OUT/'Evidence/design_manifest.json').read_text())
c.setFont('Helvetica',8);y=H-35*mm
for item in manifest:
    if item['ref'] not in [f'J{i}' for i in range(1,17)] or item['ref'] in ('J2','J3'):continue
    values=' | '.join(k+'='+str(v) for k,v in item['nets'].items())
    c.setFont('Helvetica-Bold',9);c.drawString(18*mm,y,item['ref']+'  '+item['value']);y-=5*mm
    c.setFont('Helvetica',8);c.drawString(18*mm,y,values);y-=7*mm
    if y<32*mm:c.showPage();title('Carrier connector pinout - continued');y=H-35*mm
c.setFont('Helvetica-Bold',9);c.drawString(18*mm,18*mm,'JP1-JP8 OPEN; R1/R2/R3 and J16 DNP. Supply links do not isolate signal pins. No hot-plugging.')
c.save()
writer=PdfWriter()
for source in [OUT/'Evidence/Assembly_1to1.pdf',extra]:
    for page in PdfReader(str(source)).pages:writer.add_page(page)
with (OUT/'Assembly_Drawing.pdf').open('wb') as f:writer.write(f)
print('Created engineering review notes, verification list and assembly PDF.')
