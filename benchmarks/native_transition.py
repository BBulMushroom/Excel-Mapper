"""Measure click preparation separately from the 360ms transition animation (Qt offscreen)."""
import os,sys,time,tempfile,json,argparse
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
p=argparse.ArgumentParser();p.add_argument('--source-root',default=str(Path(__file__).resolve().parents[1]));args=p.parse_args();sys.path.insert(0,args.source_root)
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from desktop.style import NativeStyle
from desktop.ui import Window
from desktop.session import Session
from sample_catalog import load_sample
app=QApplication([]);app.native_style=NativeStyle();app.setStyle(app.native_style);QSettings.setDefaultFormat(QSettings.Format.IniFormat);QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,tempfile.mkdtemp())
for sample in ['4','5']:
 old,files,name=load_sample(sample);w=Window();w.combined=False;w.session=Session(old,files,name);w.show();w.refresh();app.processEvents()
 for mode in ['merge','split']:
  start=time.perf_counter();w.toggle_combined();app.processEvents();elapsed=(time.perf_counter()-start)*1000
  print(json.dumps(dict(sample=sample,mode=mode,preparation_ms=round(elapsed,1))),flush=True)
  app.processEvents()
 w.hide();w.deleteLater();app.processEvents()
