# PROVISIONAL DESIGN P0 - DO NOT FABRICATE

Evidence-Grounded Smart Package Monitoring and Handling-Event Reconstruction System
Prepared 16 October 2026 for the 21-22 October college review.

This is an editable, electrically connected KiCad carrier project, not an SVG substitute. The board has two 20-pin Blue Pill sockets, carrier-defined sensor harness connectors, a proposed power circuit, transistor buzzer driver, indicators, and test points. Plug-in modules other than the Blue Pill are mounted externally with short secured harnesses. Their physical plug-in/socket orientations and mounting holes are NOT represented as verified.

The user's original September project was read, copied into Evidence, and left untouched. DeepSeek/Gemini reviews, hardware photographs, the earlier SVG and preliminary PCB package have NOT been supplied or inspected. No present hardware was tested. MPU communication and SD initialization failures remain unresolved.

Open SmartLogistics.kicad_pro in KiCad 10.0.7 or later. Libraries are local and portable. The 3D rendering shows generic carrier components only; it cannot prove Blue Pill/module clearance. JP1 is the master supply link. JP2-JP8 are module supply commissioning links. All are OPEN/unpopulated in P0. R1/R2/R3 pull-ups and J16 VTref are also unpopulated pending identification. These links disconnect VCC only, not signal pins: keep modules disconnected while their supply links are open. Never hot-plug or change links with power applied.

ERC_Report.txt and DRC_Report.txt are actual KiCad outputs. DRC was run with schematic parity. See Validation_Summary.txt for the final checked state and limitations. Passing these checks does not resolve module voltage thresholds, real mechanical fit, source selection or prior failed sensor tests.

Gerbers/, Drill_Files/ and PCB_Fabrication_SHOP.zip are intentionally withheld until release gates pass. Do not send the native PCB or preview images to a shop for manufacture. Fabrication_Instructions.txt is a QUOTATION/REVIEW specification only.

Review Power_Design.md and Verification_Required.csv first. Assembly_Drawing.pdf includes the actual layout, a 1:1 Blue Pill socket-fit coupon and a carrier harness table. Print the fit coupon at 100% with scaling disabled and verify its 50 mm calibration bar before comparing hardware.
