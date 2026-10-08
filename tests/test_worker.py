import threading

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from ytgui.core.events import JobResult, ProgressEvent
from ytgui.core.options import DownloadOptions
from ytgui.ui.worker import DownloadWorker


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


class FakeJob:
    def __init__(self, options, on_event, fail=False):
        self._on_event = on_event
        self._fail = fail

    def cancel(self):
        pass

    def run(self):
        self._on_event(ProgressEvent("stage", text="Старт"))
        self._on_event(ProgressEvent("line", text="строка"))
        if self._fail:
            raise RuntimeError("boom")
        return JobResult("ok", "Готово")


def run_worker(fail):
    options = DownloadOptions(url="https://youtu.be/abc", folder="/tmp/out")
    worker = DownloadWorker(options, job_factory=lambda o, cb: FakeJob(o, cb, fail=fail))
    events, results, threads = [], [], []

    def on_event(event):
        threads.append(threading.current_thread())
        events.append(event)

    def on_done(result):
        threads.append(threading.current_thread())
        results.append(result)
        loop.quit()

    loop = QEventLoop()
    worker.event.connect(on_event)
    worker.done.connect(on_done)
    QTimer.singleShot(5000, loop.quit)
    worker.start()
    loop.exec()
    worker.wait(5000)
    return events, results, threads


def test_events_and_result_arrive_in_order_on_main_thread(app):
    events, results, threads = run_worker(fail=False)
    assert [(e.kind, e.text) for e in events] == [("stage", "Старт"), ("line", "строка")]
    assert len(results) == 1 and results[0].status == "ok" and results[0].message == "Готово"
    assert threads and all(t is threading.main_thread() for t in threads)


def test_job_exception_becomes_error_result(app):
    _, results, _ = run_worker(fail=True)
    assert len(results) == 1
    assert results[0].status == "error" and "Внутренняя ошибка" in results[0].message
