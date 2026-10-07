from ytgui.core.events import ProgressEvent
from ytgui.core.progress import describe_download, format_bytes, parse_line


def test_download_line():
    ev = parse_line("YTG|downloading|1000|4000|NA|500.0|6")
    assert ev.kind == "download"
    assert ev.percent == 25.0
    assert (ev.downloaded, ev.total, ev.speed, ev.eta) == (1000, 4000, 500.0, 6)


def test_estimate_used_when_total_is_na():
    ev = parse_line("YTG|downloading|1000|NA|5000|NA|NA")
    assert ev.percent == 20.0
    assert ev.total == 5000
    assert ev.speed is None and ev.eta is None


def test_all_values_unknown():
    ev = parse_line("YTG|downloading|NA|NA|NA|NA|NA")
    assert ev.kind == "download"
    assert ev.percent is None and ev.downloaded is None and ev.total is None


def test_percent_is_capped_at_100():
    assert parse_line("YTG|finished|4100|4000|NA|NA|NA").percent == 100.0


def test_finished_line():
    ev = parse_line("YTG|finished|3433755|3433755|NA|254693.94410358524|NA")
    assert ev.percent == 100.0 and ev.text == "finished"


def test_malformed_progress_line_is_plain_line():
    ev = parse_line("YTG|oops")
    assert ev.kind == "line" and ev.text == "YTG|oops"


def test_playlist_item_line():
    ev = parse_line("[download] Downloading item 3 of 10")
    assert (ev.kind, ev.item_index, ev.item_count) == ("item", 3, 10)
    ev = parse_line("[download] Downloading video 2 of 5")
    assert (ev.item_index, ev.item_count) == (2, 5)


def test_stage_lines():
    assert parse_line("[ExtractAudio] Destination: /x/y.mp3") == ProgressEvent("stage", text="Конвертация аудио…")
    assert parse_line("[Merger] Merging formats into \"/x/y.mp4\"").text == "Объединение видео и аудио…"


def test_skipped_line():
    ev = parse_line("[download] /a/b.mp3 has already been downloaded")
    assert ev.kind == "skipped" and ev.text == "/a/b.mp3"


def test_other_line_is_log_without_newline():
    ev = parse_line("[youtube] abc: Downloading webpage\n")
    assert ev.kind == "line" and ev.text == "[youtube] abc: Downloading webpage"


def test_format_bytes():
    assert format_bytes(0) == "0 Б"
    assert format_bytes(1023) == "1023 Б"
    assert format_bytes(1536) == "1,5 КБ"
    assert format_bytes(int(12.4 * 1024 * 1024)) == "12,4 МБ"
    assert format_bytes(3 * 1024**3) == "3,0 ГБ"


def test_describe_download():
    ev = ProgressEvent("download", downloaded=13002342, total=20971520, speed=1887437.0)
    assert describe_download(ev) == "12,4 МБ из 20,0 МБ (1,8 МБ/с)"
    assert describe_download(ProgressEvent("download", downloaded=2048)) == "2,0 КБ"
    assert describe_download(ProgressEvent("download")) == ""
