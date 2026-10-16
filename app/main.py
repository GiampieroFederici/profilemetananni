"""Avvio dell'app ProfileMetaNanni (S5a).

Dalla cartella del progetto:  app\\.venv\\Scripts\\python -m app.main
Con il finto motore (D032):   set PMN_MOTORE=finto  (opzioni in PMN_FINTO_OPZIONI, per esempio "--velocita 0")
"""
import sys
from pathlib import Path

from PySide6.QtCore import QDir
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from app.finestra import Finestra

CARTELLA = Path(__file__).resolve().parent


def prepara(app):
    """Carattere Atkinson Hyperlegible (OFL, app/risorse/carattere) e stile (url(risorse:...) = app/risorse)."""
    QDir.addSearchPath("risorse", str(CARTELLA / "risorse"))
    for ttf in sorted((CARTELLA / "risorse" / "carattere").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    app.setStyleSheet((CARTELLA / "stile.qss").read_text(encoding="utf-8"))


def main():
    if sys.platform == "win32":          # icona dell'app (non quella di Python) nella barra di Windows
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("profilemetananni.app")
    app = QApplication(sys.argv)
    app.setApplicationName("ProfileMetaNanni")
    prepara(app)
    f = Finestra()
    f.show()
    f.avvia()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
