import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import threading
import queue
from urllib.parse import urlsplit

from PIL import Image


def decode_frame(value):
    if not isinstance(value, str) or not value.startswith('data:image/png;base64,'):
        raise ValueError('Očekáván PNG obrázek.')
    raw = base64.b64decode(value.split(',', 1)[1], validate=True)
    with Image.open(BytesIO(raw)) as image:
        if image.format != 'PNG' or image.size != (96, 16):
            raise ValueError('Obrázek musí mít přesně 96 × 16 pixelů.')
        output = BytesIO()
        image.convert('RGB').save(output, format='PNG')
        return output.getvalue()


def validate_motion(payload):
    animation = payload.get('animation', 'static')
    if animation not in ('static', 'scroll_left'):
        raise ValueError('Neplatný typ animace.')
    if animation == 'static':
        return {'image': decode_frame(payload['image']).hex()}
    text = payload.get('text')
    if not isinstance(text, str) or not text.strip() or len(text) > 180 or '\n' in text:
        raise ValueError('Posun potřebuje text na jednom řádku (1–180 znaků).')
    speed, size = payload.get('speed', 60), payload.get('size', 12)
    if type(speed) is not int or not 1 <= speed <= 100:
        raise ValueError('Rychlost musí být 1–100.')
    if type(size) is not int or size not in (7, 9, 12, 14, 15, 16):
        raise ValueError('Neplatná velikost písma.')
    colors = {}
    for key in ('color', 'background'):
        value = payload.get(key)
        if not isinstance(value, str) or len(value) != 7 or not value.startswith('#'):
            raise ValueError('Neplatná barva.')
        try:
            bytes.fromhex(value[1:])
        except ValueError:
            raise ValueError('Neplatná barva.')
        colors[key] = value[1:]
    result = {'animation': animation, 'text': text, 'speed': speed, 'size': size, **colors}
    return result


class BluetoothWorker:
    def __init__(self):
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'pypixelcolor.editor.transport'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.responses = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            self.responses.put(line)
        self.responses.put(None)

    def call(self, request):
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        try:
            line = self.responses.get(timeout=45)
        except queue.Empty:
            self.process.kill()
            raise RuntimeError('Bluetooth neodpovídá. Restartuj editor.')
        if line is None:
            raise RuntimeError('Bluetooth proces se ukončil. Restartuj editor.')
        return json.loads(line)

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.headers.get('Host') not in self.server.allowed_hosts:
            return self.reply(403, {'error': 'Nepovolený host.'})
        path = urlsplit(self.path).path
        if path == '/api/config':
            return self.reply(200, {'address': self.server.address, 'width': 96, 'height': 16})
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/pixel-font.js': ('pixel-font.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in files:
            return self.reply(404, {'error': 'Nenalezeno.'})
        filename, mime = files[path]
        raw = Path(__file__).with_name(filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        host = self.headers.get('Host')
        origin = self.headers.get('Origin')
        if host not in self.server.allowed_hosts or (origin and origin != f'http://{host}'):
            return self.reply(403, {'error': 'Nepovolený původ požadavku.'})
        actions = {'/api/send': 'send', '/api/scan': 'scan', '/api/connect': 'connect',
                   '/api/disconnect': 'disconnect', '/api/status': 'status'}
        if self.path not in actions:
            return self.reply(404, {'error': 'Nenalezeno.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                raise ValueError('Neplatná velikost požadavku.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Očekáván JSON objekt.')
            action = actions[self.path]
            request = {'action': action}
            if action == 'send':
                request.update(validate_motion(payload))
            address = payload.get('address') or self.server.address
            if action in ('connect', 'send') and (not isinstance(address, str) or not 1 <= len(address) <= 100 or address.startswith('-')):
                raise ValueError('Zadej adresu nebo vyber nalezený panel.')
            request['address'] = address
        except (ValueError, KeyError, TypeError, OSError) as exc:
            return self.reply(400, {'error': str(exc)})
        if not self.server.ble_lock.acquire(blocking=False):
            return self.reply(409, {'error': 'Probíhá operace Bluetooth. Zkus to za chvíli.'})
        try:
            result = self.server.worker.call(request)
            return self.reply(200 if result.get('ok') else 502, result)
        except (RuntimeError, OSError) as exc:
            return self.reply(503, {'error': str(exc)})
        finally:
            self.server.ble_lock.release()


def main():
    parser = argparse.ArgumentParser(description='Webový editor LED panelu 96 × 16')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('-a', '--address', default='')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.address = args.address
    server.allowed_hosts = {f'127.0.0.1:{server.server_port}', f'localhost:{server.server_port}'}
    server.ble_lock = threading.Lock()
    server.worker = BluetoothWorker()
    print(f'LED editor: http://localhost:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.worker.close()


if __name__ == '__main__':
    main()
