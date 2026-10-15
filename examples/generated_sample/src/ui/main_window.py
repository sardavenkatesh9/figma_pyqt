from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DemoFlow")
        self.resize(1000, 700)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        label = QLabel("Sample Screen")
        label.setObjectName("screenTitle")
        layout.addWidget(label)
        for screen_name in [frame.name for frame in document.frames]:
            layout.addWidget(QLabel(screen_name))
        self.setCentralWidget(central)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
