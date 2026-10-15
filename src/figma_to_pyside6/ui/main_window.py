"""Desktop workbench: verify a Figma link, pick frames, generate a project."""

from __future__ import annotations

import dataclasses
import json
import logging
import os

from PySide6.QtCore import Qt, QUrl, QUrlQuery
from PySide6.QtGui import QColor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from figma_to_pyside6 import config
from figma_to_pyside6.adapters.figma_api import (
    build_files_request,
    document_from_response,
    extract_figma_file_key,
    extract_figma_node_id,
)
from figma_to_pyside6.application.conversion_service import convert_document
from figma_to_pyside6.domain.models import FigmaDocument, FigmaFrame
from figma_to_pyside6.resources import app_icon
from figma_to_pyside6.theme import COLORS, build_stylesheet

logger = logging.getLogger(__name__)

_NO_FILE_TEXT = "No file verified"
_LOAD_FRAMES_HINT = "Verify a Figma file to load its frames"
_FIGMA_ACCESS_ERROR = (
    "Could not access the Figma file. Check the link, token, and file permissions."
)
_FIGMA_TIMEOUT_ERROR = "Figma did not respond in time. Check your connection and try again."
_CONTENT_MARGINS = (32, 24, 32, 24)


def _glow(widget: QWidget, color: str, blur: int) -> None:
    """Give ``widget`` a neon glow; QSS has no box-shadow so use a graphics effect."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setColor(QColor(color))
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)


def _step_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("stepLabel")
    return label


class WorkbenchMainWindow(QMainWindow):
    """Three-step workbench: verify link, select frames, generate."""

    def __init__(self) -> None:
        """Build the window; it opens maximized."""
        super().__init__()
        self.document: FigmaDocument | None = None
        self.selected_frames: list[FigmaFrame] = []
        self._pending_source_url: str | None = None
        self._pending_node_id: str | None = None
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._finish_figma_verification)
        self._create_widgets()
        self.setWindowTitle("Figma to PySide6 Workbench")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(build_stylesheet())
        self.resize(*config.WINDOW_DEFAULT_SIZE)
        self.setMinimumSize(*config.WINDOW_MIN_SIZE)
        self.setWindowState(Qt.WindowState.WindowMaximized)
        self._build_ui()
        _glow(self.title_label, COLORS["cyan"], 28)
        _glow(self.generate_button, COLORS["cyan"], 36)
        _glow(self.verify_button, COLORS["cyan"], 22)

    # ------------------------------------------------------------------ construction
    def _create_widgets(self) -> None:
        self.title_label = QLabel("FIGMA  →  PYSIDE6")
        self.title_label.setObjectName("appTitle")
        self.figma_link_input = QLineEdit()
        self.figma_link_input.setObjectName("figmaLinkInput")
        self.figma_link_input.setPlaceholderText("https://www.figma.com/design/...")
        self.figma_token_input = QLineEdit()
        self.figma_token_input.setObjectName("figmaTokenInput")
        self.figma_token_input.setPlaceholderText("Figma personal access token")
        self.figma_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.verify_button = QPushButton("Verify link")
        self.verify_button.clicked.connect(self._verify_figma_link)
        self.document_label = QLabel(_NO_FILE_TEXT)
        self.frame_list = QListWidget()
        self.frame_list.setObjectName("frameList")
        self.frame_list.setEnabled(False)
        self.frame_list.itemChanged.connect(self._update_selected_frames)
        self.frame_summary = QLabel(_LOAD_FRAMES_HINT)
        self.project_name_input = QLineEdit(config.DEFAULT_PROJECT_NAME)
        self.project_name_input.setObjectName("projectNameInput")
        self.project_name_input.setPlaceholderText("Project name")
        self.output_dir_input = QLineEdit(str(config.default_output_dir()))
        self.output_dir_input.setObjectName("outputDirectoryInput")
        self.generate_button = QPushButton("Generate project")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate_project)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)

    def _build_ui(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(*_CONTENT_MARGINS)
        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch(1)
        outer.addLayout(header)

        content = QWidget()
        content.setObjectName("workflowContent")
        content.setMaximumWidth(config.CONTENT_MAX_WIDTH)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 28, 0, 12)
        layout.setSpacing(16)
        self._add_verify_step(layout)
        self._add_select_step(layout)
        self._add_generate_step(layout)
        outer.addWidget(content, 1, Qt.AlignmentFlag.AlignHCenter)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

    def _add_verify_step(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_step_label("01  VERIFY FIGMA FILE"))
        layout.addWidget(self.figma_link_input)
        credentials = QHBoxLayout()
        credentials.addWidget(self.figma_token_input, 1)
        credentials.addWidget(self.verify_button)
        layout.addLayout(credentials)
        layout.addWidget(self.document_label)

    def _add_select_step(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_step_label("02  SELECT FRAMES"))
        layout.addWidget(self.frame_list, 1)
        layout.addWidget(self.frame_summary)

    def _add_generate_step(self, layout: QVBoxLayout) -> None:
        layout.addWidget(_step_label("03  GENERATE PROJECT"))
        layout.addWidget(self.project_name_input)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_input, 1)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_output_directory)
        output_row.addWidget(browse_button)
        layout.addLayout(output_row)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.result_label)

    # ------------------------------------------------------------------ document state
    def _set_document(self, document: FigmaDocument, *, source: str) -> None:
        self.document = document
        self.selected_frames = []
        self.result_label.clear()
        self.document_label.setText(f"Verified: {document.name}")
        self.frame_list.clear()
        self.frame_list.setEnabled(True)
        for frame in document.frames:
            item = QListWidgetItem(f"{frame.name}  |  {frame.width} x {frame.height}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.frame_list.addItem(item)
        self._update_selected_frames()
        self.statusBar().showMessage(f"{len(document.frames)} frames loaded from {source}")

    def _clear_document_state(self) -> None:
        self.document = None
        self.selected_frames = []
        self.frame_list.clear()
        self.frame_list.setEnabled(False)
        self.document_label.setText(_NO_FILE_TEXT)
        self.frame_summary.setText(_LOAD_FRAMES_HINT)
        self.generate_button.setEnabled(False)
        self.result_label.clear()

    def _update_selected_frames(self) -> None:
        if self.document is None:
            self.selected_frames = []
            self.frame_summary.setText("No document loaded")
            self.generate_button.setEnabled(False)
            return

        self.selected_frames = [
            frame
            for index, frame in enumerate(self.document.frames)
            if self.frame_list.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not self.selected_frames:
            self.frame_summary.setText("No frames selected")
        else:
            names = ", ".join(frame.name for frame in self.selected_frames)
            self.frame_summary.setText(
                f"{len(self.selected_frames)}/{len(self.document.frames)} selected: {names}"
            )
        self.generate_button.setEnabled(bool(self.selected_frames))

    # ------------------------------------------------------------------ Figma verification
    def _verify_figma_link(self) -> None:
        self._clear_document_state()
        link = self.figma_link_input.text().strip()
        token = self.figma_token_input.text().strip()
        if not token:
            self.statusBar().showMessage("Enter a Figma personal access token to verify this file")
            return
        try:
            file_key = extract_figma_file_key(link)
            node_id = extract_figma_node_id(link)
        except ValueError as exc:
            self.statusBar().showMessage(str(exc))
            return

        self._pending_source_url = link
        self._pending_node_id = node_id
        self.verify_button.setEnabled(False)
        self.verify_button.setText("Verifying…")
        url, items = build_files_request(file_key, node_id)
        request_url = QUrl(url)
        query = QUrlQuery()
        for key, value in items:
            query.addQueryItem(key, value)
        request_url.setQuery(query)
        request = QNetworkRequest(request_url)
        request.setRawHeader(b"X-Figma-Token", token.encode("utf-8"))
        request.setTransferTimeout(config.FIGMA_REQUEST_TIMEOUT_MS)
        self._network_manager.get(request)
        self.figma_token_input.clear()
        self.statusBar().showMessage("Verifying Figma file and loading frames…")

    def _finish_figma_verification(self, reply: QNetworkReply) -> None:
        try:
            status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
                raise ValueError(_FIGMA_TIMEOUT_ERROR)
            if (
                reply.error() != QNetworkReply.NetworkError.NoError
                or not status_code
                or not 200 <= status_code < 300
            ):
                raise ValueError(_FIGMA_ACCESS_ERROR)
            payload = json.loads(bytes(reply.readAll().data()).decode("utf-8"))
            source = self._pending_source_url or "Figma link"
            document = document_from_response(payload, self._pending_node_id, source)
            self._set_document(document, source=source)
        except (ValueError, json.JSONDecodeError) as exc:
            self._clear_document_state()
            self.statusBar().showMessage(str(exc))
        finally:
            self._pending_source_url = None
            self._pending_node_id = None
            reply.deleteLater()
            self.verify_button.setEnabled(True)
            self.verify_button.setText("Verify link")

    # ------------------------------------------------------------------ generation
    def _show_message(self, title: str, message: str, kind: str = "info") -> None:
        if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
            self.statusBar().showMessage(message)
            return

        if kind == "warning":
            QMessageBox.warning(self, title, message)
        elif kind == "critical":
            QMessageBox.critical(self, title, message)
        else:
            QMessageBox.information(self, title, message)

    def _browse_output_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select output directory", str(config.default_output_dir().parent)
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _generate_project(self) -> None:
        if self.document is None:
            self._show_message(
                "No input", "Please verify a Figma file before generating.", kind="warning"
            )
            return
        if not self.selected_frames:
            self._show_message(
                "No frames selected",
                "Please select at least one frame before generating.",
                kind="warning",
            )
            return

        selected_document = dataclasses.replace(self.document, frames=list(self.selected_frames))
        try:
            result = convert_document(
                selected_document,
                project_name=self.project_name_input.text().strip() or config.DEFAULT_PROJECT_NAME,
                output_dir=self.output_dir_input.text().strip() or config.default_output_dir(),
            )
        except OSError as exc:
            logger.exception("Project generation failed")
            self._show_message("Generation failed", str(exc), kind="critical")
            return

        message = f"Project generated at {result.output_dir}"
        if result.warnings:
            message += f" ({len(result.warnings)} warning(s); first: {result.warnings[0]})"
        self.result_label.setText(message)
        self.statusBar().showMessage(message)


def main() -> None:
    """Launch the workbench maximized."""
    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise RuntimeError("A QApplication is required to launch the workbench")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    window = WorkbenchMainWindow()
    window.showMaximized()
    app.exec()


if __name__ == "__main__":
    main()
