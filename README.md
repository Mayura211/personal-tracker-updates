# Personal Tracker

Windows habit, study and sleep tracker with GitHub release checking.

## What's new in v1.0.5

- Independent Bar Only / Line Only / Both chart styles for Study and Sleep Performance Analysis.
- Study Performance: customizable daily study goal with a dashed reference line. For weekly views this is scaled to seven days; for monthly/yearly totals it uses a 30-day equivalent.
- Sleep Performance: customizable horizontal bad / good guide / excellent reference lines (6h / 7h / 8h defaults).
- Chart preferences are saved separately for each signed-in account and do not change study or sleep history.
- Study and Sleep PDF exports now include each report period's duration total, overall total, current calendar month total and monthly totals at the end of the report.

The chart reference lines are display guides only and do not rewrite sleep classifications stored in existing records.

## Download

Download `PersonalTracker_Setup.exe` from this repository's latest release. Close the running app before installing. Windows may show an unsigned-app prompt because this build has no code-signing certificate.

## Publish an update

1. Edit `index.html` (or `app.py` for desktop changes).
2. Increase `version.txt`, for example from `1.0.0` to `1.0.1`.
3. Commit to `main`. The Windows Actions workflow builds an EXE, creates an installer and publishes a new GitHub Release.
4. From v1.0.2 onward, users open the update button, choose **Download update**, then **Install & Restart**. The app downloads internally, verifies the GitHub SHA-256 digest, and saves a full localStorage snapshot under `%LOCALAPPDATA%\PersonalTracker\Backups`. From v1.0.3 onward, a detached helper waits for both the app process and the PyInstaller onefile bootloader to exit before starting the verified installer; Setup then restarts the app. Version 1.0.4 also clears inherited PyInstaller environment variables before starting Setup, and explicitly resets the PyInstaller environment just before Setup launches the updated app. This prevents restarts from trying to load Python DLLs from the old deleted `_MEI` directory. The v1.0.3 installer includes a one-time delay to accommodate the older v1.0.2 updater. A local diagnostic log is saved at `%LOCALAPPDATA%\PersonalTracker\Updates\update-helper.log`. The raw snapshot is for recovery and is not the normal Import Backup format. Users on v1.0.0/v1.0.1 need one manual installation to receive this updater.

The workflow sets the HTML version from `version.txt`. Published versions are not replaced; increment the version for every release. Public releases and source files are visible to everyone.

## Existing user data

The supplied launcher uses `webview.start(private_mode=False)` without an explicit profile path. This behavior is retained. A new installation location or WebView origin can nevertheless select different storage. Before the first installation, export each user's backup from the old application and retain the old EXE. If the new version opens empty, create/sign into the matching account and import its backup. Do not delete old WebView folders. Records are not uploaded to GitHub.

Before giving this to an existing user, verify old-version export, new-version import, restart persistence, PDF export and installation on their Windows environment. The GitHub build verifies packaging, not migration on that user's PC.

## Build locally

Use Python 3.11 on Windows and Microsoft Edge WebView2 Runtime. Decode `icon.base64` to `icon.ico`, then run `python -m pip install -r requirements.txt` and `python -m PyInstaller --noconfirm PersonalTracker.spec`. Install Inno Setup 6, set environment variable `TRACKER_VERSION` from `version.txt`, and compile `setup.iss`.
