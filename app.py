import base64
import ctypes
import os
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import sys
from pathlib import Path

import webview
from updater import Updater, run_update_helper


class ExportAPI(Updater):
    def install_update(self, storage_backup):
        result = super().install_update(storage_backup)
        if result['ok']:
            import threading
            threading.Timer(0.8, webview.windows[0].destroy).start()
        return result

    def save_export(self, filename, content):
        if not isinstance(filename, str) or not re.fullmatch(
            r"[a-zA-Z0-9_-]+\.(json|pdf)", filename
        ):
            raise ValueError("Invalid export filename.")

        if filename.endswith(".pdf"):
            payload = base64.b64decode(content, validate=True)
            if not payload.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF data.")
            file_type = "PDF files (*.pdf)"
        else:
            if not isinstance(json.loads(content), dict):
                raise ValueError("Invalid backup data.")
            payload = content.encode("utf-8")
            file_type = "JSON backup files (*.json)"

        dialog_type = (
            webview.FileDialog.SAVE if hasattr(webview, "FileDialog") else webview.SAVE_DIALOG
        )
        selected = webview.windows[0].create_file_dialog(
            dialog_type, save_filename=filename, file_types=(file_type,)
        )
        if not selected:
            return False
        path = Path(selected if isinstance(selected, str) else selected[0])
        path.write_bytes(payload)
        return True


# Keep Personal Tracker's existing WebView profile, but isolate its web origin
# from Forex Backtest Data (legacy pywebview persistent port 42001).
LEGACY_PORT = 42001
TRACKER_PORT = 42002


def notify(message):
    if sys.platform == 'win32':
        ctypes.windll.user32.MessageBoxW(None, str(message), 'Personal Tracker PRO', 0x10)
    else:
        print(message, file=sys.stderr)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != 'win32'

    def server_bind(self):
        if sys.platform == 'win32' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(port, routes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = routes.get(self.path.split('?', 1)[0])
            if payload is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = LocalServer(('127.0.0.1', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def stop(server):
    if server is not None:
        server.shutdown()
        server.server_close()


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=True), encoding='utf-8')
    temp.replace(path)


def tracker_keys(value):
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
        raise ValueError('Invalid Personal Tracker storage backup.')
    return {k: v for k, v in value.items() if k.startswith('pt_')}


def run_app(resource_dir):
    data = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PersonalTracker'
    data.mkdir(parents=True, exist_ok=True)
    backup = data / 'Backups' / 'before-port-migration.json'
    backup.parent.mkdir(parents=True, exist_ok=True)
    marker = data / 'port-42002-migration-complete.json'
    token = secrets.token_hex(24)
    migrate_path = '/migration-' + token
    app_path = '/app-' + token + '/index.html'
    old_origin = f'http://127.0.0.1:{LEGACY_PORT}'
    new_origin = f'http://127.0.0.1:{TRACKER_PORT}'
    page = ('<!doctype html><meta charset="utf-8"><title>Personal Tracker PRO</title>'
            '<body style="font:16px Segoe UI;padding:32px">'
            '<h2>Preparing Personal Tracker</h2><p>Safely migrating your saved data. Do not close this window.</p>'
            f'<div id="{token}"></div></body>').encode('utf-8')
    current = 'normal' if marker.exists() else ('restore' if backup.exists() else 'capture')
    legacy = None
    main = None
    try:
        try:
            main = serve(TRACKER_PORT, {app_path: (resource_dir / 'index.html').read_bytes(), migrate_path: page})
        except OSError:
            notify('Personal Tracker is already open or its dedicated port 42002 is in use. Close it and try again.')
            return
        if current == 'capture':
            try:
                legacy = serve(LEGACY_PORT, {migrate_path: page})
            except OSError:
                notify('Close Forex Backtest Data and all older Personal Tracker windows, then open Personal Tracker again. This is required once to migrate your existing records safely.')
                return
        start_url = (old_origin + migrate_path if current == 'capture' else
                     new_origin + migrate_path if current == 'restore' else new_origin + app_path)
        window = webview.create_window(
            title='Personal Tracker PRO',
            url=start_url,
            width=1280,
            height=850,
            min_size=(900, 650),
            js_api=ExportAPI((resource_dir / 'version.txt').read_text().strip()),
        )
        guard = threading.Lock()

        def on_loaded():
            nonlocal current, legacy
            with guard:
                if current in ('normal', 'failed'):
                    return
                try:
                    expected = old_origin if current == 'capture' else new_origin
                    check = ('location.origin === ' + json.dumps(expected) +
                             ' && !!document.getElementById(' + json.dumps(token) + ')')
                    if window.evaluate_js(check) is not True:
                        raise RuntimeError('The expected migration page did not load.')
                    if current == 'capture':
                        raw = window.evaluate_js(
                            "JSON.stringify(Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('pt_')).map(k => [k,localStorage.getItem(k)])))"
                        )
                        saved = tracker_keys(json.loads(raw))
                        # Never discard a nonempty prior update backup just because
                        # a profile is unexpectedly empty.
                        if not saved:
                            previous = sorted(backup.parent.glob('before-update-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
                            if previous:
                                recent = tracker_keys(json.loads(previous[0].read_text(encoding='utf-8')))
                                if recent:
                                    saved = recent
                        atomic_json(backup, saved)
                        stop(legacy)
                        legacy = None
                        current = 'restore'
                        window.load_url(new_origin + migrate_path)
                    else:
                        saved = tracker_keys(json.loads(backup.read_text(encoding='utf-8')))
                        # Check for conflicts before writing anything. Repeated
                        # migrations are safe; no existing values are overwritten.
                        payload = json.dumps(saved, ensure_ascii=True)
                        script = """(() => {
                          const data = PAYLOAD;
                          const keys = Object.keys(data);
                          if(keys.some(k => localStorage.getItem(k) !== null && localStorage.getItem(k) !== data[k])) return false;
                          for(const k of keys) localStorage.setItem(k,data[k]);
                          return keys.every(k => localStorage.getItem(k) === data[k]);
                        })()""".replace('PAYLOAD', payload, 1)
                        if window.evaluate_js(script) is not True:
                            raise RuntimeError('Existing data on the new port differs. Your original backup has been kept.')
                        atomic_json(marker, {'source_port': LEGACY_PORT, 'target_port': TRACKER_PORT, 'keys': len(saved)})
                        current = 'normal'
                        window.load_url(new_origin + app_path)
                except Exception as error:
                    current = 'failed'
                    notify('Storage migration could not finish. No original records were deleted. Close both apps and retry.\n\n' + str(error))
                    window.destroy()

        window.events.loaded += on_loaded
        # Intentionally keep the same profile setting as previous versions.
        webview.start(private_mode=False)
    finally:
        stop(legacy)
        stop(main)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--apply-update':
        sys.exit(run_update_helper(sys.argv[2:]))
    resource_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    run_app(resource_dir)
