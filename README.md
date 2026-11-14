# Personal Tracker

Windows habit, study and sleep tracker with GitHub release checking.

## Download

Download `PersonalTracker_Setup.exe` from this repository's latest release. Close the running app before installing. Windows may show an unsigned-app prompt because this build has no code-signing certificate.

## Publish an update

1. Edit `index.html` (or `app.py` for desktop changes).
2. Increase `version.txt`, for example from `1.0.0` to `1.0.1`.
3. Commit to `main`. The Windows Actions workflow builds an EXE, creates an installer and publishes a new GitHub Release.
4. Existing users click **Check for Updates**, download the installer and run it after closing the app.

The workflow sets the HTML version from `version.txt`. Published versions are not replaced; increment the version for every release. Public releases and source files are visible to everyone.

## Existing user data

The supplied launcher uses `webview.start(private_mode=False)` without an explicit profile path. This behavior is retained. A new installation location or WebView origin can nevertheless select different storage. Before the first installation, export each user's backup from the old application and retain the old EXE. If the new version opens empty, create/sign into the matching account and import its backup. Do not delete old WebView folders. Records are not uploaded to GitHub.

Before giving this to an existing user, verify old-version export, new-version import, restart persistence, PDF export and installation on their Windows environment. The GitHub build verifies packaging, not migration on that user's PC.

## Build locally

Use Python 3.11 on Windows and Microsoft Edge WebView2 Runtime. Decode `icon.base64` to `icon.ico`, then run `python -m pip install -r requirements.txt` and `python -m PyInstaller --noconfirm PersonalTracker.spec`. Install Inno Setup 6, set environment variable `TRACKER_VERSION` from `version.txt`, and compile `setup.iss`.
