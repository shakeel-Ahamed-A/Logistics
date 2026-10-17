from pathlib import Path
import re, subprocess, shutil
ROOT=Path(__file__).parent;OUT=ROOT/'PCB_Fabrication';K=ROOT/'tools/KiCad'
fps=list((OUT/'Libraries/Carrier.pretty').glob('*.kicad_mod'))
models=set()
for f in fps:
    for m in re.findall(r'\(model\s+"\$\{KICAD10_3DMODEL_DIR\}/([^"]+)"',f.read_text()):models.add(m)
cmd=[str(ROOT/'tools/7zip/Files/7-Zip/7z.exe'),'x',str(ROOT/'tools/kicad-10.0.7-x86_64.exe'),'-o'+str(K),'-y','-bso0','-bsp0']
cmd+=['share\\kicad\\3dmodels\\'+m.replace('/','\\') for m in sorted(models)]
subprocess.run(cmd,check=True)
for m in models:
    src=K/'share/kicad/3dmodels'/m; dst=OUT/'Libraries/3dmodels'/m
    if src.exists():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    else: print('Missing model',m)
for f in fps+[OUT/'SmartLogistics.kicad_pcb']:
    txt=f.read_text();txt=txt.replace('${KICAD10_3DMODEL_DIR}/','${KIPRJMOD}/Libraries/3dmodels/');f.write_text(txt)
print('Packaged',len(models),'generic component models. Actual plug-in modules are NOT modeled.')
