"""Workbench flows: verification outcomes, selection, dialogs and application start-up."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from helpers import FIXTURE, FakeFigmaClient, FakeNetworkManager, FakeNetworkReply
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from figma_to_pyside6.adapters.figma_api import document_from_response
from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.ui import main_window
from figma_to_pyside6.ui.main_window import WorkbenchMainWindow

FILE_LINK = "https://www.figma.com/design/AbC123/Mockup"
NODE_LINK = f"{FILE_LINK}?node-id=1-2"


@pytest.fixture
def window(qt_app: QApplication) -> WorkbenchMainWindow:
    """A workbench whose network layer records requests instead of sending them."""
    win = WorkbenchMainWindow()
    win._network_manager = FakeNetworkManager()  # type: ignore[assignment]
    return win


def _verify(win: WorkbenchMainWindow, link: str = FILE_LINK, token: str = "tok") -> None:
    win.figma_link_input.setText(link)
    win.figma_token_input.setText(token)
    win._verify_figma_link()


def _file_payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _check(win: WorkbenchMainWindow, *rows: int) -> None:
    for row in rows:
        win.frame_list.item(row).setCheckState(Qt.CheckState.Checked)


# ---------------------------------------------------------------- verification
def test_verify_requires_a_token(window: WorkbenchMainWindow) -> None:
    _verify(window, token="  ")

    assert "token" in window.statusBar().currentMessage()
    assert window._network_manager.request is None  # type: ignore[attr-defined]
    assert window.verify_button.isEnabled()


def test_verify_disables_button_while_waiting_and_clears_token(window: WorkbenchMainWindow) -> None:
    _verify(window)

    assert not window.verify_button.isEnabled()
    assert window.verify_button.text() == "Verifying…"
    assert window.figma_token_input.text() == ""


def test_successful_whole_file_verification_loads_frames(window: WorkbenchMainWindow) -> None:
    _verify(window)
    reply = FakeNetworkReply(_file_payload())

    window._finish_figma_verification(reply)  # type: ignore[arg-type]

    assert window.document is not None
    assert [window.frame_list.item(i).text() for i in range(window.frame_list.count())] == [
        "Login\n360 × 640  ·  2 layers  ·  ID frame-1",
        "Dashboard\n412 × 732  ·  1 layer  ·  ID frame-2",
    ]
    assert window.frame_list.isEnabled()
    assert "Verified: Sample Screen" in window.document_label.text()
    assert reply.deleted
    assert window._pending_source_url is None and window._pending_node_id is None
    assert window.verify_button.isEnabled()


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (FakeNetworkReply({}, status_code=403), "permissions"),
        (FakeNetworkReply({}, status_code=0), "permissions"),
        (FakeNetworkReply({}, status_code=500), "permissions"),
        (
            FakeNetworkReply({}, error=QNetworkReply.NetworkError.HostNotFoundError),
            "permissions",
        ),
        (
            FakeNetworkReply({}, error=QNetworkReply.NetworkError.OperationCanceledError),
            "did not respond",
        ),
        (FakeNetworkReply(b"<html>not json"), "Expecting value"),
        (FakeNetworkReply({"document": {"children": []}}), "No FRAME nodes"),
    ],
    ids=["403", "no-status", "500", "network-error", "timeout", "bad-json", "no-frames"],
)
def test_failed_verification_clears_state_and_reports(
    window: WorkbenchMainWindow, reply: FakeNetworkReply, message: str
) -> None:
    _verify(window)

    window._finish_figma_verification(reply)  # type: ignore[arg-type]

    assert window.document is None
    assert window.frame_list.count() == 0
    assert not window.generate_button.isEnabled()
    assert message in window.statusBar().currentMessage()
    assert reply.deleted and window.verify_button.isEnabled()


def test_missing_node_in_node_response_is_reported(window: WorkbenchMainWindow) -> None:
    _verify(window, NODE_LINK)

    window._finish_figma_verification(FakeNetworkReply({"nodes": {}}))  # type: ignore[arg-type]

    assert "could not be found" in window.statusBar().currentMessage()


def test_a_new_verification_discards_the_previous_document(window: WorkbenchMainWindow) -> None:
    window._set_document(load_figma_document(FIXTURE), source="x")
    assert window.frame_list.count() == 2

    _verify(window, link="https://example.com/nope")

    assert window.document is None and window.frame_list.count() == 0


# ---------------------------------------------------------------- selection
def test_selection_summary_and_generate_button(window: WorkbenchMainWindow) -> None:
    window._set_document(load_figma_document(FIXTURE), source="x")
    assert window.frame_summary.text() == "No frames selected"
    assert not window.generate_button.isEnabled()

    _check(window, 1)
    assert window.frame_summary.text() == "1/2 selected: Dashboard"
    assert window.generate_button.isEnabled()

    _check(window, 0)
    assert window.frame_summary.text() == "2/2 selected: Login, Dashboard"

    window.frame_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    window.frame_list.item(1).setCheckState(Qt.CheckState.Unchecked)
    assert not window.generate_button.isEnabled()


def test_select_all_and_clear_buttons(window: WorkbenchMainWindow) -> None:
    assert not window.select_all_button.isEnabled()
    assert not window.clear_button.isEnabled()
    window._set_document(load_figma_document(FIXTURE), source="x")
    assert window.select_all_button.isEnabled() and window.clear_button.isEnabled()

    window.select_all_button.click()
    assert [f.name for f in window.selected_frames] == ["Login", "Dashboard"]
    assert window.generate_button.isEnabled()

    window.clear_button.click()
    assert window.selected_frames == []
    assert not window.generate_button.isEnabled()

    window._clear_document_state()
    assert not window.select_all_button.isEnabled()


def test_update_selection_without_a_document_is_safe(window: WorkbenchMainWindow) -> None:
    window._update_selected_frames()

    assert window.frame_summary.text() == "No document loaded"
    assert window.selected_frames == []


# ---------------------------------------------------------------- generate
def test_generate_without_document_or_selection_only_warns(
    window: WorkbenchMainWindow, tmp_path: Path
) -> None:
    window.output_dir_input.setText(str(tmp_path / "out"))

    window._generate_project()
    assert "verify a Figma file" in window.statusBar().currentMessage()

    window._set_document(load_figma_document(FIXTURE), source="x")
    window._generate_project()
    assert "at least one frame" in window.statusBar().currentMessage()
    assert not (tmp_path / "out").exists()


def test_generate_reports_warnings_in_result_label(
    window: WorkbenchMainWindow, tmp_path: Path
) -> None:
    document = load_figma_document(FIXTURE)
    document.frames[0].children[0].warnings.append("Unsupported Figma node type: X")
    window._set_document(document, source="x")
    _check(window, 0)
    window.output_dir_input.setText(str(tmp_path / "out"))

    window._generate_project()

    assert "Project generated at" in window.result_label.text()
    assert "1 warning(s)" in window.result_label.text()


# ---------------------------------------------------------------- dialogs
def test_browse_sets_output_directory_only_when_chosen(
    window: WorkbenchMainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.output_dir_input.setText("original")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a, **_k: "")
    window._browse_output_directory()
    assert window.output_dir_input.text() == "original"

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_a, **_k: "C:/chosen")
    window._browse_output_directory()
    assert window.output_dir_input.text() == "C:/chosen"


@pytest.mark.parametrize(
    ("kind", "method"),
    [("warning", "warning"), ("critical", "critical"), ("info", "information")],
)
def test_message_uses_message_box_outside_offscreen_mode(
    window: WorkbenchMainWindow,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    method: str,
) -> None:
    shown: list[str] = []
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, name, lambda *_a, _n=name: shown.append(_n))

    window._show_message("t", "m", kind=kind)

    assert shown == [method]


# ---------------------------------------------------------------- start-up
def test_main_shows_the_window_maximized(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(WorkbenchMainWindow, "showMaximized", lambda self: calls.append("max"))
    monkeypatch.setattr(QApplication, "exec", lambda *_a: calls.append("exec") or 0)

    main_window.main()

    assert calls == ["max", "exec"]
    assert not qt_app.windowIcon().isNull()


def test_frame_rows_show_name_page_size_layers_and_id(window: WorkbenchMainWindow) -> None:
    payload = {
        "name": "File",
        "document": {
            "type": "DOCUMENT",
            "children": [
                {
                    "type": "CANVAS",
                    "name": "Onboarding",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Welcome",
                            "width": 390,
                            "height": 844,
                        },
                        {
                            "id": "1:2",
                            "type": "FRAME",
                            "name": "Welcome",
                            "width": 390,
                            "height": 844,
                        },
                    ],
                },
                {
                    "type": "CANVAS",
                    "name": "Settings",
                    "children": [
                        {"id": "2:1", "type": "FRAME", "name": "Welcome", "width": 1, "height": 2}
                    ],
                },
            ],
        },
    }
    window._set_document(document_from_response(payload, None, "x"), source="x")

    texts = [window.frame_list.item(i).text() for i in range(3)]
    assert texts[0] == (
        "Welcome  (1 of 3)\nOnboarding  \u00b7  390 \u00d7 844  \u00b7  0 layers  \u00b7  ID 1:1"
    )
    assert texts[1].startswith("Welcome  (2 of 3)")  # same name: numbered and given its node id
    assert texts[2].startswith("Welcome  (3 of 3)\nSettings")  # and told apart by page
    assert "ID 2:1" in window.frame_list.item(2).toolTip()


def test_frame_rows_render_without_errors(window: WorkbenchMainWindow, qtlog: Any) -> None:
    window._set_document(load_figma_document(FIXTURE), source="x")
    window.resize(900, 600)
    window.show()

    image = window.frame_list.grab()

    assert not image.isNull()
    assert window.frame_list.sizeHintForRow(0) == 58
    # regression: the style sheet sizes fonts in pixels, and deriving the row fonts from
    # pointSizeF() (-1) made Qt print "QFont::setPointSizeF: Point size <= 0"
    assert not [r for r in qtlog.records if "Point size" in r.message]


# ---------------------------------------------------------------- background generation
def _verified_window(window: WorkbenchMainWindow, tmp_path: Path) -> list[dict[str, Any]]:
    """A window that verified the fixture file with a token and has the first frame ticked."""
    frames = _file_payload()["document"]["children"]
    _verify(window, token="tok")
    window._finish_figma_verification(FakeNetworkReply(_file_payload()))  # type: ignore[arg-type]
    _check(window, 0)
    window.output_dir_input.setText(str(tmp_path / "out"))
    return frames


def test_token_is_kept_in_memory_only_and_forgotten_on_reverify_or_close(
    window: WorkbenchMainWindow, tmp_path: Path
) -> None:
    _verified_window(window, tmp_path)
    assert window._session_token == "tok" and window.figma_token_input.text() == ""

    _verify(window, link="https://example.com/nope", token="tok2")  # a failed new attempt
    assert window._session_token is None

    _verified_window(window, tmp_path)
    window.close()
    assert window._session_token is None


def test_generation_runs_in_the_background_and_disables_the_buttons(
    window: WorkbenchMainWindow, qtbot: Any, tmp_path: Path
) -> None:
    import threading

    release = threading.Event()
    frames = _verified_window(window, tmp_path)

    class Slow(FakeFigmaClient):
        def get_json(self, url: str) -> dict[str, Any]:
            release.wait(5)
            return super().get_json(url)

    window._client_factory = lambda token: Slow({f["id"]: f for f in frames})
    assert window.progress_bar.isHidden()  # idle: no bar
    window._generate_project()

    assert not window.progress_bar.isHidden() and window.progress_bar.value() == 0
    assert window.busy and not window.verify_button.isEnabled()
    assert window.generate_button.text() == "Generating…" and not window.generate_button.isEnabled()
    release.set()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.verify_button.isEnabled() and window.generate_button.isEnabled()
    assert window.progress_bar.isHidden()  # the bar goes away when the job is done
    assert (tmp_path / "out" / "main.py").exists()


def test_figma_errors_during_generation_are_shown_not_raised(
    window: WorkbenchMainWindow, qtbot: Any, tmp_path: Path
) -> None:
    from figma_to_pyside6.adapters.figma_client import FigmaApiError

    _verified_window(window, tmp_path)

    class Denied(FakeFigmaClient):
        def get_json(self, url: str) -> dict[str, Any]:
            raise FigmaApiError("Figma refused access (check the token and file permissions).")

    window._client_factory = lambda token: Denied({})
    window._generate_project()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)

    assert "refused access" in window.result_label.text()
    assert not (tmp_path / "out" / "main.py").exists()
    assert window.generate_button.isEnabled()  # the user can fix the token and retry


def test_clients_are_created_with_the_session_token(
    window: WorkbenchMainWindow, qtbot: Any, tmp_path: Path
) -> None:
    frames = _verified_window(window, tmp_path)
    seen: list[str] = []

    def factory(token: str) -> FakeFigmaClient:
        seen.append(token)
        return FakeFigmaClient({f["id"]: f for f in frames})

    window._client_factory = factory
    window._generate_project()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)

    assert seen == ["tok"]


def test_progress_bar_shows_stage_and_percentage_instead_of_status_messages(
    window: WorkbenchMainWindow,
) -> None:
    window.statusBar().showMessage("Ready")
    window._set_busy(True)
    assert window.statusBar().currentMessage() == ""  # the footer text makes room for the bar

    window._on_generation_progress("Downloading images 3/8", 62)

    assert window.progress_bar.value() == 62
    assert window.progress_bar.format() == "Downloading images 3/8  —  %p%"
    assert window.statusBar().currentMessage() == ""  # progress no longer spams the footer
    window._set_busy(False)
    assert window.progress_bar.isHidden()


def test_progress_bar_is_hidden_after_a_failed_generation(
    window: WorkbenchMainWindow, qtbot: Any, tmp_path: Path
) -> None:
    from figma_to_pyside6.adapters.figma_client import FigmaApiError

    _verified_window(window, tmp_path)

    class Denied(FakeFigmaClient):
        def get_json(self, url: str) -> dict[str, Any]:
            raise FigmaApiError("Figma refused access (check the token and file permissions).")

    window._client_factory = lambda token: Denied({})
    window._generate_project()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)

    assert window.progress_bar.isHidden()


# ---------------------------------------------------------------- shutdown, cancel, Ctrl+C
def test_row_size_hint_is_fixed_and_does_not_measure_text(window: WorkbenchMainWindow) -> None:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtWidgets import QStyleOptionViewItem

    from figma_to_pyside6.ui.main_window import _FrameRowDelegate

    option = QStyleOptionViewItem()
    option.rect.setWidth(777)

    size = _FrameRowDelegate().sizeHint(option, QModelIndex())

    assert (size.width(), size.height()) == (777, _FrameRowDelegate.ROW_HEIGHT)


def test_worker_stops_at_the_next_progress_report_after_cancel(qtbot: Any) -> None:
    from figma_to_pyside6.ui.main_window import _GenerateWorker

    steps: list[str] = []

    def job(progress: Any) -> Any:
        progress("one", 10)
        steps.append("one")
        worker.cancel()
        progress("two", 20)  # raises GenerationCancelled
        steps.append("two")

    worker = _GenerateWorker(job)
    outcomes: list[str] = []
    worker.succeeded.connect(lambda _r: outcomes.append("succeeded"))
    worker.failed.connect(lambda _m: outcomes.append("failed"))

    with qtbot.waitSignal(worker.finished, timeout=2000):
        worker.run()

    assert steps == ["one"] and outcomes == []  # cancelled quietly: neither success nor error


def test_closing_during_generation_cancels_it_without_qthread_warnings(
    window: WorkbenchMainWindow, qtlog: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import threading

    from figma_to_pyside6 import config

    monkeypatch.setattr(config, "SHUTDOWN_JOIN_SECONDS", 0.05)  # do not wait for the stuck call
    proceed = threading.Event()
    frames = _verified_window(window, tmp_path)

    class Gated(FakeFigmaClient):
        def get_json(self, url: str) -> dict[str, Any]:
            proceed.wait(5)  # a request that is still in flight when the window closes
            return super().get_json(url)

    window._client_factory = lambda token: Gated({f["id"]: f for f in frames})
    window._generate_project()
    thread = window._thread
    assert thread is not None and thread.is_alive()

    window.close()  # must return promptly even though the job is stuck
    assert window._session_token is None
    proceed.set()
    thread.join(5)

    assert not thread.is_alive()  # the job noticed the cancel at its next step and ended
    assert not (tmp_path / "out" / "main.py").exists()  # nothing half-written
    assert not [r for r in qtlog.records if "QThread" in r.message]


def test_ctrl_c_closes_the_windows_instead_of_raising_inside_qt(
    window: WorkbenchMainWindow, qtbot: Any
) -> None:
    import signal

    from figma_to_pyside6.ui.main_window import install_interrupt_handler

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    previous = signal.getsignal(signal.SIGINT)
    window.show()
    timer = install_interrupt_handler(app)
    try:
        signal.raise_signal(signal.SIGINT)
        qtbot.waitUntil(lambda: not window.isVisible(), timeout=3000)
    finally:
        timer.stop()
        signal.signal(signal.SIGINT, previous)

    assert not window.isVisible()
