STYLESHEET = """
QGroupBox { font-weight: 600; border: 1px solid palette(mid); border-radius: 8px;
            margin-top: 12px; padding: 12px 10px 8px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLabel#caption { font-weight: 600; }
QLineEdit, QComboBox, QPlainTextEdit { border: 1px solid palette(mid); border-radius: 6px; padding: 5px 8px; }
QComboBox { combobox-popup: 0; }
QPushButton { border: 1px solid palette(mid); border-radius: 6px; padding: 6px 14px; }
QPushButton#primary { background: #1a73e8; color: white; border: none; font-weight: 600; padding: 8px 18px; }
QPushButton#primary:disabled { background: #8ab4f8; color: white; }
QProgressBar { border: none; background: palette(midlight); border-radius: 4px; max-height: 8px; }
QProgressBar::chunk { background: #1a73e8; border-radius: 4px; }
QLabel#status[error="true"] { color: #d93025; }
QLabel#version { color: palette(mid); font-size: 11px; }
"""
