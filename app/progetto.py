"""Il progetto dell'utente: una cartella con config.yaml (ingresso del motore, contratto §3) e risultati/.

Si scrive e si legge solo con yaml.safe_dump / yaml.safe_load. Il motore valida il contenuto
(CONFIG_NON_VALIDA): qui si controlla solo il nome della cartella.
"""
import os
import re
import tempfile
from pathlib import Path

import yaml
from PySide6.QtCore import QStandardPaths

NOME_VALIDO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}")   # come project_name di config.example.yaml


def cartella_progetti():
    """Documenti\\ProfileMetaNanni (R10: si parte da Documenti)."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)) / "ProfileMetaNanni"


class Progetto:
    def __init__(self, cartella):
        self.cartella = Path(cartella)

    @property
    def nome(self):
        return self.cartella.name

    @property
    def config(self):
        return self.cartella / "config.yaml"

    @property
    def risultati(self):
        return self.cartella / "risultati"

    def leggi(self):
        if not self.config.is_file():
            return {}
        with open(self.config, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def scrivi(self, dati):
        """Scrive config.yaml tutto o niente (file temporaneo accanto, poi sostituzione)."""
        self.cartella.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.cartella, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(dati, f, allow_unicode=True, sort_keys=False)
            os.replace(tmp, self.config)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def nuovo(nome, radice=None):
    """Crea la cartella di un progetto nuovo. Nome: lettere, numeri, punto, trattino, trattino basso."""
    if not NOME_VALIDO.fullmatch(nome or ""):
        raise ValueError("Il nome può avere solo lettere senza accenti, numeri, punto, trattino e trattino basso "
                         "(massimo 60), e deve iniziare con una lettera o un numero.")
    cartella = Path(radice or cartella_progetti()) / nome
    if cartella.exists():
        raise FileExistsError(f"Esiste già un progetto che si chiama {nome}.")
    cartella.mkdir(parents=True)
    return Progetto(cartella)


def elenco(radice=None):
    """I progetti (cartelle con config.yaml), dal più recente."""
    radice = Path(radice or cartella_progetti())
    if not radice.is_dir():
        return []
    trovati = [Progetto(d) for d in radice.iterdir() if (d / "config.yaml").is_file()]
    return sorted(trovati, key=lambda p: p.config.stat().st_mtime, reverse=True)
