"""Desktop workbench: verify a Figma link, pick frames, generate a project."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import signal
import threading
from collections.abc import Callable
from types import FrameType
from typing import override

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    QTimer,
    QUrl,
    QUrlQuery,
    Signal,
)
from PySide6.QtGui import QCloseEvent, QColor, QFont, QPainter
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
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
from figma_to_pyside6.adapters.figma_client import FigmaApiError, FigmaClient, UrllibFigmaClient
from figma_to_pyside6.application.conversion_service import convert_document
from figma_to_pyside6.application.figma_pipeline import (
    GenerationCancelled,
    ProgressFn,
    generate_from_figma,
)
from figma_to_pyside6.domain.models import ConversionResult, FigmaDocument, FigmaFrame
from figma_to_pyside6.resources import app_icon
from figma_to_pyside6.theme import COLORS, build_stylesheet

logger = logging.getLogger(__name__)

_NO_FILE_TEXT = "No file verified"
_LOAD_FRAMES_HINT = "Verify a Figma file to load its frames"
_FIGMA_ACCESS_ERROR = (
    "Could not access the Figma file. Check the link, token, and file permissions."
)
_FIGMA_TIMEOUT_ERROR = "Figma did not respond in time. Check your connection and try again."
_PAGE_MARGINS = (40, 28, 40, 24)
_CARD_MARGINS = (28, 24, 28, 24)
_CARD_SPACING = 14
_COLUMN_SPACING = 24


def _glow(widget: QWidget, color: str, blur: int) -> QGraphicsDropShadowEffect:
    """Give ``widget`` a neon glow; QSS has no box-shadow so use a graphics effect."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setColor(QColor(color))
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)
    return effect


def frame_item_text(frame: FigmaFrame, ordinal: str = "") -> tuple[str, str]:
    """Return the headline (frame name) and detail line shown for a frame in the list.

    ``ordinal`` (e.g. ``"2 of 8"``) is appended to the headline when several frames share a
    name; the detail line always ends with the Figma node id (the ``node-id`` in Figma URLs).
    """
    layers = len(frame.children)
    details = [f"{frame.width} × {frame.height}"]
    if frame.container_name:
        details.insert(0, frame.container_name)
    details += [f"{layers} layer{'s' if layers != 1 else ''}", f"ID {frame.node_id}"]
    headline = f"{frame.name}  ({ordinal})" if ordinal else frame.name
    return headline, "  ·  ".join(details)


def _ordinals(frames: list[FigmaFrame]) -> list[str]:
    """``"k of n"`` for frames whose name occurs more than once, otherwise an empty string."""
    totals: dict[str, int] = {}
    for frame in frames:
        totals[frame.name] = totals.get(frame.name, 0) + 1
    seen: dict[str, int] = {}
    ordinals = []
    for frame in frames:
        seen[frame.name] = seen.get(frame.name, 0) + 1
        total = totals[frame.name]
        ordinals.append(f"{seen[frame.name]} of {total}" if total > 1 else "")
    return ordinals


def _resized(font: QFont, delta: int) -> QFont:
    """A copy of ``font`` made ``delta`` px/pt larger, whichever unit the font is sized in.

    Fonts set through a style sheet (``font-size: 14px``) have a pixel size and a point size
    of -1, so deriving the new size from ``pointSizeF()`` would ask Qt for a size of 0.
    """
    result = QFont(font)
    if font.pixelSize() > 0:
        result.setPixelSize(max(font.pixelSize() + delta, 7))
    else:
        result.setPointSizeF(max(font.pointSizeF() + delta, 7.0))
    return result


class _FrameRowDelegate(QStyledItemDelegate):
    """Two-line row: frame name in bold, detail line (page, size, layers) muted and smaller."""

    ROW_HEIGHT = 58

    @override
    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        """Fixed row height, without measuring the text (cheap even for long lists)."""
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        item_option = QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)
        name, _, details = str(index.data(Qt.ItemDataRole.DisplayRole)).partition("\n")
        item_option.text = ""  # let the style draw background, hover and check box only
        widget = option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item_option, painter, widget)

        check_rect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemCheckIndicator, item_option, widget
        )
        left = check_rect.right() + 14
        text_rect = QRect(
            left, option.rect.top() + 9, option.rect.right() - left - 8, option.rect.height() - 18
        )
        painter.save()
        name_font = _resized(option.font, 1)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(
            text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), name
        )
        detail_font = _resized(option.font, -1)
        painter.setFont(detail_font)
        painter.setPen(QColor(COLORS["muted"]))
        painter.drawText(
            text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom), details
        )
        painter.restore()


