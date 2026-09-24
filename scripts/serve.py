import sys,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/"backend")]
os.environ.setdefault("DJANGO_SETTINGS_MODULE","ascension.settings")
from ascension.wsgi import application
from waitress import serve
port=int(os.environ.get("PORT","8000"))
serve(application,host="0.0.0.0",port=port,threads=4)
