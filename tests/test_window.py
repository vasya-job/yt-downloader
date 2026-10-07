import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog

from ytgui.core.events import JobResult, ProgressEvent
from ytgui.core.options import Mode
from ytgui.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


class FakeWorker(QObject):
    event = Signal(object)
    done = Signal(object)
    instances: list["FakeWorker"] = []

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.started = False
        self.cancelled = False
        FakeWorker.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def isRunning(self):
        return self.started

    def wait(self, msecs=0):
        return True


@pytest.fixture
def window(app, tmp_path):
    FakeWorker.instances.clear()
    return MainWindow(settings_path=tmp_path / "settings.json", worker_factory=FakeWorker)


def fill(window, url="https://youtu.be/abc", folder="/tmp/out"):
    window.url_edit.setText(url)
    window.folder_edit.setText(folder)


def test_download_disabled_until_url_and_folder(window):
    assert not window.download_button.isEnabled() and not window.cancel_button.isEnabled()
    window.url_edit.setText("https://youtu.be/abc")
    assert not window.download_button.isEnabled()
    window.folder_edit.setText("/tmp/out")
    assert window.download_button.isEnabled()
    window.url_edit.setText("   ")
    assert not window.download_button.isEnabled()


def test_playlist_checkbox_follows_url(window):
    assert not window.playlist_check.isEnabled()
    window.url_edit.setText("https://www.youtube.com/playlist?list=PL1")
    assert window.playlist_check.isEnabled()
    window.playlist_check.setChecked(True)
    window.url_edit.setText("https://youtu.be/abc")
    assert not window.playlist_check.isEnabled() and not window.playlist_check.isChecked()


def test_mode_switch_changes_formats_and_rows(window):
    assert window.audio_radio.isChecked()
    assert [window.format_combo.itemText(i) for i in range(window.format_combo.count())] == ["MP3", "M4A", "OPUS", "WAV"]
    assert window.quality_row.isVisibleTo(window) and not window.height_combo.isVisibleTo(window)
    window.video_radio.setChecked(True)
    assert [window.format_combo.itemText(i) for i in range(window.format_combo.count())] == ["MP4", "MKV", "WebM"]
    assert window.height_combo.isVisibleTo(window) and not window.quality_row.isVisibleTo(window)


def test_wav_disables_quality_slider(window):
    assert window.quality_slider.isEnabled()
    window.format_combo.setCurrentIndex(3)
    assert not window.quality_slider.isEnabled()


def test_slider_right_end_is_best_quality(window):
    fill(window)
    window.quality_slider.setValue(9)
    assert window.quality_value.text().startswith("0")
    window.download_button.click()
    assert FakeWorker.instances[-1].options.audio_quality == 0


def test_start_builds_options_and_locks_ui(window):
    fill(window, folder="/tmp/Музыка")
    window.template_edit.setText("%(title)s [%(id)s].%(ext)s")
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    assert worker.started
    o = worker.options
    assert (o.url, o.folder, o.mode, o.audio_format) == ("https://youtu.be/abc", "/tmp/Музыка", Mode.AUDIO, "mp3")
    assert o.template == "%(title)s [%(id)s].%(ext)s" and o.playlist is False
    assert not window.download_button.isEnabled() and window.cancel_button.isEnabled()
    assert not window.url_edit.isEnabled() and not window.folder_edit.isEnabled()


def test_video_options_with_height_limit(window):
    fill(window)
    window.video_radio.setChecked(True)
    window.height_combo.setCurrentIndex(1)
    window.download_button.click()
    o = FakeWorker.instances[-1].options
    assert (o.mode, o.video_format, o.max_height) == (Mode.VIDEO, "mp4", 1080)


