import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","ascension.settings")
if __name__=="__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
