"""Prune resources unused by the raster Widgets app, then freeze the generated spec."""
from pathlib import Path
import subprocess
import sys
spec=Path('ExcelMapper.spec')
source=spec.read_text(encoding='utf-8')
prune="""# This app uses raster Widgets, never software OpenGL or Qt translators.
a.binaries = [item for item in a.binaries if item[0].replace(chr(92),'/').split('/')[-1].lower() != 'opengl32sw.dll']
a.datas = [item for item in a.datas if '/translations/' not in ('/'+item[0].replace(chr(92),'/')).lower()]
"""
source=source.replace('pyz = PYZ(',prune+'\npyz = PYZ(')
spec.write_text(source,encoding='utf-8')
subprocess.run([sys.executable,'-m','PyInstaller','--clean','--noconfirm',str(spec)],check=True)
