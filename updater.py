"""Download and verify this application's public GitHub release."""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPOSITORY = 'Mayura211/personal-tracker-updates'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_DOWNLOAD = 200 * 1024 * 1024


def version_tuple(value):
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', value):
        raise ValueError('Invalid release version.')
    return tuple(map(int, value.lstrip('v').split('.')))


def open_url(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'PersonalTracker-Updater',
        'Accept': 'application/vnd.github+json' if url == API_URL else 'application/octet-stream',
    })
    return urllib.request.urlopen(request, timeout=30)


class Updater:
    def __init__(self, current_version):
        self.current_version = current_version
        self.directory = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PersonalTracker' / 'Updates'
        self.lock = threading.Lock()
        self.state = {'status': 'idle', 'progress': 0, 'message': ''}
        self.installer = None
        self.digest = None
        self.installing = False

    def _set(self, **values):
        with self.lock:
            self.state.update(values)

    def update_download_status(self):
        with self.lock:
            return dict(self.state)

    def start_update_download(self):
        with self.lock:
            if self.state['status'] in ('downloading', 'ready', 'installing'):
                return dict(self.state)
            self.state = {'status': 'downloading', 'progress': 0, 'message': 'Finding the latest update…'}
        threading.Thread(target=self._download, daemon=True).start()
        return self.update_download_status()

    def _download(self):
        temporary = None
        try:
            with open_url(API_URL) as response:
                release = json.loads(response.read(2 * 1024 * 1024))
            tag = release['tag_name']
            if version_tuple(tag) <= version_tuple(self.current_version):
                self._set(status='current', message='This version is up to date.')
                return
            asset = next(a for a in release.get('assets', []) if a['name'] == 'PersonalTracker_Setup.exe')
            url = asset['browser_download_url']
            if not url.startswith(f'https://github.com/{REPOSITORY}/releases/download/'):
                raise ValueError('Unexpected update location.')
            digest = asset.get('digest', '')
            if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
                raise ValueError('The release has no verification checksum. Try again later.')
            expected = digest.split(':', 1)[1].lower()
            size = asset['size']
            if not isinstance(size, int) or not 0 < size <= MAX_DOWNLOAD:
                raise ValueError('Unexpected update size.')
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self.directory / f'PersonalTracker-{tag}.exe'
            temporary = target.with_suffix('.part')
            hasher = hashlib.sha256()
            received = 0
            with open_url(url) as response, temporary.open('wb') as output:
                if not response.url.startswith('https://'):
                    raise ValueError('Update requires a secure connection.')
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > size:
                        raise ValueError('The update size does not match the release.')
                    output.write(chunk)
                    hasher.update(chunk)
                    self._set(progress=min(99, int(received * 100 / size)), message='Downloading update…')
            if received != size or hasher.hexdigest() != expected:
                raise ValueError('Update verification failed. Please download again.')
            temporary.replace(target)
            self.installer, self.digest = target, expected
            self._set(status='ready', progress=100, message='Update downloaded and verified. Ready to install.')
        except Exception as error:
            if temporary:
                temporary.unlink(missing_ok=True)
            self._set(status='error', message=f'Could not download update: {error}')

    def install_update(self, storage_backup):
        with self.lock:
            if self.state['status'] != 'ready' or self.installing:
                return {'ok': False, 'message': 'Download the update first.'}
            self.installing = True
        try:
            if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
                raise ValueError('Install updates from the installed Windows application.')
            if not isinstance(storage_backup, str) or len(storage_backup) > 20 * 1024 * 1024:
                raise ValueError('Could not prepare a local data backup.')
            data = json.loads(storage_backup)
            if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()):
                raise ValueError('Invalid local data backup.')
            if not self.installer or hashlib.sha256(self.installer.read_bytes()).hexdigest() != self.digest:
                self._set(status='error', message='Installer changed. Download it again.')
                raise ValueError('Installer verification failed.')
            backups = self.directory.parent / 'Backups'
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / f'before-update-{time.time_ns()}.json'
            backup.write_text(storage_backup, encoding='utf-8')
            log = self.directory / 'install.log'
            subprocess.Popen([str(self.installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS', '/PTUPDATE=1', f'/LOG={log}'], cwd=str(self.installer.parent))
            self._set(status='installing', message='Installing. The app will restart shortly.')
            return {'ok': True}
        except Exception as error:
            return {'ok': False, 'message': str(error)}
        finally:
            self.installing = False
