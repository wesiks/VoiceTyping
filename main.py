import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    app_dir = Path(sys.executable).resolve().parent
    meipass = Path(getattr(sys, "_MEIPASS", app_dir / "_internal"))
    possible_src = [meipass / "src", app_dir / "_internal" / "src", app_dir / "src"]
else:
    app_dir = Path(__file__).resolve().parent
    possible_src = [app_dir / "src"]

for p in possible_src:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    os.chdir(app_dir)
except Exception:
    pass

from app_logger import setup_logging, show_crash_dialog
logger = setup_logging()

from app_main import run_app

def main():
    run_app()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        if 'logger' in globals():
            logger.critical("Фатальный сбой в main():\n%s", tb)
        show_crash_dialog(str(e), tb)
        sys.exit(1)
