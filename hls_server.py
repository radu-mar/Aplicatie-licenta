from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 8080
STREAM_DIR = Path(r"D:\Licenta\AplicatieLucrareLicenta\stream")

class HLSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STREAM_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")

        if self.path.endswith(".m3u8"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

        elif self.path.endswith(".ts"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

        super().end_headers()

    def guess_type(self, path):
        if path.endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        if path.endswith(".ts"):
            return "video/mp2t"
        return super().guess_type(path)

if __name__ == "__main__":
    if not STREAM_DIR.exists():
        raise FileNotFoundError(f"Folderul stream nu exista: {STREAM_DIR}")

    server = ThreadingHTTPServer(("127.0.0.1", PORT), HLSRequestHandler)
    print(f"HLS server pornit la http://127.0.0.1:{PORT}")
    print(f"Serveste fisiere din: {STREAM_DIR}")
    server.serve_forever()