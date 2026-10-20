"""Light and dark themes (plain, Windows-style)."""
from PySide6.QtGui import QColor, QPalette

LIGHT = dict(bg="#F3F3F3", panel="#FFFFFF", text="#1B1B1B", muted="#5C5C5C", border="#D1D1D1",
             line="#E5E5E5", cb="#8A8A8A", sunken="#FAFAFA", accent="#0067C0",
             accent_hover="#005BAA", on_accent="#FFFFFF", ok="#0F7B0F", on_ok="#FFFFFF",
             warn="#7A4A00", warn_bg="#FFF8E6", selected="#EAF2FB", field="#FFFFFF")
DARK = dict(bg="#1F1F1F", panel="#2B2B2B", text="#F3F3F3", muted="#ADADAD", border="#3D3D3D",
            line="#383838", cb="#6E6E6E", sunken="#252525", accent="#4CC2FF",
            accent_hover="#7DD3FF", on_accent="#0B1A24", ok="#6CCB5F", on_ok="#0B1A24",
            warn="#F5C463", warn_bg="#3A3020", selected="#1F3A52", field="#1F1F1F")

# waveforms look the same in both themes (dark sampler style)
WAVE = dict(bg="#1C2126", grid="#2A3138", center="#46525C", fill="#86D9A0", edge="#C4F2D1",
            handle="#4CC2FF", shade="#0A0C0E", region="#4CC2FF", ai="#C8CDD2",
            groove=["#4C8DFF", "#6CCB5F", "#C88DFF", "#FFB347"], roll="#F5C463")


def palette(t: dict) -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(t["bg"]))
    p.setColor(QPalette.WindowText, QColor(t["text"]))
    p.setColor(QPalette.Base, QColor(t["field"]))
    p.setColor(QPalette.AlternateBase, QColor(t["sunken"]))
    p.setColor(QPalette.Text, QColor(t["text"]))
    p.setColor(QPalette.Button, QColor(t["panel"]))
    p.setColor(QPalette.ButtonText, QColor(t["text"]))
    p.setColor(QPalette.Highlight, QColor(t["accent"]))
    p.setColor(QPalette.HighlightedText, QColor(t["on_accent"]))
    p.setColor(QPalette.ToolTipBase, QColor(t["panel"]))
    p.setColor(QPalette.ToolTipText, QColor(t["text"]))
    p.setColor(QPalette.PlaceholderText, QColor(t["muted"]))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(t["muted"]))
    return p


def stylesheet(t: dict) -> str:
    return f"""
QWidget {{ font-family: "Segoe UI", "Segoe UI Variable", Arial, sans-serif; font-size: 10pt;
          color: {t['text']}; }}
QMainWindow, QDialog, QWidget#page {{ background: {t['bg']}; }}
QFrame#panel {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 4px; }}
QFrame#topbar {{ background: {t['panel']}; border: none; border-bottom: 1px solid {t['border']}; }}
QFrame#row {{ background: {t['panel']}; border: none; border-bottom: 1px solid {t['line']}; }}
QFrame#row[selected="true"] {{ background: {t['selected']}; }}
QFrame#groupHeader {{ background: {t['sunken']}; border: none; border-bottom: 1px solid {t['line']}; }}
QFrame#drop {{ background: {t['sunken']}; border: 2px dashed {t['cb']}; border-radius: 4px; }}
QFrame#drop[hover="true"] {{ border-color: {t['accent']}; background: {t['selected']}; }}
QFrame#warnbox {{ background: {t['warn_bg']}; border: none; border-radius: 3px; }}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {t['muted']}; }}
QLabel#warn {{ color: {t['warn']}; }}
QLabel#h1 {{ font-size: 15pt; font-weight: 600; }}
QLabel#h2 {{ font-size: 11pt; font-weight: 600; }}
QLabel#mono {{ font-family: Consolas, "Cascadia Mono", monospace; }}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background: {t['field']}; border: 1px solid {t['cb']}; border-radius: 3px;
    padding: 4px 6px; min-height: 22px; selection-background-color: {t['accent']};
    selection-color: {t['on_accent']}; }}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['panel']}; border: 1px solid {t['border']};
    selection-background-color: {t['accent']}; selection-color: {t['on_accent']}; }}
QPushButton {{ background: {t['panel']}; border: 1px solid {t['cb']}; border-radius: 3px;
    padding: 6px 14px; min-height: 22px; }}
QPushButton:hover {{ border-color: {t['accent']}; }}
QPushButton:disabled {{ color: {t['muted']}; border-color: {t['line']}; }}
QPushButton#primary {{ background: {t['accent']}; color: {t['on_accent']}; border: none;
    font-weight: 600; padding: 7px 20px; }}
QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
QPushButton#primary:disabled {{ background: {t['line']}; color: {t['muted']}; }}
QPushButton#step {{ background: transparent; border: none; border-bottom: 3px solid transparent;
    border-radius: 0; padding: 10px 16px; color: {t['muted']}; }}
QPushButton#step:checked {{ color: {t['accent']}; border-bottom: 3px solid {t['accent']};
    font-weight: 600; }}
QPushButton#link {{ background: transparent; border: none; color: {t['accent']}; padding: 4px 6px; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QToolButton {{ background: {t['panel']}; border: 1px solid {t['cb']}; border-radius: 3px; }}
QToolButton:hover {{ border-color: {t['accent']}; }}
QToolButton#thumb:checked {{ background: {t['ok']}; border-color: {t['ok']}; }}
QToolButton#seg {{ border-radius: 0; padding: 5px 12px; }}
QToolButton#seg:checked {{ background: {t['accent']}; color: {t['on_accent']}; border-color: {t['accent']}; }}
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {t['cb']}; border-radius: 3px;
    background: {t['field']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}
QCheckBox::indicator:hover {{ border-color: {t['accent']}; }}
QProgressBar {{ background: {t['line']}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {t['ok']}; border-radius: 3px; }}
QProgressBar#busy::chunk {{ background: {t['accent']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QTableWidget {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 4px;
    gridline-color: {t['line']}; alternate-background-color: {t['panel']}; }}
QTableWidget::item {{ padding: 4px; border-bottom: 1px solid {t['line']}; }}
QTableWidget::item:selected {{ background: {t['selected']}; color: {t['text']}; }}
QHeaderView::section {{ background: {t['panel']}; color: {t['muted']}; border: none;
    border-bottom: 1px solid {t['border']}; padding: 6px; font-weight: 600; font-size: 9pt; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['cb']}; border-radius: 4px; min-height: 30px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t['cb']}; border-radius: 4px; min-width: 30px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QToolTip {{ background: {t['panel']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QMenu {{ background: {t['panel']}; border: 1px solid {t['border']}; }}
QMenu::item:selected {{ background: {t['accent']}; color: {t['on_accent']}; }}
"""
