"""Tests for gui."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import (
    FIXTURE,
    FakeNetworkManager,
    FakeNetworkReply,
)
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QComboBox, QLineEdit

from figma_to_pyside6.adapters.figma_json import load_figma_document
from figma_to_pyside6.ui.main_window import WorkbenchMainWindow


def test_workbench_starts_with_three_step_flow(qt_app):
    window = WorkbenchMainWindow()

    assert window.windowTitle() == "Figma to PySide6 Workbench"
    assert window.centralWidget() is not None
    assert window.frame_list.count() == 0
    assert not window.generate_button.isEnabled()
    assert window.figma_token_input.echoMode() == QLineEdit.EchoMode.Password
    assert qt_app is not None


def test_workbench_starts_maximized_without_theme_switchers(qt_app):
    window = WorkbenchMainWindow()

    assert window.windowState() & Qt.WindowState.WindowMaximized
    assert window.findChild(QComboBox) is None
    assert "#00F0FF" in window.styleSheet().upper()


def test_verification_selects_frames_and_generates_project(qt_app, tmp_path):
    window = WorkbenchMainWindow()
    network = FakeNetworkManager()
    window._network_manager = network
    window.figma_link_input.setText("https://www.figma.com/design/AbC123/Mockup?node-id=4431-19072")
    window.figma_token_input.setText("test-token")

    window._verify_figma_link()

    assert network.request.url().path() == "/v1/files/AbC123/nodes"
    assert network.request.url().query() == "ids=4431:19072&depth=3"
    assert network.request.rawHeader("X-Figma-Token") == b"test-token"
    assert window.figma_token_input.text() == ""

    fixture_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    frame_nodes = fixture_payload["document"]["children"]
    payload = {
        "nodes": {
            "4431:19072": {
                "document": {
                    "id": "4431:19072",
                    "name": "PyGui Final Screens",
                    "type": "SECTION",
                    "children": [
                        *frame_nodes,
                        {
                            "id": "group:1",
                            "type": "GROUP",
                            "name": "Nested internals",
                            "children": [
                                {"id": "nested:1", "type": "FRAME", "name": "Nested frame"}
                            ],
                        },
                    ],
                }
            }
        }
    }
    window._finish_figma_verification(FakeNetworkReply(payload))

    assert window.document.name == "PyGui Final Screens"
    assert window.frame_list.count() == 2
    assert not window.generate_button.isEnabled()

    window.frame_list.item(0).setCheckState(Qt.CheckState.Checked)

    assert {frame.name for frame in window.selected_frames} == {"Login"}
    assert window.generate_button.isEnabled()

    output_dir = tmp_path / "generated"
    window.project_name_input.setText("GuiGenerated")
    window.output_dir_input.setText(str(output_dir))
    window._generate_project()

    pages_dir = output_dir / "src" / "ui" / "pages"
    assert (pages_dir / "login_page.py").exists()
    assert not (pages_dir / "dashboard_page.py").exists()


def test_invalid_figma_link_does_not_send_request(qt_app):
    window = WorkbenchMainWindow()
    network = FakeNetworkManager()
    window._network_manager = network
    window.figma_link_input.setText("https://example.com/not-figma")
    window.figma_token_input.setText("test-token")

    window._verify_figma_link()

    assert network.request is None
    assert "figma.com" in window.statusBar().currentMessage()


def test_unavailable_figma_file_cannot_be_generated(qt_app):
    window = WorkbenchMainWindow()
    network = FakeNetworkManager()
    window._network_manager = network
    window.figma_link_input.setText("https://www.figma.com/file/AbC123/Mockup")
    window.figma_token_input.setText("test-token")
    window._verify_figma_link()

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    window._finish_figma_verification(FakeNetworkReply(payload, status_code=403))

    assert window.document is None
    assert window.frame_list.count() == 0
    assert not window.generate_button.isEnabled()
    assert "permissions" in window.statusBar().currentMessage()


def test_b4_request_has_timeout_and_timeout_error_is_reported(qt_app):
    window = WorkbenchMainWindow()
    network = FakeNetworkManager()
    window._network_manager = network
    window.figma_link_input.setText("https://www.figma.com/design/AbC123/Mockup")
    window.figma_token_input.setText("test-token")

    window._verify_figma_link()

    assert network.request.transferTimeout() == 30_000
    assert network.request.url().query() == "depth=4"  # B2: reach frame children

    class TimedOut(FakeNetworkReply):
        def error(self):
            return QNetworkReply.NetworkError.OperationCanceledError

    window._finish_figma_verification(TimedOut({}))

    assert "did not respond" in window.statusBar().currentMessage()
    assert window.verify_button.isEnabled()
    assert window.verify_button.text() == "Verify link"


def test_b12_empty_project_name_and_output_dir_fall_back_to_defaults(
    qt_app: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B12: an empty output field must not write the project into the working directory."""
    from PySide6.QtCore import Qt

    from figma_to_pyside6.ui.main_window import WorkbenchMainWindow

    monkeypatch.chdir(tmp_path)
    window = WorkbenchMainWindow()
    window._set_document(load_figma_document(FIXTURE), source="test")
    window.frame_list.item(0).setCheckState(Qt.CheckState.Checked)
    window.project_name_input.setText("   ")
    window.output_dir_input.setText("")

    window._generate_project()

    assert (tmp_path / "generated_project" / "main.py").exists()
    assert not (tmp_path / "main.py").exists()
    assert "GeneratedApp" in (tmp_path / "generated_project/src/ui/main_window.py").read_text(
        encoding="utf-8"
    )


def test_b11_unwritable_output_is_reported_not_raised(qt_app: object, tmp_path: Path) -> None:
    """B11: an OSError while generating shows a message; the window stays usable."""
    from PySide6.QtCore import Qt

    from figma_to_pyside6.ui.main_window import WorkbenchMainWindow

    blocker = tmp_path / "file.txt"
    blocker.write_text("x", encoding="utf-8")
    window = WorkbenchMainWindow()
    window._set_document(load_figma_document(FIXTURE), source="test")
    window.frame_list.item(0).setCheckState(Qt.CheckState.Checked)
    window.output_dir_input.setText(str(blocker))

    window._generate_project()

    assert window.statusBar().currentMessage()
    assert window.result_label.text() == ""
