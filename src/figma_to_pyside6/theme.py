"""Single dark neon theme shared by the workbench and the generated applications."""

from __future__ import annotations

COLORS: dict[str, str] = {
    "window": "#07070D",
    "surface": "#0E0E18",
    "raised": "#161626",
    "border": "#2A2A44",
    "text": "#E8EAF6",
    "muted": "#8A8FB0",
    "cyan": "#00F0FF",
    "magenta": "#FF2BD6",
    "accent_text": "#04040A",
}


def tokens_qss() -> str:
    """Base widget colors and typography."""
    c = COLORS
    return f"""QWidget {{
    color: {c["text"]};
    background-color: {c["window"]};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", "Ubuntu", sans-serif;
    font-size: 14px;
}}
QToolTip {{
    color: {c["cyan"]};
    background: {c["surface"]};
    border: 1px solid {c["cyan"]};
    padding: 4px 8px;
}}
"""


def main_qss() -> str:
    """Window, label, card and scrollbar styles."""
    c = COLORS
    return f"""QMainWindow, QStackedWidget {{
    background: {c["window"]};
}}
QLabel {{
    background: transparent;
}}
QLabel#appTitle, QLabel#pageTitle {{
    color: {c["cyan"]};
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#stepLabel {{
    color: {c["magenta"]};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 3px;
}}
QWidget#workflowContent, QFrame#card {{
    background: {c["surface"]};
    border: 1px solid {c["border"]};
    border-radius: 14px;
}}
QWidget#workflowContent QLabel, QFrame#card QLabel {{
    background: transparent;
}}
QStatusBar {{
    color: {c["muted"]};
    background: {c["surface"]};
    border-top: 1px solid {c["border"]};
}}
QScrollBar:vertical {{
    background: {c["window"]};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {c["border"]};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c["cyan"]};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
"""


def components_qss() -> str:
    """Inputs, lists and buttons with neon hover/focus states."""
    c = COLORS
    return f"""QLineEdit, QListWidget, QComboBox {{
    background: {c["window"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    padding: 9px 12px;
    selection-background-color: {c["cyan"]};
    selection-color: {c["accent_text"]};
}}
QLineEdit:hover, QListWidget:hover {{
    border: 1px solid {c["muted"]};
}}
QLineEdit:focus, QListWidget:focus, QComboBox:focus {{
    border: 1px solid {c["cyan"]};
}}
QListWidget::item {{
    padding: 9px 8px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background: {c["raised"]};
}}
QListWidget::item:selected {{
    background: {c["raised"]};
    color: {c["cyan"]};
    border: 1px solid {c["cyan"]};
}}
QListWidget::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c["muted"]};
    border-radius: 4px;
    background: {c["window"]};
}}
QListWidget::indicator:checked {{
    background: {c["cyan"]};
    border: 1px solid {c["cyan"]};
}}
QPushButton {{
    background: {c["raised"]};
    color: {c["cyan"]};
    border: 1px solid {c["cyan"]};
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {c["cyan"]};
    color: {c["accent_text"]};
}}
QPushButton:pressed {{
    background: {c["magenta"]};
    border-color: {c["magenta"]};
    color: {c["accent_text"]};
}}
QPushButton:disabled {{
    color: {c["muted"]};
    border-color: {c["border"]};
    background: {c["surface"]};
}}
QPushButton#generateButton {{
    background: {c["cyan"]};
    color: {c["accent_text"]};
    border: none;
    padding: 13px 18px;
    font-weight: 800;
    letter-spacing: 1px;
}}
QPushButton#generateButton:hover {{
    background: {c["magenta"]};
}}
QPushButton#generateButton:disabled {{
    background: {c["raised"]};
    color: {c["muted"]};
}}
QPushButton#navButton {{
    text-align: left;
    background: transparent;
    color: {c["muted"]};
    border: 1px solid transparent;
    padding: 11px 16px;
}}
QPushButton#navButton:hover {{
    color: {c["cyan"]};
    background: {c["raised"]};
}}
QPushButton#navButton:checked {{
    color: {c["cyan"]};
    background: {c["raised"]};
    border: 1px solid {c["cyan"]};
}}
"""


def build_stylesheet() -> str:
    """Return the full application stylesheet (QSS has no ``@import`` support)."""
    return "\n".join((tokens_qss(), main_qss(), components_qss()))
