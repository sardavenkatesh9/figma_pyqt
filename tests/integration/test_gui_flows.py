"""Workbench flows: verification outcomes, selection, dialogs and application start-up."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from helpers import FIXTURE, FakeNetworkManager, FakeNetworkReply
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

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
        "Login  |  360 x 640",
        "Dashboard  |  412 x 732",
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
