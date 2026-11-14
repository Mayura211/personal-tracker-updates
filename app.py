import base64
import json
import re
import sys
from pathlib import Path

import webview


class ExportAPI:
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


if __name__ == "__main__":
    resource_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    webview.create_window(
        title="Personal Tracker PRO",
        url=str(resource_dir / "index.html"),
        width=1280,
        height=850,
        min_size=(900, 650),
        js_api=ExportAPI(),
    )
    webview.start(private_mode=False)
