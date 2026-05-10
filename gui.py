import os
import sys
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QLabel, QTextEdit, QProgressBar, QPushButton,
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor

load_dotenv()

SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI")

_QSS = """
* { background: #0f0f0f; color: #ffffff; border: none; outline: none; }
QTextEdit {
    background: #1a1a1a;
    font-family: Menlo, Consolas, monospace;
    font-size: 11pt;
    border-radius: 6px;
    padding: 6px;
}
QScrollBar:vertical {
    background: #1a1a1a; width: 10px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #444; border-radius: 5px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar {
    background: #1a1a1a; border-radius: 4px; max-height: 8px;
}
QProgressBar::chunk { background: #1DB954; border-radius: 4px; }
QPushButton {
    background: #1DB954;
    color: #0f0f0f;
    border-radius: 6px;
    padding: 10px 40px;
    font-size: 13pt;
    font-weight: bold;
}
QPushButton:hover    { background: #17a349; }
QPushButton:disabled { background: #555555; color: #888888; }
"""


class Worker(QObject):
    logged     = pyqtSignal(str, str)   # (message, colour: "" | "green" | "red")
    progressed = pyqtSignal(float, str) # (0–100, label)
    finished   = pyqtSignal(bool)       # success

    def run(self):
        try:
            self._log("Connecting to Spotify...")
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="user-library-read playlist-read-private playlist-read-collaborative",
            ))

            self._log("Fetching liked songs...")
            liked_songs = []
            page = sp.current_user_saved_tracks(limit=50)
            while page:
                for item in page["items"]:
                    track  = item["track"]
                    title  = track["name"]
                    artist = track["artists"][0]["name"]
                    if title and artist:
                        liked_songs.append({"title": title, "artist": artist})
                page = sp.next(page) if page["next"] else None

            self._log(f"Found {len(liked_songs)} songs.\n")
            self._log("Connecting to YouTube Music...")
            ytmusic = YTMusic("browser.json")

            entries, total = [], len(liked_songs)

            for i, song in enumerate(liked_songs):
                query = f"{song['title']} {song['artist']}"
                try:
                    hits = ytmusic.search(query, filter="songs", limit=1)
                    if hits:
                        vid = hits[0]["videoId"]
                        ytmusic.rate_song(vid, "LIKE")
                        entries.append({**song, "status": "success", "yt_id": vid})
                        self._log(f"✓  {song['title']} — {song['artist']}", "green")
                    else:
                        entries.append({**song, "status": "not_found", "yt_id": None})
                        self._log(f"✗  Not found: {song['title']}", "red")
                except Exception as e:
                    entries.append({**song, "status": f"error: {e}", "yt_id": None})
                    self._log(f"✗  Error: {song['title']}", "red")

                self.progressed.emit(((i + 1) / total) * 100,
                                     f"{i + 1}/{total} songs processed")

            df      = pd.DataFrame(entries)
            os.makedirs("reports", exist_ok=True)
            base         = "reports/transfer_report"
            report_path  = f"{base}.csv"
            counter      = 1
            while os.path.exists(report_path):
                report_path = f"{base}_{counter}.csv"
                counter += 1
            df.to_csv(report_path, index=False)
            success = (df["status"] == "success").sum()

            self._log(f"\n✅  Done! {success}/{total} songs transferred.", "green")
            self._log(f"Report saved to {report_path}")
            self.progressed.emit(100, f"Complete — {success}/{total} transferred")
            self.finished.emit(True)

        except Exception as e:
            self._log(f"\n❌  Fatal error: {e}", "red")
            self.finished.emit(False)

    def _log(self, msg: str, colour: str = ""):
        self.logged.emit(msg, colour)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Songs Synchronizer")
        self.setFixedSize(620, 560)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(40, 28, 40, 28)
        lay.setSpacing(0)

        # Header
        header = QLabel("Songs Synchronizer")
        header.setFont(QFont("Helvetica", 22, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(header)
        lay.addSpacing(8)

        subtitle = QLabel("Spotify  →  YouTube Music")
        subtitle.setStyleSheet("color: #888888; background: transparent;")
        subtitle.setFont(QFont("Helvetica", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(subtitle)
        lay.addSpacing(20)

        # Log box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        lay.addWidget(self.log_box)
        lay.addSpacing(14)

        # Progress bar
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        lay.addSpacing(8)

        # Progress label
        self.prog_lbl = QLabel("Ready")
        self.prog_lbl.setStyleSheet("color: #888888; background: transparent;")
        self.prog_lbl.setFont(QFont("Helvetica", 11))
        self.prog_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.prog_lbl)
        lay.addSpacing(16)

        # Button
        self.btn = QPushButton("Start Transfer")
        self.btn.setFont(QFont("Helvetica", 13, QFont.Weight.Bold))
        self.btn.setFixedSize(200, 44)
        self.btn.clicked.connect(self.start)
        lay.addWidget(self.btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._thread = self._worker = None

    def _append(self, msg: str, colour: str):
        cursor = self.log_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(
            "#1DB954" if colour == "green" else
            "#FF4444" if colour == "red"   else "#ffffff"
        ))
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        self.log_box.setTextCursor(cursor)
        self.log_box.ensureCursorVisible()

    def _update_progress(self, pct: float, label: str):
        self.bar.setValue(int(pct))
        self.prog_lbl.setText(label)

    def start(self):
        self.btn.setEnabled(False)
        self.btn.setText("Transferring...")
        self.bar.setValue(0)
        self.prog_lbl.setText("Starting...")

        self._thread = QThread()
        self._worker = Worker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.logged.connect(self._append)
        self._worker.progressed.connect(self._update_progress)
        self._worker.finished.connect(self._done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _done(self, success: bool):
        self.btn.setEnabled(True)
        self.btn.setText("Run Again" if success else "Start Transfer")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(_QSS)
    w = App()
    w.show()
    sys.exit(app.exec())
