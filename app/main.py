"""Avvio dell'app ProfileMetaNanni (S5a).

Dalla cartella del progetto:  app\\.venv\\Scripts\\python -m app.main
Con il finto motore (D032):   set PMN_MOTORE=finto  (opzioni in PMN_FINTO_OPZIONI, per esempio "--velocita 0")
"""
import sys
from pathlib import Path

from PySide6.QtCore import QDir, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from app import lingua
from app.finestra import Finestra, movimento_ridotto

CARTELLA = Path(__file__).resolve().parent


def prepara(app):
    """Carattere Atkinson Hyperlegible (OFL, app/risorse/carattere) e stile (url(risorse:...) = app/risorse).
    Con "riduci movimento" di Windows (R15) si spengono anche le animazioni di Qt (menu, suggerimenti)."""
    QDir.addSearchPath("risorse", str(CARTELLA / "risorse"))
    for ttf in sorted((CARTELLA / "risorse" / "carattere").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    app.setStyleSheet((CARTELLA / "stile.qss").read_text(encoding="utf-8"))
    if movimento_ridotto():
        for effetto in (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip,
                        Qt.UI_FadeTooltip, Qt.UI_AnimateToolBox):
            app.setEffectEnabled(effetto, False)


def main():
    if sys.platform == "win32":          # icona dell'app (non quella di Python) nella barra di Windows
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("profilemetananni.app")
    app = QApplication(sys.argv)
    app.setApplicationName("ProfileMetaNanni")
    prepara(app)
    lingua.imposta(lingua.salvata())     # la lingua scelta l'ultima volta (italiano la prima)
    f = Finestra()
    f.show()
    f.avvia()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
