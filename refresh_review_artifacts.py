"""Refresh review-only outputs from the saved CAD; no fabrication export."""
from pathlib import Path
import os, subprocess, json, concurrent.futures, shutil
from pypdf import PdfReader,PdfWriter
from PIL import Image,ImageChops
R=Path(__file__).parent; O=R/'PCB_Fabrication';E=O/'Evidence'; K=R/'tools/KiCad'
for key,val in {'KICAD_DOCUMENTS_HOME':R/'tools/KiCadUser','KICAD_CONFIG_HOME':R/'tools/KiCadConfig','KICAD10_SYMBOL_DIR':K/'share/kicad/symbols','KICAD10_FOOTPRINT_DIR':K/'share/kicad/footprints'}.items():os.environ[key]=str(val)
pcb=O/'SmartLogistics.kicad_pcb'
commands=[
 ['sch','export','pdf','-o',O/'Schematic.pdf',O/'SmartLogistics.kicad_sch'],
 ['pcb','export','pdf','--mode-single','--layers','F.Cu,F.Silkscreen,Edge.Cuts','-o',E/'PCB_Top.pdf',pcb],
 ['pcb','export','pdf','--mode-single','--mirror','--layers','B.Cu,B.Silkscreen,Edge.Cuts','-o',E/'PCB_Bottom.pdf',pcb],
 ['pcb','export','pdf','--mode-single','--scale','1','--layers','F.Fab,F.Silkscreen,Edge.Cuts,Dwgs.User','--exclude-value','--sketch-pads-on-fab-layers','--black-and-white','-o',E/'Assembly_1to1.pdf',pcb],
 ['pcb','render','--width','1600','--height','1400','--zoom','0.7','--rotate','35,0,25','--quality','high','-o',O/'PCB_3D.png',pcb]]
def run(args):
    q=subprocess.run([str(K/'bin/kicad-cli.exe'),*map(str,args)],capture_output=True,text=True)
    return dict(args=list(map(str,args)),exit=q.returncode,stdout=q.stdout,stderr=q.stderr)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex: logs=list(ex.map(run,commands))
(E/'review_export_log.json').write_text(json.dumps(logs,indent=2))
assert all(x['exit']==0 for x in logs),logs
# Keep the already reviewed explanatory pages. Native layout comes from this export.
writer=PdfWriter()
for src in [E/'Assembly_1to1.pdf',E/'Assembly_notes.pdf']:
    for page in PdfReader(src).pages:writer.add_page(page)
with (O/'Assembly_Drawing.pdf').open('wb') as f:writer.write(f)
fit=PdfWriter();fit.add_page(PdfReader(E/'Assembly_notes.pdf').pages[0])
with (O/'BluePill_Socket_Fit_1to1.pdf').open('wb') as f:fit.write(f)
pop=Path(r'C:\Users\anwar\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
for src,dest,dpi in [(E/'PCB_Top.pdf',O/'PCB_Top',200),(E/'PCB_Bottom.pdf',O/'PCB_Bottom',200),(O/'Schematic.pdf',E/'schematic_review',100),(O/'BluePill_Socket_Fit_1to1.pdf',E/'socket_fit_review',120)]:
    subprocess.run([str(pop),'-r',str(dpi),'-png','-singlefile',str(src),str(dest)],check=True,capture_output=True)
    if dest.name.startswith('PCB_'):
        image=Image.open(dest.with_suffix('.png')).convert('RGB');box=ImageChops.difference(image,Image.new('RGB',image.size,'white')).getbbox()
        if box:
            box=(max(0,box[0]-30),max(0,box[1]-30),min(image.width,box[2]+30),min(image.height,box[3]+30));image.crop(box).save(dest.with_suffix('.png'))
subprocess.run([str(pop),'-r','100','-png',str(O/'Assembly_Drawing.pdf'),str(E/'assembly_review')],check=True,capture_output=True)
print('Refreshed schematic, top/bottom, 3D, assembly and separate 1:1 fit PDF. Native CAD unchanged.')
