from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QUrlQuery
from PySide6.QtGui import QColor, QPalette
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
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

from figma_to_pyside6.adapters.figma_api import extract_figma_file_key, extract_figma_node_id
from figma_to_pyside6.adapters.figma_json import load_figma_document, parse_figma_document
from figma_to_pyside6.application.conversion_service import convert_document
from figma_to_pyside6.domain.models import FigmaDocument, FigmaFrame


class WorkbenchMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.document: FigmaDocument | None = None
        self.selected_frames: list[FigmaFrame] = []
        self._pending_source_url: str | None = None
        self._pending_node_id: str | None = None
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._finish_figma_verification)
        self.figma_link_input: QLineEdit | None = None
        self.figma_token_input: QLineEdit | None = None
        self.verify_button: QPushButton | None = None
        self.document_label: QLabel | None = None
        self.frame_summary: QLabel | None = None
        self.frame_list: QListWidget | None = None
        self.project_name_input: QLineEdit | None = None
        self.output_dir_input: QLineEdit | None = None
        self.generate_button: QPushButton | None = None
        self.result_label: QLabel | None = None
        self.theme_selector: QComboBox | None = None
        self.style_selector: QComboBox | None = None
        self.setWindowTitle("Figma to PySide6 Workbench")
        self.resize(900, 760)
        self.setMinimumSize(640, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(32, 24, 32, 24)
        header = QHBoxLayout()
        title = QLabel("Figma to PySide6")
        title.setObjectName("appTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.theme_selector = QComboBox()
        self.theme_selector.setObjectName("themeSelector")
        self.theme_selector.addItems(["Dark", "Light"])
        self.theme_selector.setToolTip("Choose dark or light colors")
        self.style_selector = QComboBox()
        self.style_selector.setObjectName("styleSelector")
        self.style_selector.addItems(["Modern", "Standard"])
        self.style_selector.setToolTip("Choose modern or standard Qt styling")
        self.theme_selector.currentTextChanged.connect(self._apply_appearance)
        self.style_selector.currentTextChanged.connect(self._apply_appearance)
        header.addWidget(self.theme_selector)
        header.addWidget(self.style_selector)
        outer_layout.addLayout(header)

        content = QWidget()
        content.setObjectName("workflowContent")
        content.setMaximumWidth(1040)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 28, 0, 12)
        layout.setSpacing(16)

        verify_step = QLabel("01  VERIFY FIGMA FILE")
        verify_step.setObjectName("stepLabel")
        layout.addWidget(verify_step)
        self.figma_link_input = QLineEdit()
        self.figma_link_input.setObjectName("figmaLinkInput")
        self.figma_link_input.setPlaceholderText("https://www.figma.com/design/...")
        layout.addWidget(self.figma_link_input)

        credentials = QHBoxLayout()
        self.figma_token_input = QLineEdit()
        self.figma_token_input.setObjectName("figmaTokenInput")
        self.figma_token_input.setPlaceholderText("Figma personal access token")
        self.figma_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        credentials.addWidget(self.figma_token_input, 1)
        self.verify_button = QPushButton("Verify link")
        self.verify_button.clicked.connect(self._verify_figma_link)
        credentials.addWidget(self.verify_button)
        layout.addLayout(credentials)

        self.document_label = QLabel("No file verified")
        layout.addWidget(self.document_label)

        select_step = QLabel("02  SELECT FRAMES")
        select_step.setObjectName("stepLabel")
        layout.addWidget(select_step)
        self.frame_list = QListWidget()
        self.frame_list.setObjectName("frameList")
        self.frame_list.setEnabled(False)
        self.frame_list.itemChanged.connect(self._update_selected_frames)
        layout.addWidget(self.frame_list, 1)

        self.frame_summary = QLabel("Verify a Figma file to load its frames")
        layout.addWidget(self.frame_summary)

        generate_step = QLabel("03  GENERATE PROJECT")
        generate_step.setObjectName("stepLabel")
        layout.addWidget(generate_step)
        self.project_name_input = QLineEdit("GeneratedApp")
        self.project_name_input.setObjectName("projectNameInput")
        self.project_name_input.setPlaceholderText("Project name")
        layout.addWidget(self.project_name_input)

        output_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(str(Path.cwd() / "generated_project"))
        self.output_dir_input.setObjectName("outputDirectoryInput")
        output_row.addWidget(self.output_dir_input, 1)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_output_directory)
        output_row.addWidget(browse_button)
        layout.addLayout(output_row)

        self.generate_button = QPushButton("Generate project")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate_project)
        layout.addWidget(self.generate_button)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        outer_layout.addWidget(content, 1, Qt.AlignmentFlag.AlignHCenter)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")
        self._apply_appearance()

    def _apply_appearance(self, *_args) -> None:
        theme = self.theme_selector.currentText() if self.theme_selector is not None else "Dark"
        modern = self.style_selector is None or self.style_selector.currentText() == "Modern"
        dark = theme == "Dark"
        colors = (
            {
                "window": "#11151B",
                "surface": "#181F28",
                "raised": "#202A36",
                "border": "#384556",
                "text": "#F1F5F9",
                "muted": "#AAB6C4",
                "accent": "#67E8F9",
                "accent_text": "#0B1720",
            }
            if dark
            else {
                "window": "#F4F7FA",
                "surface": "#FFFFFF",
                "raised": "#EDF2F7",
                "border": "#CBD5E1",
                "text": "#15202B",
                "muted": "#526273",
                "accent": "#087E8B",
                "accent_text": "#FFFFFF",
            }
        )
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["raised"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(colors["raised"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["accent_text"]))
        app = QApplication.instance()
        if app is not None:
            app.setPalette(palette)

        if not modern:
            self.setStyleSheet("")
            return

        self.setStyleSheet(
            f"""
            QWidget#workflowContent {{ background: {colors['surface']}; border: 1px solid {colors['border']}; border-radius: 12px; }}
            QLabel#appTitle {{ font-size: 22px; font-weight: 700; }}
            QLabel#stepLabel {{ color: {colors['accent']}; font-size: 11px; font-weight: 700; }}
            QLineEdit, QListWidget, QComboBox {{ background: {colors['window']}; border: 1px solid {colors['border']}; border-radius: 7px; padding: 9px 11px; }}
            QLineEdit:focus, QListWidget:focus, QComboBox:focus {{ border: 1px solid {colors['accent']}; }}
            QListWidget::item {{ padding: 8px; border-radius: 5px; }}
            QPushButton {{ background: {colors['raised']}; border: 1px solid {colors['border']}; border-radius: 7px; padding: 9px 14px; }}
            QPushButton:hover {{ border-color: {colors['accent']}; }}
            QPushButton:disabled {{ color: {colors['muted']}; }}
            QPushButton#generateButton {{ background: {colors['accent']}; color: {colors['accent_text']}; font-weight: 700; border: none; padding: 12px 16px; }}
            QStatusBar {{ color: {colors['muted']}; }}
            """
        )

    def _load_document(self, path: str | Path) -> None:
        document = load_figma_document(path)
        self._set_document(document, source=str(path), select_all=True)

    def _set_document(
        self, document: FigmaDocument, *, source: str, select_all: bool = False
    ) -> None:
        self.document = document
        self.selected_frames = []
        if self.result_label is not None:
            self.result_label.clear()
        if self.document_label is not None:
            self.document_label.setText(f"Verified: {document.name}")
        if self.frame_list is not None:
            self.frame_list.clear()
            self.frame_list.setEnabled(True)
            for frame in document.frames:
                item = QListWidgetItem(f"{frame.name}  |  {frame.width} x {frame.height}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if select_all else Qt.CheckState.Unchecked)
                self.frame_list.addItem(item)
        if select_all:
            self.selected_frames = list(document.frames)
        self._update_selected_frames()
        self.statusBar().showMessage(f"{len(document.frames)} frames loaded from {source}")

    def _verify_figma_link(self) -> None:
        if (
            self.figma_link_input is None
            or self.figma_token_input is None
            or self.verify_button is None
        ):
            return
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
        if node_id is not None:
            request_url = QUrl(f"https://api.figma.com/v1/files/{file_key}/nodes")
            query = QUrlQuery()
            query.addQueryItem("ids", node_id)
        else:
            request_url = QUrl(f"https://api.figma.com/v1/files/{file_key}")
            query = QUrlQuery()
        query.addQueryItem("depth", "2")
        request_url.setQuery(query)
        request = QNetworkRequest(request_url)
        request.setRawHeader(b"X-Figma-Token", token.encode("utf-8"))
        self._network_manager.get(request)
        self.figma_token_input.clear()
        self.statusBar().showMessage("Verifying Figma file and loading frames…")

    def _clear_document_state(self) -> None:
        self.document = None
        self.selected_frames = []
        if self.frame_list is not None:
            self.frame_list.clear()
            self.frame_list.setEnabled(False)
        if self.document_label is not None:
            self.document_label.setText("No file verified")
        if self.frame_summary is not None:
            self.frame_summary.setText("Verify a Figma file to load its frames")
        if self.generate_button is not None:
            self.generate_button.setEnabled(False)
        if self.result_label is not None:
            self.result_label.clear()

    def _finish_figma_verification(self, reply: QNetworkReply) -> None:
        try:
            status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if (
                reply.error() != QNetworkReply.NetworkError.NoError
                or not status_code
                or not 200 <= status_code < 300
            ):
                raise ValueError(
                    "Could not access the Figma file. Check the link, token, and file permissions."
                )
            payload = json.loads(bytes(reply.readAll().data()).decode("utf-8"))
            source = self._pending_source_url or "Figma link"
            if self._pending_node_id is not None:
                node_entry = payload.get("nodes", {}).get(self._pending_node_id)
                node = node_entry.get("document") if node_entry else None
                if not node:
                    raise ValueError("The linked Figma section could not be found.")
                payload = {"name": node.get("name"), "document": node}
                document = parse_figma_document(payload, source=source, recurse_frames=False)
            else:
                document = parse_figma_document(payload, source=source)
            self._set_document(document, source=source)
        except (ValueError, json.JSONDecodeError) as exc:
            self._clear_document_state()
            self.statusBar().showMessage(str(exc))
        finally:
            self._pending_source_url = None
            self._pending_node_id = None
            reply.deleteLater()
            if self.verify_button is not None:
                self.verify_button.setEnabled(True)
                self.verify_button.setText("Verify link")

    def _update_selected_frames(self) -> None:
        if self.document is None or self.frame_list is None:
            self.selected_frames = []
            if self.frame_summary is not None:
                self.frame_summary.setText("No document loaded")
            if self.generate_button is not None:
                self.generate_button.setEnabled(False)
            return

        selected = []
        for index in range(self.frame_list.count()):
            item = self.frame_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(self.document.frames[index])
        self.selected_frames = selected

        if self.frame_summary is not None:
            if not selected:
                self.frame_summary.setText("No frames selected")
            else:
                names = ", ".join(frame.name for frame in selected)
                self.frame_summary.setText(
                    f"{len(selected)}/{len(self.document.frames)} selected: {names}"
                )
        if self.generate_button is not None:
            self.generate_button.setEnabled(bool(selected))

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
        if self.output_dir_input is None:
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Select output directory", str(Path.cwd())
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _generate_project(self) -> None:
        if self.document is None:
            self._show_message(
                "No input", "Please import a Figma JSON file before converting.", kind="warning"
            )
            return

        if not self.selected_frames:
            self._show_message(
                "No frames selected",
                "Please select at least one frame before generating.",
                kind="warning",
            )
            return

        project_name = (
            self.project_name_input.text().strip()
            if self.project_name_input is not None
            else "GeneratedApp"
        )
        output_dir = (
            self.output_dir_input.text().strip()
            if self.output_dir_input is not None
            else str(Path.cwd() / "generated_project")
        )

        try:
            selected_document = type(self.document)(
                name=self.document.name,
                node_id=self.document.node_id,
                frames=list(self.selected_frames),
                source=self.document.source,
            )
            result = convert_document(
                selected_document, project_name=project_name, output_dir=output_dir
            )
            message = f"Project generated at {result.output_dir}"
            if self.result_label is not None:
                self.result_label.setText(message)
            self.statusBar().showMessage(message)
        except Exception as exc:  # pragma: no cover - GUI error reporting path
            self._show_message("Generation failed", str(exc), kind="critical")


def main() -> None:
    app = QApplication([])
    window = WorkbenchMainWindow()
    window.showMaximized()
    app.exec()


if __name__ == "__main__":
    main()