def _card(number: str, title: str) -> tuple[QFrame, QVBoxLayout]:
    """A padded card with a numbered step header; returns the card and its body layout."""
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(*_CARD_MARGINS)
    layout.setSpacing(_CARD_SPACING)
    header = QHBoxLayout()
    header.setSpacing(12)
    number_label = QLabel(number)
    number_label.setObjectName("stepNumber")
    title_label = QLabel(title)
    title_label.setObjectName("stepLabel")
    header.addWidget(number_label)
    header.addWidget(title_label)
    header.addStretch(1)
    layout.addLayout(header)
    return card, layout


class _GenerateWorker(QObject):
    """Runs a generation job on a daemon thread and reports back through queued signals.

    The job can be cancelled: the next progress report raises :class:`GenerationCancelled`,
    so the job stops at a step boundary and nothing half-written is left behind.
    """

    progress = Signal(str, int)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, job: Callable[[ProgressFn], ConversionResult]) -> None:
        super().__init__()
        self._job = job
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Ask the job to stop at its next progress report."""
        self._cancel.set()

    def _report(self, message: str, percent: int) -> None:
        if self._cancel.is_set():
            raise GenerationCancelled
        self.progress.emit(message, percent)

    def run(self) -> None:
        """Execute the job; always ends by emitting ``finished``."""
        try:
            result = self._job(self._report)
        except GenerationCancelled:
            logger.info("Project generation cancelled")
        except (FigmaApiError, ValueError, OSError) as exc:
            logger.exception("Project generation failed")
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class WorkbenchMainWindow(QMainWindow):
    """Three-step workbench: verify link, select frames, generate."""

    def __init__(self) -> None:
        """Build the window; it opens maximized."""
        super().__init__()
        self.document: FigmaDocument | None = None
        self.selected_frames: list[FigmaFrame] = []
        self._pending_source_url: str | None = None
        self._pending_file_key: str | None = None
        self._pending_token: str | None = None
        self._pending_node_id: str | None = None
        self._session_token: str | None = None  # memory only; never written anywhere
        self._file_key: str | None = None
        self._client_factory: Callable[[str], FigmaClient] = UrllibFigmaClient
        self._thread: threading.Thread | None = None
        self._worker: _GenerateWorker | None = None
        self.busy = False
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
        _glow(self.verify_button, COLORS["cyan"], 18)
        self._generate_glow = _glow(self.generate_button, COLORS["cyan"], 30)
        self._generate_glow.setEnabled(False)

    # ------------------------------------------------------------------ construction
    def _create_widgets(self) -> None:
        self.title_label = QLabel("FIGMA  →  PYSIDE6")
        self.title_label.setObjectName("appTitle")
        self.figma_link_input = QLineEdit()
        self.figma_link_input.setObjectName("figmaLinkInput")
        self.figma_link_input.setPlaceholderText("https://www.figma.com/design/...")
        self.figma_token_input = QLineEdit()
        self.figma_token_input.setObjectName("figmaTokenInput")
        self.figma_token_input.setPlaceholderText("Personal access token")
        self.figma_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.verify_button = QPushButton("Verify link")
        self.verify_button.clicked.connect(self._verify_figma_link)
        self.subtitle_label = QLabel("Turn Figma frames into a PySide6 app, one page per frame")
        self.subtitle_label.setObjectName("subtitle")
        self.document_label = QLabel(_NO_FILE_TEXT)
        self.document_label.setObjectName("hint")
        self.frame_list = QListWidget()
        self.frame_list.setObjectName("frameList")
        self.frame_list.setItemDelegate(_FrameRowDelegate(self.frame_list))
        self.frame_list.setEnabled(False)
        self.frame_list.itemChanged.connect(self._update_selected_frames)
        self.select_all_button = QPushButton("Select all")
        self.select_all_button.setObjectName("smallButton")
        self.select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("smallButton")
        self.clear_button.clicked.connect(lambda: self._set_all_checked(False))
        self.select_all_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.frame_summary = QLabel(_LOAD_FRAMES_HINT)
        self.frame_summary.setObjectName("hint")
        self.frame_summary.setWordWrap(True)
        self.project_name_input = QLineEdit(config.DEFAULT_PROJECT_NAME)
        self.project_name_input.setObjectName("projectNameInput")
        self.project_name_input.setPlaceholderText("Project name")
        self.output_dir_input = QLineEdit(str(config.default_output_dir()))
        self.output_dir_input.setObjectName("outputDirectoryInput")
        self.output_dir_input.setCursorPosition(0)
        self.generate_button = QPushButton("Generate project")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate_project)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self._browse_output_directory)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("generateProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMinimumWidth(config.PROGRESS_BAR_MIN_WIDTH)
        self.progress_bar.hide()
        self.result_label = QLabel("")
        self.result_label.setObjectName("result")
        self.result_label.setWordWrap(True)

    def _build_ui(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(*_PAGE_MARGINS)
        outer.setSpacing(20)
        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(self.title_label)
        header.addWidget(self.subtitle_label)
        outer.addLayout(header)

        columns = QHBoxLayout()
        columns.setSpacing(_COLUMN_SPACING)
        left = QWidget()
        left.setFixedWidth(config.LEFT_COLUMN_WIDTH)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(_COLUMN_SPACING)
        left_layout.addWidget(self._verify_card())
        left_layout.addWidget(self._generate_card())
        left_layout.addStretch(1)
        columns.addWidget(left)
        columns.addWidget(self._frames_card(), 1)
        outer.addLayout(columns, 1)

        self.setCentralWidget(central)
        self.statusBar().addPermanentWidget(self.progress_bar, 1)
        self.statusBar().showMessage("Ready")

    def _verify_card(self) -> QFrame:
        card, layout = _card("01", "VERIFY FIGMA FILE")
        layout.addWidget(self.figma_link_input)
        credentials = QHBoxLayout()
        credentials.setSpacing(12)
        credentials.addWidget(self.figma_token_input, 1)
        credentials.addWidget(self.verify_button)
        layout.addLayout(credentials)
        layout.addWidget(self.document_label)
        return card

    def _frames_card(self) -> QFrame:
        card, layout = _card("02", "SELECT FRAMES")
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.frame_summary, 1)
        actions.addWidget(self.select_all_button)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)
        layout.addWidget(self.frame_list, 1)
        return card

    def _generate_card(self) -> QFrame:
        card, layout = _card("03", "GENERATE PROJECT")
        layout.addWidget(self.project_name_input)
        output_row = QHBoxLayout()
        output_row.setSpacing(12)
        output_row.addWidget(self.output_dir_input, 1)
        output_row.addWidget(self.browse_button)
        layout.addLayout(output_row)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.result_label)
        return card

    def _set_generate_enabled(self, enabled: bool) -> None:
        """Enable the Generate button; it only glows while it can be pressed."""
        self.generate_button.setEnabled(enabled)
        self._generate_glow.setEnabled(enabled)

    def _set_bulk_buttons_enabled(self, enabled: bool) -> None:
        self.select_all_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self.frame_list.count()):
            self.frame_list.item(index).setCheckState(state)

    # ------------------------------------------------------------------ document state
    def _set_document(self, document: FigmaDocument, *, source: str) -> None:
        self.document = document
        self.selected_frames = []
        self.result_label.clear()
        self.document_label.setText(f"Verified: {document.name}")
        self.frame_list.clear()
        self.frame_list.setEnabled(True)
        self._set_bulk_buttons_enabled(True)
        for frame, ordinal in zip(document.frames, _ordinals(document.frames), strict=True):
            name, details = frame_item_text(frame, ordinal)
            item = QListWidgetItem(f"{name}\n{details}")
            item.setToolTip(f"{name}\n{details}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.frame_list.addItem(item)
        self._update_selected_frames()
        self.statusBar().showMessage(f"{len(document.frames)} frames loaded from {source}")

    def _clear_document_state(self) -> None:
        self._session_token = None
        self._file_key = None
        self.document = None
        self.selected_frames = []
        self.frame_list.clear()
        self.frame_list.setEnabled(False)
        self._set_bulk_buttons_enabled(False)
        self.document_label.setText(_NO_FILE_TEXT)
        self.frame_summary.setText(_LOAD_FRAMES_HINT)
        self._set_generate_enabled(False)
        self.result_label.clear()

    def _update_selected_frames(self) -> None:
        if self.document is None:
            self.selected_frames = []
            self.frame_summary.setText("No document loaded")
            self._set_generate_enabled(False)
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
        self._set_generate_enabled(bool(self.selected_frames))

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
        self._pending_file_key = file_key
        self._pending_token = token
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
            self._session_token = self._pending_token
            self._file_key = self._pending_file_key
        except (ValueError, json.JSONDecodeError) as exc:
            self._clear_document_state()
            self.statusBar().showMessage(str(exc))
        finally:
            self._pending_source_url = None
            self._pending_node_id = None
            self._pending_file_key = None
            self._pending_token = None
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
        project_name = self.project_name_input.text().strip() or config.DEFAULT_PROJECT_NAME
        output_dir = self.output_dir_input.text().strip() or str(config.default_output_dir())

        token, file_key = self._session_token, self._file_key
        if token and file_key:
            client = self._client_factory(token)

            def job(progress: ProgressFn) -> ConversionResult:
                return generate_from_figma(
                    client, file_key, selected_document, project_name, output_dir, progress
                )

            self._start_generation(job)
            return
        try:
            result = convert_document(selected_document, project_name, output_dir)
        except OSError as exc:
            logger.exception("Project generation failed")
            self._show_message("Generation failed", str(exc), kind="critical")
            return
        self._show_result(result)

    def _start_generation(self, job: Callable[[ProgressFn], ConversionResult]) -> None:
        """Run ``job`` in a worker thread, keeping the window responsive."""
        self._set_busy(True)
        worker = _GenerateWorker(job)
        worker.progress.connect(self._on_generation_progress)
        worker.succeeded.connect(self._on_generation_succeeded)
        worker.failed.connect(self._on_generation_failed)
        worker.finished.connect(self._on_generation_finished)
        # A daemon thread: Qt does not own it, so quitting can never trip over a running
        # QThread, and a request stuck on the network cannot keep the process alive.
        thread = threading.Thread(target=worker.run, name="figma-generate", daemon=True)
        self._thread, self._worker = thread, worker
        thread.start()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.verify_button.setEnabled(not busy)
        self.generate_button.setText("Generating…" if busy else "Generate project")
        if busy:
            self._set_generate_enabled(False)
            self.statusBar().clearMessage()
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Starting…  %p%")
            self.progress_bar.show()
        else:
            self.progress_bar.hide()
            self._update_selected_frames()

    def _on_generation_progress(self, message: str, percent: int) -> None:
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{message}  —  %p%")

    def _on_generation_succeeded(self, result: ConversionResult) -> None:
        self._show_result(result)

    def _on_generation_failed(self, message: str) -> None:
        self.result_label.setText(f"Generation failed: {message}")
        self._show_message("Generation failed", message, kind="critical")

    def _on_generation_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = self._worker = None
        self._set_busy(False)

    def _show_result(self, result: ConversionResult) -> None:
        message = f"Project generated at {result.output_dir}"
        if result.warnings:
            message += f" ({len(result.warnings)} warning(s); first: {result.warnings[0]})"
        self.result_label.setText(message)
        self.statusBar().showMessage(message)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        """Forget the token and stop a running generation before closing."""
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Drop the token and cancel a running job, waiting briefly for it to stop."""
        self._session_token = None
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.join(timeout=config.SHUTDOWN_JOIN_SECONDS)


def install_interrupt_handler(app: QApplication) -> QTimer:
    """Make Ctrl+C in the terminal close the app cleanly instead of raising inside Qt code.

    Python only runs signal handlers while it executes Python code, so a no-op timer wakes
    the interpreter regularly while Qt's event loop is idle. The returned timer must be kept.
    """

    def handler(_signum: int, _frame: FrameType | None) -> None:
        app.closeAllWindows()  # runs each window's closeEvent, which cancels running work
        app.quit()

    signal.signal(signal.SIGINT, handler)
    timer = QTimer(app)
    timer.timeout.connect(lambda: None)
    timer.start(config.INTERRUPT_POLL_MS)
    return timer


def main() -> None:
    """Launch the workbench maximized."""
    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise RuntimeError("A QApplication is required to launch the workbench")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    window = WorkbenchMainWindow()
    app.aboutToQuit.connect(window.shutdown)
    interrupt_timer = install_interrupt_handler(app)
    window.showMaximized()
    app.exec()
    interrupt_timer.stop()


if __name__ == "__main__":
    main()
