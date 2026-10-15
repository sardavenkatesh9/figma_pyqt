from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QLineEdit

from figma_to_pyside6.adapters.figma_api import extract_figma_node_id
from figma_to_pyside6.ui.main_window import WorkbenchMainWindow

FIXTURE = Path(__file__).parent / "fixtures" / "figma_json" / "sample_figma.json"


@pytest.fixture
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


class FakeNetworkManager:
    def __init__(self):
        self.request = None

    def get(self, request):
        self.request = request


class FakeNetworkReply:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def error(self):
        return QNetworkReply.NetworkError.NoError

    def attribute(self, attribute):
        if attribute == QNetworkRequest.Attribute.HttpStatusCodeAttribute:
            return self.status_code
        return None

    def readAll(self):
        return json.dumps(self.payload).encode("utf-8")

    def deleteLater(self):
        pass


def test_workbench_starts_with_three_step_flow(qt_app):
    window = WorkbenchMainWindow()

    assert window.windowTitle() == "Figma to PySide6 Workbench"
    assert window.centralWidget() is not None
    assert window.frame_list.count() == 0
    assert not window.generate_button.isEnabled()
    assert window.figma_token_input.echoMode() == QLineEdit.EchoMode.Password
    assert qt_app is not None


def test_verification_selects_frames_and_generates_project(qt_app, tmp_path):
    window = WorkbenchMainWindow()
    network = FakeNetworkManager()
    window._network_manager = network
    window.figma_link_input.setText("https://www.figma.com/design/AbC123/Mockup?node-id=4431-19072")
    window.figma_token_input.setText("test-token")

    window._verify_figma_link()

    assert network.request.url().path() == "/v1/files/AbC123/nodes"
    assert network.request.url().query() == "ids=4431:19072&depth=2"
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

    generated_source = (output_dir / "main.py").read_text(encoding="utf-8")
    assert "Login" in generated_source
    assert "Dashboard" not in generated_source


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


def test_extract_figma_node_id_from_link():
    assert (
        extract_figma_node_id("https://www.figma.com/design/AbC123/Mockup?node-id=4431-19072")
        == "4431:19072"
    )