def test_progress_events_update_widgets(window):
    fill(window)
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    worker.event.emit(ProgressEvent("download", percent=62.0, downloaded=13002342, total=20971520, speed=1887437.0))
    assert window.progress.value() == 62
    assert "62%" in window.status_label.text()
    assert window.detail_label.text() == "12,4 МБ из 20,0 МБ (1,8 МБ/с)"
    worker.event.emit(ProgressEvent("item", text="[download] Downloading item 3 of 10", item_index=3, item_count=10))
    worker.event.emit(ProgressEvent("download", percent=10.0, downloaded=1, total=10))
    assert "3 из 10" in window.status_label.text()
    worker.event.emit(ProgressEvent("stage", text="Конвертация аудио…"))
    assert window.status_label.text() == "Конвертация аудио…"
    assert window.progress.maximum() == 0  # неопределённый индикатор
    worker.event.emit(ProgressEvent("line", text="[youtube] abc: Downloading webpage"))
    assert "Downloading webpage" in window.log.toPlainText()


def test_done_ok_reenables_ui_and_opens_folder(window, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toLocalFile())))
    fill(window, folder="/tmp/out")
    window.download_button.click()
    FakeWorker.instances[-1].done.emit(JobResult("ok", "Готово", 0))
    assert window.status_label.text() == "Готово" and window.progress.value() == 100
    assert window.download_button.isEnabled() and not window.cancel_button.isEnabled()
    assert window.url_edit.isEnabled()
    assert opened == ["/tmp/out"]


def test_done_ok_without_open_folder_option(window, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url)))
    fill(window)
    window.open_folder_check.setChecked(False)
    window.download_button.click()
    FakeWorker.instances[-1].done.emit(JobResult("ok", "Готово", 0))
    assert opened == []


def test_error_is_shown_as_plain_text(window):
    fill(window)
    window.download_button.click()
    FakeWorker.instances[-1].done.emit(JobResult("error", "Это приватное видео, доступ закрыт.", 1))
    assert window.status_label.text() == "Это приватное видео, доступ закрыт."
    assert window.status_label.property("error") is True
    assert window.download_button.isEnabled()


def test_cancel_button_cancels_worker_and_cancelled_result_resets(window):
    fill(window)
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    window.cancel_button.click()
    assert worker.cancelled and not window.cancel_button.isEnabled()
    worker.done.emit(JobResult("cancelled", "Отменено"))
    assert window.status_label.text() == "Отменено" and window.progress.value() == 0
    assert window.download_button.isEnabled()


def test_invalid_input_does_not_start_worker(window):
    fill(window, url="не ссылка")
    window.download_button.click()
    assert FakeWorker.instances == []
    assert "ссылк" in window.status_label.text()


def test_folder_persists_across_restart(app, tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    chosen = tmp_path / "Музыка"
    chosen.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(chosen)))
    first = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    first.browse_button.click()
    assert first.folder_edit.text() == str(chosen)
    second = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    assert second.folder_edit.text() == str(chosen)


def test_other_settings_are_restored(app, tmp_path):
    settings = tmp_path / "settings.json"
    first = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    first.video_radio.setChecked(True)
    first.format_combo.setCurrentIndex(2)  # WebM
    first.height_combo.setCurrentIndex(3)  # 480p
    first.cookies_combo.setCurrentIndex(1)  # Chrome
    first.open_folder_check.setChecked(False)
    first.url_edit.setText("https://youtu.be/abc")
    first.folder_edit.setText("/tmp/out")
    first.download_button.click()
    first.closeEvent(QCloseEvent())
    second = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    assert second.video_radio.isChecked()
    assert second.format_combo.currentData() == "webm"
    assert second.height_combo.currentData() == 480
    assert second.cookies_combo.currentData() == "chrome"
    assert not second.open_folder_check.isChecked()


def test_unwritable_settings_do_not_break_start(app, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    window = MainWindow(settings_path=blocker / "s.json", worker_factory=FakeWorker)
    FakeWorker.instances.clear()
    fill(window)
    window.download_button.click()
    assert FakeWorker.instances[-1].started
    window.closeEvent(QCloseEvent())


def test_close_cancels_running_worker(window):
    fill(window)
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    window.closeEvent(QCloseEvent())
    assert worker.cancelled


def test_window_width_is_fixed(window):
    assert window.minimumWidth() == window.maximumWidth() == 680
