# Proposed power circuit - analysis only, not electrical approval

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
