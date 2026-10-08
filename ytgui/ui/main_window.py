"""Единственное окно приложения."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSlider,
    QVBoxLayout, QWidget,
)

from ytgui import __version__
from ytgui.core import settings as settings_store
from ytgui.core.options import (
    AUDIO_FORMATS, COOKIE_BROWSERS, DEFAULT_TEMPLATE, HEIGHT_LIMITS, VIDEO_FORMATS,
    DownloadOptions, Mode, is_playlist_url,
)
from ytgui.core.progress import describe_download
from ytgui.ui.style import STYLESHEET
from ytgui.ui.worker import DownloadWorker

WINDOW_WIDTH = 680
FORMAT_LABELS = {"mp3": "MP3", "m4a": "M4A", "opus": "OPUS", "wav": "WAV", "mp4": "MP4", "mkv": "MKV", "webm": "WebM"}
HEIGHT_LABELS = {None: "Лучшее", 1080: "1080p", 720: "720p", 480: "480p"}
BROWSER_LABELS = {None: "Нет", "chrome": "Chrome", "firefox": "Firefox", "edge": "Edge"}

# Потоки, которые не успели завершиться при закрытии окна: держим обёртку живой до конца процесса.
_ORPHAN_WORKERS: list = []


def quality_text(quality: int) -> str:
    if quality == 0:
        return "0 · лучшее"
    if quality == 9:
        return "9 · минимальное"
    return str(quality)


class MainWindow(QWidget):
    def __init__(self, settings_path: str | Path | None = None, worker_factory=DownloadWorker) -> None:
        super().__init__()
        self._settings_path = settings_path
        self._worker_factory = worker_factory
        self._worker = None
        self._item_prefix = ""
        self._formats = {"audio": "mp3", "video": "mp4"}
        self.setWindowTitle("YouTube Загрузчик")
        self.setFixedWidth(WINDOW_WIDTH)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._connect()
        self._apply_settings(settings_store.load(settings_path))
        self._refresh()

    # ---- построение окна -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        caption = QLabel("Ссылка")
        caption.setObjectName("caption")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Вставьте ссылку на ролик, шортс или плейлист")
        self.url_edit.setClearButtonEnabled(True)
        root.addWidget(caption)
        root.addWidget(self.url_edit)

        what = QGroupBox("Что скачать")
        what_row = QHBoxLayout(what)
        self.audio_radio = QRadioButton("Только аудио")
        self.video_radio = QRadioButton("Видео")
        self.playlist_check = QCheckBox("Скачать весь плейлист")
        what_row.addWidget(self.audio_radio)
        what_row.addWidget(self.video_radio)
        what_row.addStretch(1)
        what_row.addWidget(self.playlist_check)
        root.addWidget(what)

        fmt_box = QGroupBox("Формат")
        self._fmt_form = QFormLayout(fmt_box)
        self.format_combo = QComboBox()
        self.height_combo = QComboBox()
        for height in HEIGHT_LIMITS:
            self.height_combo.addItem(HEIGHT_LABELS[height], height)
        self._fmt_form.addRow("Формат", self.format_combo)
        self._fmt_form.addRow("Качество видео", self.height_combo)
        root.addWidget(fmt_box)

        par_box = QGroupBox("Параметры")
        self._par_form = QFormLayout(par_box)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(0, 9)
        self.quality_slider.setPageStep(1)
        self.quality_value = QLabel()
        self.quality_value.setFixedWidth(110)
        self.quality_row = QWidget()
        quality_layout = QHBoxLayout(self.quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.addWidget(self.quality_slider, 1)
        quality_layout.addWidget(self.quality_value)
        self.template_edit = QLineEdit()
        self.cookies_combo = QComboBox()
        for browser in COOKIE_BROWSERS:
            self.cookies_combo.addItem(BROWSER_LABELS[browser], browser)
        self._par_form.addRow("Качество аудио", self.quality_row)
        self._par_form.addRow("Шаблон имени", self.template_edit)
        self._par_form.addRow("Cookies из браузера", self.cookies_combo)
        root.addWidget(par_box)

        save_box = QGroupBox("Куда сохранить")
        save_layout = QVBoxLayout(save_box)
        path_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Выберите папку")
        self.browse_button = QPushButton("Обзор…")
        path_row.addWidget(self.folder_edit, 1)
        path_row.addWidget(self.browse_button)
        self.open_folder_check = QCheckBox("Открыть папку после загрузки")
        save_layout.addLayout(path_row)
        save_layout.addWidget(self.open_folder_check)
        root.addWidget(save_box)

        buttons = QHBoxLayout()
        self.download_button = QPushButton("Скачать")
        self.download_button.setObjectName("primary")
        self.cancel_button = QPushButton("Отмена")
        buttons.addWidget(self.download_button, 1)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Готов к загрузке")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_label = QLabel("")
        self.detail_label.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.detail_label)
        root.addLayout(status_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        self.log.setFixedHeight(96)
        self.log.setPlaceholderText("Здесь появится журнал загрузки")
        root.addWidget(self.log)

        self.version_label = QLabel(f"Версия {__version__}")
        self.version_label.setObjectName("version")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.version_label)

        self._locked_while_running = (
            self.url_edit, self.audio_radio, self.video_radio, self.format_combo, self.height_combo,
            self.template_edit, self.cookies_combo, self.folder_edit, self.browse_button,
            self.open_folder_check,
        )

    def _connect(self) -> None:
        self.url_edit.textChanged.connect(self._refresh)
        self.folder_edit.textChanged.connect(self._refresh)
        self.folder_edit.editingFinished.connect(self._save_settings)
        self.audio_radio.toggled.connect(self._on_mode_changed)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        self.browse_button.clicked.connect(self._browse)
        self.download_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)

    # ---- состояние формы -------------------------------------------------------

    def _mode_key(self) -> str:
        return "audio" if self.audio_radio.isChecked() else "video"

    def _quality(self) -> int:
        return 9 - self.quality_slider.value()

    def _fill_formats(self) -> None:
        key = self._mode_key()
        formats = AUDIO_FORMATS if key == "audio" else VIDEO_FORMATS
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for fmt in formats:
            self.format_combo.addItem(FORMAT_LABELS[fmt], fmt)
        self.format_combo.setCurrentIndex(formats.index(self._formats[key]))
        self.format_combo.blockSignals(False)

    def _on_mode_changed(self) -> None:
        self._fill_formats()
        self._refresh()

    def _on_format_changed(self) -> None:
        self._formats[self._mode_key()] = self.format_combo.currentData()
        self._refresh()

    def _on_quality_changed(self) -> None:
        self.quality_value.setText(quality_text(self._quality()))

    def _refresh(self) -> None:
        running = self._worker is not None
        audio = self._mode_key() == "audio"
        is_playlist = is_playlist_url(self.url_edit.text())
        if not is_playlist:
            self.playlist_check.setChecked(False)
        self.playlist_check.setEnabled(is_playlist and not running)
        self._par_form.setRowVisible(self.quality_row, audio)
        self._fmt_form.setRowVisible(self.height_combo, not audio)
        for widget in self._locked_while_running:
            widget.setEnabled(not running)
        self.quality_slider.setEnabled(not running and self.format_combo.currentData() != "wav")
        can_start = bool(self.url_edit.text().strip()) and bool(self.folder_edit.text().strip())
        self.download_button.setEnabled(can_start and not running)
        self.cancel_button.setEnabled(running)
        self._fit_height()

    def _fit_height(self) -> None:
        self.layout().activate()
        height = self.layout().totalHeightForWidth(WINDOW_WIDTH)
        if height <= 0:
            height = self.sizeHint().height()
        if self.height() != height:
            self.resize(WINDOW_WIDTH, height)

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self._fit_height()

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    # ---- настройки -------------------------------------------------------------

    def _apply_settings(self, s: settings_store.Settings) -> None:
        self._formats = {"audio": s.audio_format, "video": s.video_format}
        self.audio_radio.setChecked(s.mode == "audio")
        self.video_radio.setChecked(s.mode == "video")
        self._fill_formats()
        self.quality_slider.setValue(9 - s.audio_quality)
        self._on_quality_changed()
        self.height_combo.setCurrentIndex(HEIGHT_LIMITS.index(s.max_height))
        self.template_edit.setText(s.template)
        self.cookies_combo.setCurrentIndex(COOKIE_BROWSERS.index(s.cookies_browser))
        self.folder_edit.setText(s.folder)
        self.open_folder_check.setChecked(s.open_folder)

    def _save_settings(self) -> None:
        current = settings_store.Settings(
            folder=self.folder_edit.text().strip(),
            mode=self._mode_key(),
            audio_format=self._formats["audio"],
            audio_quality=self._quality(),
            video_format=self._formats["video"],
            max_height=self.height_combo.currentData(),
            template=self.template_edit.text().strip() or DEFAULT_TEMPLATE,
            cookies_browser=self.cookies_combo.currentData(),
            open_folder=self.open_folder_check.isChecked(),
        )
        try:
            settings_store.save(current, self._settings_path)
        except OSError as exc:
            self._append_log(f"Не удалось сохранить настройки: {exc.strerror or exc}")

    # ---- действия --------------------------------------------------------------

    def _build_options(self) -> DownloadOptions:
        return DownloadOptions(
            url=self.url_edit.text().strip(),
            folder=self.folder_edit.text().strip(),
            mode=Mode.AUDIO if self._mode_key() == "audio" else Mode.VIDEO,
            audio_format=self._formats["audio"],
            audio_quality=self._quality(),
            video_format=self._formats["video"],
            max_height=self.height_combo.currentData(),
            template=self.template_edit.text().strip() or DEFAULT_TEMPLATE,
            cookies_browser=self.cookies_combo.currentData(),
            playlist=self.playlist_check.isChecked(),
        )

    def _browse(self) -> None:
        start = self.folder_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Выберите папку", start)
        if chosen:
            self.folder_edit.setText(chosen)
            self._save_settings()

    def _start(self) -> None:
        options = self._build_options()
        try:
            options.validate()
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self._save_settings()
        self.log.clear()
        self._item_prefix = ""
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.detail_label.clear()
        self._set_status("Подготовка…")
        self._worker = self._worker_factory(options)
        self._worker.event.connect(self._on_event)
        self._worker.done.connect(self._on_done)
        self._refresh()
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker is not None:
            self.cancel_button.setEnabled(False)
            self._set_status("Отмена…")
            self._worker.cancel()

    def _on_event(self, event) -> None:
        if event.kind == "download":
            if event.percent is not None:
                self.progress.setRange(0, 100)
                self.progress.setValue(int(event.percent))
                self._set_status(f"{self._item_prefix}Скачивание… {int(event.percent)}%")
            else:
                self.progress.setRange(0, 0)
                self._set_status(f"{self._item_prefix}Скачивание…")
            self.detail_label.setText(describe_download(event))
        elif event.kind == "item":
            self._item_prefix = f"Элемент {event.item_index} из {event.item_count}. "
            self._append_log(event.text)
        elif event.kind == "stage":
            self.progress.setRange(0, 0)
            self.detail_label.clear()
            self._set_status(event.text)
        elif event.kind == "skipped":
            self._append_log(f"Уже скачано: {event.text}")
        else:
            self._append_log(event.text)

    def _on_done(self, result) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self.progress.setRange(0, 100)
        self.detail_label.clear()
        if result.status == "ok":
            self.progress.setValue(100)
            self._set_status(result.message)
            if self.open_folder_check.isChecked():
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_edit.text().strip()))
        elif result.status == "cancelled":
            self.progress.setValue(0)
            self._set_status(result.message)
        else:
            self.progress.setValue(0)
            self._set_status(result.message, error=True)
            self._append_log(result.message)
        self._refresh()

    def closeEvent(self, event) -> None:
        self._save_settings()
        worker = self._worker
        if worker is not None:
            worker.cancel()
            if not worker.wait(5000):
                _ORPHAN_WORKERS.append(worker)
        event.accept()
