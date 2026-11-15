"""Download and verify this application's public GitHub release."""
import hashlib
import json
import os
import re
import shutil
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
        # Remove old helper copies when the next app instance starts.
        for previous_helper in self.directory.glob('PersonalTracker_UpdateHelper_*.exe'):
            try:
                previous_helper.unlink()
            except OSError:
                pass

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
            # Never launch Setup while the installed EXE is still running.
            # A separate copy of this frozen EXE survives the main app's exit,
            # waits for its PyInstaller child and bootloader, then starts Setup.
            helper = self.directory / f'PersonalTracker_UpdateHelper_{time.time_ns()}.exe'
            shutil.copy2(sys.executable, helper)
            env = os.environ.copy()
            env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
            subprocess.Popen(
                [str(helper), '--apply-update', str(os.getpid()), str(os.getppid()),
                 str(self.installer.resolve()), self.digest],
                cwd=str(self.directory),
                env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                close_fds=True,
            )
            self._set(status='installing', message='Closing Personal Tracker before installing. The app will restart after the update.')
            return {'ok': True}
        except Exception as error:
            return {'ok': False, 'message': str(error)}
        finally:
            self.installing = False


def _wait_for_process_exit(pid, timeout_ms=180000):
    """Wait for a Windows process, including the PyInstaller onefile parent."""
    import ctypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    kernel32.WaitForSingleObject.restype = ctypes.c_ulong
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool

    handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: process already exited
            return
        raise OSError(f'Cannot wait for process {pid}: Windows error {error}.')
    try:
        result = kernel32.WaitForSingleObject(handle, timeout_ms)
        if result != 0:  # WAIT_OBJECT_0
            raise TimeoutError(f'Personal Tracker process {pid} did not exit (wait result {result}).')
    finally:
        kernel32.CloseHandle(handle)


def run_update_helper(arguments):
    """Executed by a detached copy of PersonalTracker.exe, not the live app."""
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return 1

    directory = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PersonalTracker' / 'Updates'
    log = directory / 'update-helper.log'
    try:
        if len(arguments) != 4:
            raise ValueError('Invalid update helper arguments.')
        app_pid, bootloader_pid = int(arguments[0]), int(arguments[1])
        installer, checksum = Path(arguments[2]), arguments[3]
        if not (0 < app_pid < 2**32 and 0 < bootloader_pid < 2**32):
            raise ValueError('Invalid process identifiers.')
        if installer.parent.resolve() != directory.resolve():
            raise ValueError('Installer is not in the verified update directory.')
        if not re.fullmatch(r'PersonalTracker-v\d+\.\d+\.\d+\.exe', installer.name):
            raise ValueError('Unexpected installer filename.')
        if not re.fullmatch(r'[0-9a-f]{64}', checksum):
            raise ValueError('Invalid installer checksum.')
        if not 0 < installer.stat().st_size <= MAX_DOWNLOAD:
            raise ValueError('Invalid installer size.')

        # Onefile PyInstaller runs an application child and a bootloader parent.
        # The original EXE may remain locked until BOTH have exited.
        for pid in dict.fromkeys((app_pid, bootloader_pid)):
            if pid != os.getpid():
                _wait_for_process_exit(pid)
        time.sleep(0.75)

        # Verify the downloaded bytes a second time immediately before execution.
        hasher = hashlib.sha256()
        with installer.open('rb') as file:
            for chunk in iter(lambda: file.read(256 * 1024), b''):
                hasher.update(chunk)
        if hasher.hexdigest() != checksum:
            raise ValueError('Update installer verification failed.')

        install_log = directory / 'install.log'
        result = subprocess.run(
            [str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
             '/CLOSEAPPLICATIONS', '/PTUPDATE=2', f'/LOG={install_log}'],
            cwd=str(directory),
            timeout=900,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f'Installer exited with code {result.returncode}.')
        message = 'Update installation completed successfully.'
        code = 0
    except Exception as error:
        message = f'Update failed: {error}'
        code = 1

    try:
        directory.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as output:
            output.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}\n')
    except OSError:
        pass
    return code
