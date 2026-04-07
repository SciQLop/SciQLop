from PySide6.QtCore import Signal, Qt, QModelIndex, QStringListModel, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListView, QLabel,
    QSpacerItem, QSizePolicy, QFrame,
)
from SciQLopPlots import ProductsFlatFilterModel, ProductsModel, QueryParser, ProductsModelNodeType

from SciQLop.core.mime import decode_mime
from SciQLop.core.ui import Metrics
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_MAX_RESULTS = 50
_MIN_QUERY_LENGTH = 2
_DEBOUNCE_MS = 150

_MUTED = "color: palette(placeholder-text); background: transparent; border: none;"
_DROP_ZONE_STYLE = (
    "border: 3ex dashed palette(mid);"
    "border-radius: 3ex;"
    "background: transparent;"
    "padding: 6ex;"
    "font-size: 14ex;"
)


def _display_path(path_parts: list[str]) -> str:
    """Strip internal tree prefixes (root, speasy) for human-readable display."""
    if len(path_parts) >= 3 and path_parts[0] == "root":
        path_parts = path_parts[2:]
    return "/".join(path_parts)


class ProductSearchOverlay(QWidget):
    """Overlay shown on empty plot panels with a product search box."""

    product_selected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._filter_model = ProductsFlatFilterModel(ProductsModel.instance())
        self._list_model = QStringListModel()
        self._result_paths: list[list[str]] = []

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_query)

        content_width = Metrics.em(60)
        separator_width = Metrics.em(20)
        result_height = Metrics.ex(20)
        drop_height = Metrics.ex(8)

        layout = QVBoxLayout(self)
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self._label = QLabel("Add a product to this panel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(_MUTED + "font-size: 16ex;")
        layout.addWidget(self._label, 0, Qt.AlignmentFlag.AlignCenter)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search products (e.g. MMS FGM, ACE MAG B_gsm)\u2026")
        self._search_box.setFixedWidth(content_width)
        self._search_box.setStyleSheet("font-size: 14ex; padding: 1ex;")
        self._search_box.setClearButtonEnabled(True)
        layout.addWidget(self._search_box, 0, Qt.AlignmentFlag.AlignCenter)

        self._result_list = QListView()
        self._result_list.setModel(self._list_model)
        self._result_list.setFixedWidth(content_width)
        self._result_list.setMaximumHeight(result_height)
        self._result_list.setVisible(False)
        layout.addWidget(self._result_list, 0, Qt.AlignmentFlag.AlignCenter)

        # --- "or" separator + drop zone (hidden when results are shown) ---
        self._drop_section = QWidget()
        drop_layout = QVBoxLayout(self._drop_section)
        drop_layout.setContentsMargins(0, 0, 0, 0)

        separator_layout = QHBoxLayout()
        separator_layout.setContentsMargins(0, 0, 0, 0)
        line_left = QFrame()
        line_left.setFrameShape(QFrame.Shape.HLine)
        line_left.setStyleSheet("color: palette(placeholder-text);")
        line_left.setMaximumWidth(separator_width)
        or_label = QLabel("or")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_label.setStyleSheet(_MUTED)
        line_right = QFrame()
        line_right.setFrameShape(QFrame.Shape.HLine)
        line_right.setStyleSheet("color: palette(placeholder-text);")
        line_right.setMaximumWidth(separator_width)
        separator_layout.addStretch()
        separator_layout.addWidget(line_left)
        separator_layout.addWidget(or_label)
        separator_layout.addWidget(line_right)
        separator_layout.addStretch()
        drop_layout.addLayout(separator_layout)

        drop_zone = QLabel("Drop products here")
        drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_zone.setStyleSheet(_DROP_ZONE_STYLE)
        drop_zone.setFixedWidth(content_width)
        drop_zone.setMinimumHeight(drop_height)
        drop_layout.addWidget(drop_zone, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._drop_section, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self._search_box.textChanged.connect(self._on_text_changed)
        self._result_list.clicked.connect(self._on_result_clicked)
        self._result_list.activated.connect(self._on_result_clicked)
        self._filter_model.layoutChanged.connect(self._on_filter_ready)
        self._filter_model.modelReset.connect(self._on_filter_ready)

    def _show_results(self, show: bool):
        self._result_list.setVisible(show)
        self._drop_section.setVisible(not show)

    def _on_text_changed(self, text: str):
        if len(text.strip()) < _MIN_QUERY_LENGTH:
            self._debounce.stop()
            self._show_results(False)
            self._result_paths.clear()
            self._list_model.setStringList([])
            return
        self._debounce.start()

    def _run_query(self):
        text = self._search_box.text().strip()
        if len(text) < _MIN_QUERY_LENGTH:
            return
        self._filter_model.set_query(QueryParser.parse(text))

    def _on_filter_ready(self):
        text = self._search_box.text().strip()
        if len(text) < _MIN_QUERY_LENGTH:
            return
        count = min(self._filter_model.rowCount(), _MAX_RESULTS)
        if count == 0:
            self._show_results(False)
            self._result_paths.clear()
            self._list_model.setStringList([])
            return
        indices = [self._filter_model.index(i, 0) for i in range(count)]
        mime = self._filter_model.mimeData(indices)
        if mime is None:
            return
        products = decode_mime(mime)
        if not products:
            return
        self._result_paths = products
        self._list_model.setStringList([_display_path(p) for p in products])
        self._show_results(True)

    def _on_result_clicked(self, index: QModelIndex):
        row = index.row()
        if row < 0 or row >= len(self._result_paths):
            return
        product_path = self._result_paths[row]
        node = ProductsModel.node(product_path)
        if node is None or node.node_type() != ProductsModelNodeType.PARAMETER:
            return
        log.debug(f"Product selected from search overlay: {product_path}")
        self.product_selected.emit(product_path)

    def focus_search(self):
        self._search_box.setFocus()
