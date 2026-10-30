# -*- coding: utf-8 -*-
"""A "difficult" local mirror for the installer tests (D038, v1.1 R1-R4): serves files from a folder like
`--specchio`, with a speed limit per connection (per path prefix, so two sources can have two speeds), servers
without Range, connections that drop half way, and a log of every request with its byte range."""
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Specchio:
    def __init__(self, radice, velocita=None, senza_range=(), cadute=None, linea=None):
        """velocita: {"/kraken/": byte/s per connection}; senza_range: path prefixes that ignore Range (always 200);
        cadute: {path prefix: n} the first n answers for each path of that prefix stop after a quarter of the bytes;
        linea: byte/s for all the connections together (the line of the PC), shared in the order the bytes are asked."""
        self.radice = str(radice)
        self.linea = linea
        self.prossimo = 0.0          # when the line is free again (time.monotonic)
        self.velocita = dict(velocita or {})
        self.senza_range = tuple(senza_range)
        self.cadute = dict(cadute or {})
        self.contate = {}
        self.richieste = []          # (path, start, end, code)
        self.lock = threading.Lock()
        specchio = self

        class Gestore(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_HEAD(self):
                self.rispondi(corpo=False)

            def do_GET(self):
                self.rispondi(corpo=True)

            def rispondi(self, corpo):
                file = os.path.join(specchio.radice, self.path.lstrip("/"))
                if not os.path.isfile(file):
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                n = os.path.getsize(file)
                a, z, codice = 0, n - 1, 200
                m = re.fullmatch(r"bytes=(\d+)-(\d*)", self.headers.get("Range", ""))
                if m and not self.path.startswith(specchio.senza_range):
                    a = int(m.group(1))
                    z = min(int(m.group(2)) if m.group(2) else n - 1, n - 1)
                    if a >= n:
                        self.send_response(416)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    codice = 206
                with specchio.lock:
                    specchio.richieste.append((self.path, a, z, codice))
                    cade = next((k for k in specchio.cadute if self.path.startswith(k)), None)
                    cade = cade is not None and specchio.contate.get(self.path, 0) < specchio.cadute[cade]
                    if cade:
                        specchio.contate[self.path] = specchio.contate.get(self.path, 0) + 1
                self.send_response(codice)
                self.send_header("Content-Length", str(z - a + 1))
                if codice == 206:
                    self.send_header("Content-Range", f"bytes {a}-{z}/{n}")
                    self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                if not corpo:
                    return
                v = next((v for k, v in specchio.velocita.items() if self.path.startswith(k)), None)
                limite = a + (z - a + 1) // 4 if cade else z + 1
                inizio = time.monotonic()
                mandati = 0
                with open(file, "rb") as f:
                    f.seek(a)
                    pos = a
                    while pos < limite:
                        blocco = f.read(min(16384, limite - pos))
                        try:
                            self.wfile.write(blocco)
                        except OSError:
                            return
                        pos += len(blocco)
                        mandati += len(blocco)
                        if specchio.linea:
                            with specchio.lock:
                                adesso = time.monotonic()
                                specchio.prossimo = max(adesso, specchio.prossimo) + len(blocco) / specchio.linea
                                attesa = specchio.prossimo - adesso
                            time.sleep(attesa)
                        if v:
                            ritardo = mandati / v - (time.monotonic() - inizio)
                            if ritardo > 0:
                                time.sleep(ritardo)
                if cade:
                    self.close_connection = True
                    try:
                        self.connection.shutdown(2)
                    except OSError:
                        pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Gestore)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def chiudi(self):
        self.server.shutdown()
        self.server.server_close()
