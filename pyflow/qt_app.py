from __future__ import annotations

import argparse
import json
import locale
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtTest, QtWidgets

import qt_i18n as i18n
import qt_languages as qlang
import qt_services as svc


APP_VERSION = "1.1.1"
GRAPH_LANGUAGES = {"python", "rust", "go", "c", "cpp", "zyenlang"}
NODE_DEMOS = {
    "python": ("Python", "demo_flow.py"),
    "rust": ("Rust", "demo_flow.rs"),
    "go": ("Go", "demo_flow.go"),
    "c": ("C", "demo_flow.c"),
    "cpp": ("C++", "demo_flow.cpp"),
    "zyenlang": ("ZyenLang", "demo_flow.zy"),
}
SYNTAX_CONTRAST_OPTIONS = (
    ("keyword", "關鍵字對比度"),
    ("comment", "註解對比度"),
    ("string", "字串對比度"),
    ("function", "函式對比度"),
    ("type", "型別對比度"),
    ("number", "數字對比度"),
)


def python_runtime_command() -> tuple[str, list[str]] | None:
    if not getattr(sys, "frozen", False):
        return sys.executable, []

    configured = os.environ.get("PYFLOW_PYTHON", "").strip()
    if configured and Path(configured).is_file():
        return configured, []

    for name in ("python.exe", "python3.exe", "python3", "python"):
        executable = shutil.which(name)
        if executable and Path(executable).resolve() != Path(sys.executable).resolve():
            return executable, []

    launcher = shutil.which("py.exe")
    if launcher:
        return launcher, ["-3"]
    return None


CLAUDE_STYLE = """
QMainWindow, QWidget {
  background: #1f1f1c;
  color: #e8e6df;
}
QToolBar {
  background: #262623;
  border: 0;
  border-bottom: 1px solid #3a3934;
  spacing: 3px;
  padding: 5px 7px;
}
QToolButton {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 5px;
  color: #d8d5cd;
  padding: 5px 9px;
}
QToolButton:hover {
  background: #34332f;
  border-color: #4a4841;
}
QToolButton:pressed {
  background: #403f39;
}
QTreeView, QTreeWidget, QListWidget, QListView, QPlainTextEdit, QTextEdit {
  background: #20201d;
  color: #dedbd3;
  border: 1px solid #35342f;
  selection-background-color: #754b38;
  selection-color: #fffaf4;
  outline: 0;
}
QTreeView::item, QTreeWidget::item {
  min-height: 24px;
}
QTreeView::item:hover, QTreeWidget::item:hover {
  background: #2d2c28;
}
QPlainTextEdit {
  background: #191917;
  color: #e5e2da;
  selection-background-color: #73513f;
  border: 0;
}
QGraphicsView {
  background: #191917;
  border: 1px solid #35342f;
}
QTabWidget::pane {
  border: 0;
  border-top: 1px solid #373630;
  background: #191917;
}
QTabBar::tab {
  background: #262623;
  color: #9f9d96;
  border: 0;
  border-right: 1px solid #373630;
  border-bottom: 0;
  padding: 8px 14px;
  min-width: 90px;
}
QTabBar::tab:selected {
  background: #191917;
  color: #f0eee8;
  border-top: 2px solid #d97757;
  padding-top: 6px;
}
QTabBar::tab:hover:!selected {
  background: #302f2b;
}
QDockWidget {
  titlebar-close-icon: none;
  titlebar-normal-icon: none;
  color: #d8d5cd;
  border: 1px solid #35342f;
}
QDockWidget::title {
  background: #262623;
  padding: 7px 8px;
  border-bottom: 1px solid #35342f;
}
QLineEdit, QSpinBox {
  background: #171715;
  color: #ece9e1;
  border: 1px solid #48463f;
  border-radius: 5px;
  padding: 6px;
  selection-background-color: #754b38;
}
QLineEdit:focus, QSpinBox:focus {
  border-color: #b86648;
}
QPushButton {
  background: #b85f42;
  color: #fff9f3;
  border: 0;
  border-radius: 5px;
  padding: 7px 12px;
}
QPushButton:hover { background: #cc6b4b; }
QPushButton:pressed { background: #9d4e36; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator {
  width: 14px;
  height: 14px;
  border: 1px solid #5a584f;
  border-radius: 3px;
  background: #171715;
}
QCheckBox::indicator:checked {
  background: #b85f42;
  border-color: #d87959;
}
QScrollBar:vertical {
  background: #1f1f1c;
  width: 11px;
  margin: 0;
}
QScrollBar::handle:vertical {
  background: #4a4943;
  min-height: 28px;
  border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: #5c5a53; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
  background: #1f1f1c;
  height: 11px;
  margin: 0;
}
QScrollBar::handle:horizontal {
  background: #4a4943;
  min-width: 28px;
  border-radius: 5px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QMenuBar, QMenu {
  background: #262623;
  color: #e4e1da;
}
QMenu::item:selected { background: #754b38; }
QToolTip {
  background: #34332f;
  color: #f0eee8;
  border: 1px solid #555249;
  padding: 4px;
}
QStatusBar {
  background: #262623;
  color: #aaa79f;
  border-top: 1px solid #3a3934;
}
QFrame#editorFindBar {
  background: #292925;
  border: 1px solid #48463f;
  border-radius: 6px;
}
QFrame#editorFindBar QLineEdit {
  border: 0;
  border-radius: 0;
  background: #1b1b19;
}
QLabel#zoomLabel {
  color: #d8d5cd;
  min-width: 48px;
  padding: 0 5px;
}
"""


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        self.editor.paint_line_number_area(event)


class CodeEditor(QtWidgets.QPlainTextEdit):
    zoomRequested = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        font = QtGui.QFont("Cascadia Code")
        if not QtGui.QFontInfo(font).fixedPitch():
            font = QtGui.QFont("Consolas")
        font.setPointSize(11)
        self.setFont(font)
        self.setObjectName("codeEditor")
        self.setTabStopDistance(QtGui.QFontMetricsF(font).horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setUndoRedoEnabled(True)
        self.setPlaceholderText("從左側檔案樹或工具列開啟檔案...")
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.language = "text"
        self.interface_language = "zh_TW"
        self.document_callables: set[str] = set()
        self.context_completion_words: set[str] = set()
        self.highlighter = qlang.LanguageHighlighter(self.document())
        self.find_bar = QtWidgets.QFrame(self)
        self.find_bar.setObjectName("editorFindBar")
        self.find_input = QtWidgets.QLineEdit()
        self.find_input.setClearButtonEnabled(True)
        self.find_input.textChanged.connect(self._find_query_changed)
        self.find_input.returnPressed.connect(self._find_return_pressed)
        self.find_input.installEventFilter(self)
        self.find_status = QtWidgets.QLabel("")
        self.find_case = QtWidgets.QToolButton()
        self.find_case.setText("Aa")
        self.find_case.setCheckable(True)
        self.find_case.clicked.connect(lambda: self._find_query_changed(self.find_input.text()))
        self.find_previous = QtWidgets.QToolButton()
        self.find_previous.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowBack)
        )
        self.find_previous.clicked.connect(lambda: self._find_text(backward=True))
        self.find_next = QtWidgets.QToolButton()
        self.find_next.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.find_next.clicked.connect(self._find_text)
        self.find_close = QtWidgets.QToolButton()
        self.find_close.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton
            )
        )
        self.find_close.clicked.connect(self.hide_find)
        find_layout = QtWidgets.QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(5, 4, 5, 4)
        find_layout.setSpacing(3)
        find_layout.addWidget(self.find_input, 1)
        find_layout.addWidget(self.find_status)
        find_layout.addWidget(self.find_case)
        find_layout.addWidget(self.find_previous)
        find_layout.addWidget(self.find_next)
        find_layout.addWidget(self.find_close)
        self.find_bar.hide()
        self.set_interface_language(self.interface_language)
        self.completion_model = QtGui.QStandardItemModel(0, 2, self)
        self.completer = QtWidgets.QCompleter(self.completion_model, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCompletionColumn(0)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseSensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchFlag.MatchStartsWith)
        completion_popup = QtWidgets.QTreeView()
        completion_popup.setHeaderHidden(True)
        completion_popup.setRootIsDecorated(False)
        completion_popup.setUniformRowHeights(True)
        completion_popup.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.completer.setPopup(completion_popup)
        self.completer.activated[str].connect(self._insert_completion)
        self.completion_update_timer = QtCore.QTimer(self)
        self.completion_update_timer.setSingleShot(True)
        self.completion_update_timer.setInterval(180)
        self.completion_update_timer.timeout.connect(self._refresh_completion_model)
        self.textChanged.connect(self.completion_update_timer.start)
        self.cursorPositionChanged.connect(self.completion_update_timer.start)
        self.installEventFilter(self)
        self._update_line_number_area_width()
        self._highlight_current_line()

    def set_interface_language(self, language: str) -> None:
        self.interface_language = i18n.normalize_language(language)
        self.setPlaceholderText(
            i18n.tr(
                self.interface_language,
                "從左側檔案樹或工具列開啟檔案...",
            )
        )
        self.find_input.setPlaceholderText(
            i18n.tr(self.interface_language, "在目前檔案中搜尋")
        )
        self.find_case.setToolTip(
            i18n.tr(self.interface_language, "區分大小寫")
        )
        self.find_previous.setToolTip(
            i18n.tr(self.interface_language, "上一個搜尋結果")
        )
        self.find_next.setToolTip(
            i18n.tr(self.interface_language, "下一個搜尋結果")
        )
        self.find_close.setToolTip(i18n.tr(self.interface_language, "關閉搜尋"))

    def set_editor_font_size(self, point_size: int) -> None:
        font = self.font()
        font.setPointSize(point_size)
        self.setFont(font)
        self.setTabStopDistance(QtGui.QFontMetricsF(font).horizontalAdvance(" ") * 4)
        self._update_line_number_area_width()
        self.line_number_area.update()

    def set_syntax_contrast(self, values: dict[str, int]) -> None:
        self.highlighter.set_syntax_contrast(values)

    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QtCore.QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_number_area.setGeometry(
            QtCore.QRect(rect.left(), rect.top(), self.line_number_area_width(), rect.height())
        )
        self._position_find_bar()

    def _position_find_bar(self) -> None:
        width = max(380, min(620, self.viewport().width() - 24))
        height = self.find_bar.sizeHint().height()
        self.find_bar.setGeometry(max(8, self.width() - width - 18), 8, width, height)

    def show_find(self) -> None:
        selected = self.textCursor().selectedText()
        if selected and "\u2029" not in selected and "\n" not in selected:
            self.find_input.setText(selected)
        self._position_find_bar()
        self.find_bar.show()
        self.find_bar.raise_()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._update_find_status()

    def hide_find(self) -> None:
        self.find_bar.hide()
        self.setFocus()

    def _find_return_pressed(self) -> None:
        backward = bool(
            QtWidgets.QApplication.keyboardModifiers()
            & QtCore.Qt.KeyboardModifier.ShiftModifier
        )
        self._find_text(backward=backward)

    def _find_query_changed(self, query: str) -> None:
        if not query:
            self.find_status.clear()
            return
        cursor = QtGui.QTextCursor(self.document())
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        self._find_text()

    def _find_text(self, backward: bool = False) -> None:
        query = self.find_input.text()
        if not query:
            self.find_status.clear()
            return
        flags = QtGui.QTextDocument.FindFlag(0)
        if backward:
            flags |= QtGui.QTextDocument.FindFlag.FindBackward
        if self.find_case.isChecked():
            flags |= QtGui.QTextDocument.FindFlag.FindCaseSensitively
        if not self.find(query, flags):
            cursor = QtGui.QTextCursor(self.document())
            cursor.movePosition(
                QtGui.QTextCursor.MoveOperation.End
                if backward
                else QtGui.QTextCursor.MoveOperation.Start
            )
            self.setTextCursor(cursor)
            self.find(query, flags)
        self._update_find_status()

    def _update_find_status(self) -> None:
        query = self.find_input.text()
        if not query:
            self.find_status.clear()
            return
        source = self.toPlainText()
        flags = 0 if self.find_case.isChecked() else re.IGNORECASE
        matches = list(re.finditer(re.escape(query), source, flags))
        selection_start = self.textCursor().selectionStart()
        current = next(
            (index + 1 for index, match in enumerate(matches) if match.start() == selection_start),
            0,
        )
        self.find_status.setText(f"{current}/{len(matches)}")

    def paint_line_number_area(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QtGui.QColor("#20201d"))
        painter.setFont(self.font())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current_line = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(
                    QtGui.QColor("#d99172")
                    if block_number == current_line
                    else QtGui.QColor("#77756e")
                )
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 7,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self) -> None:
        selection = QtWidgets.QTextEdit.ExtraSelection()
        selection.format.setBackground(QtGui.QColor("#22221f"))
        selection.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])
        self.line_number_area.update()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            steps = int(event.angleDelta().y() / 120)
            if steps:
                self.zoomRequested.emit(steps)
            event.accept()
            return
        super().wheelEvent(event)

    def set_language(self, language: str) -> None:
        self.language = language
        self.highlighter.set_language(language)
        self._refresh_completion_model()
        self.completer.popup().hide()

    def _refresh_completion_model(self) -> None:
        code = self.toPlainText()
        words = qlang.completion_words(self.language, code)
        details = qlang.completion_details(self.language, code)
        context_details = qlang.context_completion_details(
            self.language,
            code,
            self.textCursor().position(),
        )
        details.update(context_details)
        self.context_completion_words = set(context_details)
        words = sorted(context_details, key=str.casefold) + [
            word for word in words if word not in context_details
        ]
        self.document_callables = qlang.document_callables(self.language, code)
        self.completion_model.clear()
        self.completion_model.setHorizontalHeaderLabels(["Name", "Signature"])
        for word in words:
            detail = details.get(word, "Any")
            name_item = QtGui.QStandardItem(word)
            detail_item = QtGui.QStandardItem(detail)
            name_item.setToolTip(detail)
            detail_item.setToolTip(detail)
            self.completion_model.appendRow([name_item, detail_item])

    def _word_under_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def _insert_completion(self, completion: str) -> None:
        prefix = self.completer.completionPrefix()
        cursor = self.textCursor()
        cursor.insertText(completion[len(prefix):])
        before = cursor.block().text()[: cursor.position() - cursor.block().position()]
        decorator_context = (
            self.language == "python"
            and before[: -len(completion) if completion else None].rstrip().endswith("@")
        )
        if (
            completion in qlang.call_completions(self.language)
            or completion in self.document_callables
        ) and not decorator_context:
            cursor.insertText("()")
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)

    def _select_first_completion(self) -> None:
        popup = self.completer.popup()
        model = self.completer.completionModel()
        if model.rowCount() <= 0:
            return
        self.completer.setCurrentRow(0)
        first = model.index(0, 0)
        popup.setCurrentIndex(first)
        popup.selectionModel().setCurrentIndex(
            first,
            QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QtCore.QItemSelectionModel.SelectionFlag.Rows,
        )
        popup.scrollTo(first)

    def _insert_newline_with_indent(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        block = cursor.block()
        text = block.text()
        offset = cursor.position() - block.position()
        before = text[:offset]
        after = text[offset:]
        leading_match = re.match(r"^[ \t]*", before)
        leading = leading_match.group(0) if leading_match else ""
        stripped = before.rstrip()
        indent = leading

        if self.language == "python" and stripped.endswith(":"):
            indent += " " * 4
        elif self.language in {"rust", "go", "c", "cpp", "zyenlang"} and stripped.endswith("{"):
            indent += " " * 4
        elif stripped.count("(") + stripped.count("[") > stripped.count(")") + stripped.count("]"):
            indent += " " * 4

        paired_braces = (
            self.language in {"rust", "go", "c", "cpp", "zyenlang"}
            and stripped.endswith("{")
            and after.lstrip().startswith("}")
        )
        if paired_braces:
            cursor.insertText("\n" + indent + "\n" + leading)
            cursor.movePosition(
                QtGui.QTextCursor.MoveOperation.Left,
                QtGui.QTextCursor.MoveMode.MoveAnchor,
                len(leading) + 1,
            )
        else:
            cursor.insertText("\n" + indent)
        self.setTextCursor(cursor)
        self._refresh_completion_model()

    def _unindent_current_line(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return
        block = cursor.block()
        text = block.text()
        spaces = len(text) - len(text.lstrip(" "))
        remove_count = min(4, spaces)
        if not remove_count:
            return
        original_position = cursor.position()
        edit = QtGui.QTextCursor(self.document())
        edit.setPosition(block.position())
        edit.setPosition(
            block.position() + remove_count,
            QtGui.QTextCursor.MoveMode.KeepAnchor,
        )
        edit.removeSelectedText()
        cursor.setPosition(max(block.position(), original_position - remove_count))
        self.setTextCursor(cursor)

    def _toggle_line_comment(self) -> None:
        prefix = {
            "python": "#",
            "shell": "#",
            "yaml": "#",
            "toml": "#",
            "rust": "//",
            "go": "//",
            "c": "//",
            "cpp": "//",
            "zyenlang": "//",
            "javascript": "//",
            "typescript": "//",
            "sql": "--",
        }.get(self.language)
        if not prefix:
            return

        cursor = self.textCursor()
        had_selection = cursor.hasSelection()
        original_position = cursor.position()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        start_block = self.document().findBlock(start)
        end_position = end
        if had_selection and end > start:
            end_block_at_cursor = self.document().findBlock(end)
            if end_block_at_cursor.isValid() and end_block_at_cursor.position() == end:
                end_position = end - 1
        end_block = self.document().findBlock(max(start, end_position))
        start_number = start_block.blockNumber()
        end_number = end_block.blockNumber()

        blocks = [
            self.document().findBlockByNumber(number)
            for number in range(start_number, end_number + 1)
        ]
        nonempty = [block for block in blocks if block.text().strip()]
        uncomment = bool(nonempty) and all(
            block.text().lstrip(" \t").startswith(prefix) for block in nonempty
        )

        operations: list[tuple[int, int, str]] = []
        for block in blocks:
            text = block.text()
            leading = len(text) - len(text.lstrip(" \t"))
            content = text[leading:]
            position = block.position() + leading
            if uncomment:
                if not content.startswith(prefix):
                    continue
                remove_count = len(prefix)
                if content[remove_count:].startswith(" "):
                    remove_count += 1
                operations.append((position, remove_count, ""))
            elif text.strip() or len(blocks) == 1:
                operations.append((position, 0, prefix + " "))

        if not operations:
            return
        edit = QtGui.QTextCursor(self.document())
        edit.beginEditBlock()
        for position, remove_count, replacement in reversed(operations):
            edit.setPosition(position)
            if remove_count:
                edit.setPosition(
                    position + remove_count,
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                )
            edit.insertText(replacement)
        edit.endEditBlock()

        restored = self.textCursor()
        if had_selection:
            first_block = self.document().findBlockByNumber(start_number)
            last_block = self.document().findBlockByNumber(end_number)
            restored.setPosition(first_block.position())
            restored.setPosition(
                last_block.position() + len(last_block.text()),
                QtGui.QTextCursor.MoveMode.KeepAnchor,
            )
        else:
            position, remove_count, replacement = operations[0]
            delta = len(replacement) - remove_count
            new_position = original_position
            if original_position >= position + remove_count:
                new_position += delta
            elif original_position > position:
                new_position = position + len(replacement)
            restored.setPosition(max(0, new_position))
        self.setTextCursor(restored)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if (
            watched is getattr(self, "find_input", None)
            and event.type() == QtCore.QEvent.Type.KeyPress
            and event.key() == QtCore.Qt.Key.Key_Escape
        ):
            self.hide_find()
            return True
        if (
            watched is self
            and event.type() == QtCore.QEvent.Type.KeyPress
            and self.completer.popup().isVisible()
        ):
            key_event = event
            if key_event.key() in {
                QtCore.Qt.Key.Key_Enter,
                QtCore.Qt.Key.Key_Return,
                QtCore.Qt.Key.Key_Tab,
                QtCore.Qt.Key.Key_Backtab,
            }:
                completion = self.completer.currentCompletion()
                if completion:
                    self._insert_completion(completion)
                self.completer.popup().hide()
                return True
            if key_event.key() == QtCore.Qt.Key.Key_Escape:
                self.completer.popup().hide()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.matches(QtGui.QKeySequence.StandardKey.Find):
            self.show_find()
            event.accept()
            return
        popup = self.completer.popup()
        if (
            event.key() == QtCore.Qt.Key.Key_Slash
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self._toggle_line_comment()
            popup.hide()
            event.accept()
            return
        if popup.isVisible() and event.key() in {
            QtCore.Qt.Key.Key_Enter,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Escape,
            QtCore.Qt.Key.Key_Tab,
            QtCore.Qt.Key.Key_Backtab,
        }:
            event.ignore()
            return

        manual = (
            event.key() == QtCore.Qt.Key.Key_Space
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        )
        if not manual and event.key() in {
            QtCore.Qt.Key.Key_Enter,
            QtCore.Qt.Key.Key_Return,
        }:
            self._insert_newline_with_indent()
            popup.hide()
            return
        if not manual and event.key() == QtCore.Qt.Key.Key_Tab:
            cursor = self.textCursor()
            cursor.insertText(" " * 4)
            self.setTextCursor(cursor)
            popup.hide()
            return
        if not manual and event.key() == QtCore.Qt.Key.Key_Backtab:
            self._unindent_current_line()
            popup.hide()
            return
        if (
            not manual
            and event.text() == "}"
            and self.language in {"rust", "go", "c", "cpp", "zyenlang"}
        ):
            cursor = self.textCursor()
            before = cursor.block().text()[: cursor.position() - cursor.block().position()]
            if before and not before.strip():
                self._unindent_current_line()
        if not manual:
            super().keyPressEvent(event)

        if self.language not in qlang.EDITOR_LANGUAGES:
            popup.hide()
            return

        prefix = self._word_under_cursor()
        typed_word_char = bool(event.text()) and (event.text().isalnum() or event.text() == "_")
        if (
            not manual
            and typed_word_char
            and len(prefix) == 1
            and self.language in {"python", "zyenlang"}
        ):
            self._refresh_completion_model()
        short_context_match = bool(prefix) and any(
            word.startswith(prefix) for word in self.context_completion_words
        )
        if not manual and (
            not typed_word_char or (len(prefix) < 2 and not short_context_match)
        ):
            popup.hide()
            return

        self.completer.setCompletionPrefix(prefix)
        if self.completer.completionCount() == 0:
            popup.hide()
            return

        rect = self.cursorRect()
        popup.resizeColumnToContents(0)
        popup.resizeColumnToContents(1)
        width = (
            popup.sizeHintForColumn(0)
            + popup.sizeHintForColumn(1)
            + popup.verticalScrollBar().sizeHint().width()
            + 28
        )
        available_width = max(420, min(self.viewport().width() - 24, 920))
        rect.setWidth(max(340, min(width, available_width)))
        self.completer.complete(rect)
        self._select_first_completion()

    def goto_line(self, line: int) -> None:
        if line < 1:
            return
        block = self.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return
        cursor = QtGui.QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()


class FlowGraphView(QtWidgets.QGraphicsView):
    nodeActivated = QtCore.Signal(int)
    nodeSelected = QtCore.Signal(str)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        interface_language: str = "zh_TW",
    ) -> None:
        super().__init__(parent)
        self.interface_language = i18n.normalize_language(interface_language)
        self.graph_scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.graph_scene)
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumHeight(260)
        self.ui_font_size = 9
        self.graph: dict[str, object] = {"nodes": [], "edges": [], "error": None}
        self.title = ""

    def set_graph(self, graph: dict[str, object], title: str) -> None:
        self.graph = graph
        self.title = title
        self._render()

    def set_ui_font_size(self, point_size: int) -> None:
        self.ui_font_size = point_size
        self._render()

    def _node_positions(
        self,
        nodes: list[dict[str, object]],
        edges: list[dict[str, object]],
        width: float,
        height: float,
    ) -> dict[str, QtCore.QPointF]:
        node_ids = [str(node["id"]) for node in nodes]
        incoming = {node_id: 0 for node_id in node_ids}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            if source in outgoing and target in incoming:
                outgoing[source].append(target)
                incoming[target] += 1

        roots = [node_id for node_id in node_ids if incoming[node_id] == 0]
        if "__module__" in node_ids:
            roots = ["__module__"] + [node_id for node_id in roots if node_id != "__module__"]
        layers = {node_id: 0 for node_id in roots}
        queue = list(roots)
        while queue:
            source = queue.pop(0)
            for target in outgoing[source]:
                if target not in layers:
                    layers[target] = layers[source] + 1
                    queue.append(target)
        for node_id in node_ids:
            layers.setdefault(node_id, 0)

        grouped: dict[int, list[str]] = {}
        for node_id in node_ids:
            grouped.setdefault(layers[node_id], []).append(node_id)
        scale = self.ui_font_size / 9
        x_gap = 74 * scale
        y_gap = 28 * scale
        positions: dict[str, QtCore.QPointF] = {}
        max_rows = 10
        column_cursor = 0
        for layer, ids in sorted(grouped.items()):
            column_count = max(1, (len(ids) + max_rows - 1) // max_rows)
            for index, node_id in enumerate(ids):
                column = column_cursor + index // max_rows
                row = index % max_rows
                positions[node_id] = QtCore.QPointF(
                    24 * scale + column * (width + x_gap),
                    42 * scale + row * (height + y_gap),
                )
            column_cursor += column_count
        return positions

    def _render(self) -> None:
        self.graph_scene.clear()
        nodes = list(self.graph.get("nodes") or [])
        edges = list(self.graph.get("edges") or [])
        error = self.graph.get("error")
        font = QtGui.QFont("Microsoft JhengHei UI", self.ui_font_size)
        if error:
            item = self.graph_scene.addText(str(error), font)
            item.setDefaultTextColor(QtGui.QColor("#d99172"))
            return
        if not nodes:
            return

        scale = self.ui_font_size / 9
        width = 300 * scale
        height = 108 * scale
        positions = self._node_positions(nodes, edges, width, height)
        node_map = {str(node["id"]): node for node in nodes}

        edge_pen = QtGui.QPen(QtGui.QColor("#716d64"), max(1.5, 1.8 * scale))
        edge_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        for edge in edges:
            source_id = str(edge.get("source", ""))
            target_id = str(edge.get("target", ""))
            if source_id not in positions or target_id not in positions:
                continue
            source = positions[source_id] + QtCore.QPointF(width, height / 2)
            target = positions[target_id] + QtCore.QPointF(0, height / 2)
            path = QtGui.QPainterPath(source)
            bend = max(42 * scale, abs(target.x() - source.x()) * 0.46)
            path.cubicTo(
                source + QtCore.QPointF(bend, 0),
                target - QtCore.QPointF(bend, 0),
                target,
            )
            edge_item = self.graph_scene.addPath(path, edge_pen)
            edge_item.setZValue(-2)
            arrow = QtGui.QPolygonF(
                [
                    target,
                    target + QtCore.QPointF(-10 * scale, -5 * scale),
                    target + QtCore.QPointF(-10 * scale, 5 * scale),
                ]
            )
            arrow_item = self.graph_scene.addPolygon(arrow, edge_pen, QtGui.QBrush("#716d64"))
            arrow_item.setZValue(-1)

        kind_colors = {
            "module": "#d97757",
            "class": "#c8a96b",
            "method": "#7fa8c9",
            "async": "#a48bc2",
            "function": "#79a88b",
        }
        for node_id, point in positions.items():
            node = node_map[node_id]
            rect = QtCore.QRectF(point.x(), point.y(), width, height)
            path = QtGui.QPainterPath()
            path.addRoundedRect(rect, 6 * scale, 6 * scale)
            color = QtGui.QColor(kind_colors.get(str(node.get("kind")), "#8b8981"))
            node_item = self.graph_scene.addPath(
                path,
                QtGui.QPen(color, max(1.5, 2 * scale)),
                QtGui.QBrush("#292925"),
            )
            node_item.setData(0, int(node.get("line") or 0))
            node_item.setData(1, node_id)
            node_item.setFlag(
                QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                True,
            )
            tooltip_parts = [
                str(node.get("signature") or node.get("label") or node_id),
                i18n.tr(self.interface_language, "第 {line} 行", line=node.get("line", 0)),
                i18n.tr(
                    self.interface_language,
                    "呼叫 {outgoing} 個節點，被 {incoming} 個節點呼叫",
                    outgoing=node.get("outgoing", 0),
                    incoming=node.get("incoming", 0),
                ),
            ]
            if node.get("calls"):
                tooltip_parts.append(
                    i18n.tr(
                        self.interface_language,
                        "呼叫：{calls}",
                        calls=", ".join(str(value) for value in node["calls"]),
                    )
                )
            if node.get("doc"):
                tooltip_parts.append(str(node["doc"]))
            node_item.setToolTip("\n".join(tooltip_parts))

            label_text = str(node.get("label") or node_id)
            if node_id == "__module__":
                label_text = i18n.tr(self.interface_language, "程式入口")
            label = QtWidgets.QGraphicsTextItem(label_text, node_item)
            label.setDefaultTextColor(QtGui.QColor("#f0eee8"))
            label.setFont(QtGui.QFont("Microsoft JhengHei UI", self.ui_font_size + 1, QtGui.QFont.Weight.DemiBold))
            label.setTextWidth(width - 20 * scale)
            label.setPos(point + QtCore.QPointF(10 * scale, 7 * scale))

            signature_font = QtGui.QFont("Cascadia Code", max(8, self.ui_font_size - 1))
            signature_metrics = QtGui.QFontMetrics(signature_font)
            signature_text = signature_metrics.elidedText(
                str(node.get("signature") or ""),
                QtCore.Qt.TextElideMode.ElideRight,
                round(width - 22 * scale),
            )
            signature = QtWidgets.QGraphicsSimpleTextItem(signature_text, node_item)
            signature.setBrush(QtGui.QBrush("#c8c4ba"))
            signature.setFont(signature_font)
            signature.setPos(point + QtCore.QPointF(11 * scale, 45 * scale))

            kind_names = {
                "module": i18n.tr(self.interface_language, "入口"),
                "class": i18n.tr(self.interface_language, "類別"),
                "method": i18n.tr(self.interface_language, "方法"),
                "async": i18n.tr(self.interface_language, "非同步函式"),
                "function": i18n.tr(self.interface_language, "函式"),
            }
            detail = QtWidgets.QGraphicsSimpleTextItem(
                i18n.tr(
                    self.interface_language,
                    "{kind}  |  第 {line} 行  |  呼叫 {outgoing}  |  被呼叫 {incoming}",
                    kind=kind_names.get(
                        str(node.get("kind")), i18n.tr(self.interface_language, "節點")
                    ),
                    line=node.get("line", 0),
                    outgoing=node.get("outgoing", 0),
                    incoming=node.get("incoming", 0),
                ),
                node_item,
            )
            detail.setBrush(QtGui.QBrush("#99968e"))
            detail.setFont(QtGui.QFont("Microsoft JhengHei UI", max(8, self.ui_font_size - 1)))
            detail.setPos(point + QtCore.QPointF(11 * scale, 76 * scale))

        title = self.title
        if self.graph.get("truncated"):
            title += "  |  " + i18n.tr(
                self.interface_language,
                "顯示 {shown} / {total} 個節點",
                shown=len(nodes),
                total=self.graph.get("total_definitions", len(nodes)),
            )
        title_item = self.graph_scene.addText(title, QtGui.QFont("Microsoft JhengHei UI", self.ui_font_size + 1))
        title_item.setDefaultTextColor(QtGui.QColor("#d99172"))
        title_item.setPos(18 * scale, 4 * scale)
        bounds = self.graph_scene.itemsBoundingRect().adjusted(-20, -20, 30, 30)
        self.graph_scene.setSceneRect(bounds)
        QtCore.QTimer.singleShot(0, self.fit_graph)

    def fit_graph(self) -> None:
        if not self.graph_scene.items():
            return
        self.resetTransform()
        if len(self.graph.get("nodes") or []) <= 24:
            self.fitInView(self.graph_scene.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            # fitInView cancels larger node geometry; restore the user's global zoom.
            global_zoom = self.ui_font_size / 9
            self.scale(global_zoom, global_zoom)
        else:
            self.scale(0.9, 0.9)
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
            self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def focus_node(self, node_id: str) -> bool:
        for item in self.graph_scene.items():
            if str(item.data(1) or "") != node_id:
                continue
            self.graph_scene.clearSelection()
            item.setSelected(True)
            self.centerOn(item.sceneBoundingRect().center())
            return True
        return False

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        while item is not None and not item.data(0):
            item = item.parentItem()
        if item is not None and item.data(0):
            self.nodeActivated.emit(int(item.data(0)))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        while item is not None and not item.data(1):
            item = item.parentItem()
        if item is not None and item.data(1):
            self.graph_scene.clearSelection()
            item.setSelected(True)
            self.nodeSelected.emit(str(item.data(1)))
        super().mousePressEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            super().wheelEvent(event)
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        event.accept()


class NodeGraphPanel(QtWidgets.QWidget):
    nodeActivated = QtCore.Signal(int)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        interface_language: str = "zh_TW",
    ) -> None:
        super().__init__(parent)
        self.interface_language = i18n.normalize_language(interface_language)
        self.graph: dict[str, object] = {"nodes": [], "edges": [], "error": None}
        self.nodes: dict[str, dict[str, object]] = {}
        self.current_node_id = ""
        self.node_search_matches: list[str] = []
        self.node_search_index = -1

        self.node_search = QtWidgets.QLineEdit()
        self.node_search.setPlaceholderText(
            i18n.tr(self.interface_language, "搜尋節點或函式...")
        )
        self.node_search.setClearButtonEnabled(True)
        self.node_search.addAction(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView
            ),
            QtWidgets.QLineEdit.ActionPosition.LeadingPosition,
        )
        self.node_search_model = QtCore.QStringListModel(self)
        self.node_search_completer = QtWidgets.QCompleter(
            self.node_search_model, self
        )
        self.node_search_completer.setCaseSensitivity(
            QtCore.Qt.CaseSensitivity.CaseInsensitive
        )
        self.node_search_completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self.node_search.setCompleter(self.node_search_completer)
        self.node_search.textChanged.connect(self._update_node_search)
        self.node_search.returnPressed.connect(self._activate_node_search)
        self.node_search_completer.activated[str].connect(
            self._activate_node_search_text
        )

        self.node_search_status = QtWidgets.QLabel("")
        self.node_search_previous = QtWidgets.QToolButton()
        self.node_search_previous.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowBack)
        )
        self.node_search_previous.setToolTip(
            i18n.tr(self.interface_language, "上一個搜尋結果")
        )
        self.node_search_previous.clicked.connect(
            lambda: self._step_node_search(-1)
        )
        self.node_search_next = QtWidgets.QToolButton()
        self.node_search_next.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.node_search_next.setToolTip(
            i18n.tr(self.interface_language, "下一個搜尋結果")
        )
        self.node_search_next.clicked.connect(lambda: self._step_node_search(1))

        search_row = QtWidgets.QHBoxLayout()
        search_row.setContentsMargins(8, 6, 8, 0)
        search_row.setSpacing(5)
        search_row.addWidget(self.node_search, 1)
        search_row.addWidget(self.node_search_status)
        search_row.addWidget(self.node_search_previous)
        search_row.addWidget(self.node_search_next)

        self.graph_view = FlowGraphView(interface_language=self.interface_language)
        self.graph_view.nodeActivated.connect(self.nodeActivated.emit)
        self.graph_view.nodeSelected.connect(self.select_node)

        self.node_name = QtWidgets.QLabel(i18n.tr(self.interface_language, "節點關係"))
        self.node_name.setObjectName("nodeRelationTitle")
        self.node_name.setWordWrap(True)
        self.go_to_code = QtWidgets.QPushButton(
            i18n.tr(self.interface_language, "前往程式碼")
        )
        self.go_to_code.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.go_to_code.clicked.connect(self._activate_current_node)

        self.node_signature = QtWidgets.QLabel("")
        self.node_signature.setWordWrap(True)
        self.node_signature.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.parameters = QtWidgets.QTreeWidget()
        self.parameters.setHeaderLabels(
            [
                i18n.tr(self.interface_language, "參數"),
                i18n.tr(self.interface_language, "型別"),
                i18n.tr(self.interface_language, "預設值"),
            ]
        )
        self.parameters.setRootIsDecorated(False)
        self.parameters.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.parameters.header().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.parameters.header().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.return_type = QtWidgets.QLabel("")
        self.return_type.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.node_doc = QtWidgets.QLabel("")
        self.node_doc.setWordWrap(True)
        self.node_doc.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.node_counts = QtWidgets.QLabel("")
        self.node_counts.setWordWrap(True)

        self.relations = QtWidgets.QTreeWidget()
        self.relations.setHeaderLabels(
            [
                i18n.tr(self.interface_language, "關係與節點"),
                i18n.tr(self.interface_language, "行"),
            ]
        )
        self.relations.setRootIsDecorated(True)
        self.relations.setAlternatingRowColors(False)
        self.relations.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.relations.header().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.relations.itemDoubleClicked.connect(self._activate_relation)

        details_page = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(details_page)
        details_layout.setContentsMargins(6, 6, 6, 6)
        details_layout.setSpacing(7)
        details_layout.addWidget(self.node_signature)
        details_layout.addWidget(self.parameters, 1)
        details_layout.addWidget(self.return_type)
        details_layout.addWidget(self.node_doc)

        calls_page = QtWidgets.QWidget()
        calls_layout = QtWidgets.QVBoxLayout(calls_page)
        calls_layout.setContentsMargins(6, 6, 6, 6)
        calls_layout.setSpacing(7)
        calls_layout.addWidget(self.node_counts)
        calls_layout.addWidget(self.relations, 1)

        self.detail_tabs = QtWidgets.QTabWidget()
        self.detail_tabs.addTab(
            details_page, i18n.tr(self.interface_language, "詳細資料")
        )
        self.detail_tabs.addTab(
            calls_page, i18n.tr(self.interface_language, "呼叫關係")
        )

        details = QtWidgets.QWidget()
        details.setMinimumWidth(310)
        detail_layout = QtWidgets.QVBoxLayout(details)
        detail_layout.setContentsMargins(10, 8, 8, 8)
        detail_layout.setSpacing(7)
        heading = QtWidgets.QHBoxLayout()
        heading.addWidget(self.node_name, 1)
        heading.addWidget(self.go_to_code)
        detail_layout.addLayout(heading)
        detail_layout.addWidget(self.detail_tabs, 1)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.graph_view)
        self.splitter.addWidget(details)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([860, 360])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(search_row)
        layout.addWidget(self.splitter)

    def set_graph(self, graph: dict[str, object], title: str) -> None:
        self.graph = graph
        self.nodes = {
            str(node.get("id")): node
            for node in (graph.get("nodes") or [])
            if isinstance(node, dict) and node.get("id") is not None
        }
        self._refresh_node_search()
        self.graph_view.set_graph(graph, title)
        selected = self.current_node_id if self.current_node_id in self.nodes else ""
        if not selected and self.nodes:
            selected = next(iter(self.nodes))
        if selected:
            self.select_node(selected)
        else:
            self.current_node_id = ""
            self.node_name.setText(i18n.tr(self.interface_language, "節點關係"))
            self.node_signature.setText(str(graph.get("error") or ""))
            self.parameters.clear()
            self.return_type.clear()
            self.node_doc.clear()
            self.node_counts.clear()
            self.relations.clear()
            self.go_to_code.setEnabled(False)

    def set_ui_font_size(self, point_size: int) -> None:
        font = QtGui.QFont("Microsoft JhengHei UI", point_size)
        self.setFont(font)
        for widget in (
            self.node_name,
            self.node_signature,
            self.parameters,
            self.return_type,
            self.node_doc,
            self.node_counts,
            self.relations,
            self.detail_tabs,
            self.go_to_code,
            self.node_search,
            self.node_search_status,
            self.node_search_previous,
            self.node_search_next,
        ):
            widget.setFont(font)
        self.graph_view.set_ui_font_size(point_size)

    def _refresh_node_search(self) -> None:
        labels = sorted(
            {
                str(node.get("label") or node_id)
                for node_id, node in self.nodes.items()
            },
            key=str.casefold,
        )
        self.node_search_model.setStringList(labels)
        self._update_node_search(self.node_search.text())

    def _update_node_search(self, text: str) -> None:
        query = text.strip().casefold()
        self.node_search_index = -1
        if not query:
            self.node_search_matches = []
            self.node_search_status.clear()
            return
        self.node_search_matches = [
            node_id
            for node_id, node in self.nodes.items()
            if query
            in " ".join(
                (
                    node_id,
                    str(node.get("label") or ""),
                    str(node.get("signature") or ""),
                )
            ).casefold()
        ]
        self.node_search_status.setText(str(len(self.node_search_matches)))

    def _activate_node_search_text(self, text: str) -> None:
        self.node_search.setText(text)
        expected = text.casefold()
        for index, node_id in enumerate(self.node_search_matches):
            node = self.nodes[node_id]
            if str(node.get("label") or node_id).casefold() == expected:
                self.node_search_index = index
                self._focus_node_search_result()
                return
        self._activate_node_search()

    def _activate_node_search(self) -> None:
        self._step_node_search(1)

    def _step_node_search(self, direction: int) -> None:
        if not self.node_search_matches:
            return
        if self.node_search_index < 0:
            self.node_search_index = 0 if direction >= 0 else len(
                self.node_search_matches
            ) - 1
        else:
            self.node_search_index = (
                self.node_search_index + direction
            ) % len(self.node_search_matches)
        self._focus_node_search_result()

    def _focus_node_search_result(self) -> None:
        if not (0 <= self.node_search_index < len(self.node_search_matches)):
            return
        node_id = self.node_search_matches[self.node_search_index]
        self.select_node(node_id)
        self.graph_view.focus_node(node_id)
        self.node_search_status.setText(
            f"{self.node_search_index + 1}/{len(self.node_search_matches)}"
        )

    def select_node(self, node_id: str) -> None:
        node = self.nodes.get(node_id)
        if not node:
            return
        self.current_node_id = node_id
        line = int(node.get("line") or 0)
        signature = str(node.get("signature") or node.get("label") or node_id)
        node_label = str(node.get("label") or node_id)
        if node_id == "__module__":
            node_label = i18n.tr(self.interface_language, "程式入口")
            signature = i18n.tr(self.interface_language, signature)
        self.node_name.setText(node_label)
        self.go_to_code.setEnabled(bool(line))
        self.node_signature.setText(
            i18n.tr(
                self.interface_language,
                "第 {line} 行  |  {signature}",
                line=line,
                signature=signature,
            )
        )

        self.parameters.clear()
        raw_parameters = node.get("parameters") or []
        if raw_parameters:
            for raw_parameter in raw_parameters:
                if not isinstance(raw_parameter, dict):
                    continue
                self.parameters.addTopLevelItem(
                    QtWidgets.QTreeWidgetItem(
                        [
                            str(raw_parameter.get("name") or "Any"),
                            str(raw_parameter.get("type") or "Any"),
                            str(raw_parameter.get("default") or ""),
                        ]
                    )
                )
        else:
            empty_parameter = QtWidgets.QTreeWidgetItem(
                [i18n.tr(self.interface_language, "沒有參數"), "", ""]
            )
            empty_parameter.setFlags(
                empty_parameter.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled
            )
            self.parameters.addTopLevelItem(empty_parameter)
        self.return_type.setText(
            i18n.tr(
                self.interface_language,
                "回傳型別：{type}",
                type=str(node.get("return_type") or "Any"),
            )
        )
        doc = str(node.get("doc") or "").strip()
        self.node_doc.setText(
            i18n.tr(self.interface_language, "說明：{doc}", doc=doc) if doc else ""
        )
        self.node_doc.setVisible(bool(doc))

        outgoing_ids: list[str] = []
        incoming_ids: list[str] = []
        for edge in self.graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            if source == node_id and target in self.nodes:
                outgoing_ids.append(target)
            if target == node_id and source in self.nodes:
                incoming_ids.append(source)
        outgoing_ids = list(dict.fromkeys(outgoing_ids))
        incoming_ids = list(dict.fromkeys(incoming_ids))
        self.node_counts.setText(
            i18n.tr(
                self.interface_language,
                "呼叫其他 {outgoing} 個節點  |  由 {incoming} 個節點呼叫",
                outgoing=len(outgoing_ids),
                incoming=len(incoming_ids),
            )
        )

        self.relations.clear()
        self._add_relation_group(
            i18n.tr(
                self.interface_language,
                "它呼叫的節點（{count}）",
                count=len(outgoing_ids),
            ),
            outgoing_ids,
        )
        self._add_relation_group(
            i18n.tr(
                self.interface_language,
                "呼叫它的節點（{count}）",
                count=len(incoming_ids),
            ),
            incoming_ids,
        )
        self.relations.expandAll()

    def _add_relation_group(self, title: str, node_ids: list[str]) -> None:
        group = QtWidgets.QTreeWidgetItem([title, ""])
        group.setFirstColumnSpanned(True)
        group.setFlags(group.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
        self.relations.addTopLevelItem(group)
        if not node_ids:
            empty = QtWidgets.QTreeWidgetItem(
                [i18n.tr(self.interface_language, "沒有"), ""]
            )
            empty.setFlags(empty.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            group.addChild(empty)
            return
        for related_id in node_ids:
            related = self.nodes[related_id]
            line = int(related.get("line") or 0)
            item = QtWidgets.QTreeWidgetItem(
                [str(related.get("label") or related_id), str(line or "")]
            )
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, related_id)
            item.setData(1, QtCore.Qt.ItemDataRole.UserRole, line)
            group.addChild(item)

    def _activate_relation(self, item: QtWidgets.QTreeWidgetItem) -> None:
        node_id = str(item.data(0, QtCore.Qt.ItemDataRole.UserRole) or "")
        if node_id not in self.nodes:
            return
        line = int(self.nodes[node_id].get("line") or 0)
        self.select_node(node_id)
        self.graph_view.focus_node(node_id)
        if line:
            self.nodeActivated.emit(line)

    def _activate_current_node(self) -> None:
        node = self.nodes.get(self.current_node_id)
        line = int(node.get("line") or 0) if node else 0
        if line:
            self.nodeActivated.emit(line)


class PowerShellPanel(QtWidgets.QWidget):
    closeRequested = QtCore.Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        interface_language: str = "zh_TW",
    ) -> None:
        super().__init__(parent)
        self.interface_language = i18n.normalize_language(interface_language)
        self.encoding = locale.getpreferredencoding(False) or "utf-8"
        self.cwd = str(Path.home())
        self.history: list[str] = []
        self.history_index = 0
        self.ready = False
        self.ready_probe_attempts = 0

        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(
            QtCore.QProcess.ProcessChannelMode.MergedChannels
        )
        self.process.started.connect(self._process_started)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.output_timer = QtCore.QTimer(self)
        self.output_timer.setInterval(50)
        self.output_timer.timeout.connect(self._poll_output)

        self.title = QtWidgets.QLabel("PowerShell")
        title_font = self.title.font()
        title_font.setBold(True)
        self.title.setFont(title_font)
        self.status = QtWidgets.QLabel("")
        self.cwd_label = QtWidgets.QLabel("")
        self.cwd_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.restart_button = QtWidgets.QToolButton()
        self.restart_button.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.restart_button.setToolTip(
            i18n.tr(self.interface_language, "重新啟動 PowerShell")
        )
        self.restart_button.clicked.connect(self.restart)
        self.clear_button = QtWidgets.QToolButton()
        self.clear_button.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton
            )
        )
        self.clear_button.setToolTip(
            i18n.tr(self.interface_language, "清除終端內容")
        )
        self.clear_button.clicked.connect(self.output_clear)
        self.close_button = QtWidgets.QToolButton()
        self.close_button.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_TitleBarCloseButton
            )
        )
        self.close_button.setToolTip(
            i18n.tr(self.interface_language, "關閉 PowerShell")
        )
        self.close_button.clicked.connect(self.closeRequested.emit)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        terminal_font = QtGui.QFont("Cascadia Mono")
        if not QtGui.QFontInfo(terminal_font).fixedPitch():
            terminal_font = QtGui.QFont("Consolas")
        terminal_font.setPointSize(10)
        self.output.setFont(terminal_font)

        self.prompt = QtWidgets.QLabel("PS>")
        self.input = QtWidgets.QLineEdit()
        input_font = QtGui.QFont(terminal_font)
        input_font.setPointSize(12)
        self.prompt.setFont(input_font)
        self.input.setFont(input_font)
        self.input.setMinimumHeight(QtGui.QFontMetrics(input_font).height() + 12)
        self.input.setPlaceholderText(
            i18n.tr(self.interface_language, "輸入 PowerShell 指令")
        )
        self.input.setEnabled(False)
        self.input.returnPressed.connect(self.run_command)
        self.input.installEventFilter(self)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(5)
        title_row.addWidget(self.title)
        title_row.addWidget(self.status)
        title_row.addWidget(self.cwd_label, 1)
        title_row.addWidget(self.restart_button)
        title_row.addWidget(self.clear_button)
        title_row.addWidget(self.close_button)

        input_row = QtWidgets.QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(6)
        input_row.addWidget(self.prompt)
        input_row.addWidget(self.input, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 7)
        layout.setSpacing(5)
        layout.addLayout(title_row)
        layout.addWidget(self.output, 1)
        layout.addLayout(input_row)

    def start(self, cwd: str | None = None) -> None:
        if cwd and Path(cwd).is_dir():
            self.cwd = str(Path(cwd).resolve())
        self.cwd_label.setText(self.cwd)
        self.cwd_label.setToolTip(self.cwd)
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.focus_input()
            return
        program = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
        if not program:
            self.output.appendPlainText(
                i18n.tr(self.interface_language, "找不到 PowerShell")
            )
            self.status.setText(i18n.tr(self.interface_language, "無法啟動"))
            return
        self.process.setWorkingDirectory(self.cwd)
        self.ready = False
        self.ready_probe_attempts = 0
        self.input.setEnabled(False)
        self.status.setText(i18n.tr(self.interface_language, "正在啟動..."))
        self.process.start(
            program,
            ["-NoLogo", "-NoProfile", "-NoExit", "-Command", "-"],
        )

    def restart(self) -> None:
        self.stop()
        QtCore.QTimer.singleShot(100, lambda: self.start(self.cwd))

    def stop(self) -> None:
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            return
        self.process.terminate()
        if not self.process.waitForFinished(500):
            self.process.kill()
            self.process.waitForFinished(500)

    def output_clear(self) -> None:
        self.output.clear()

    def focus_input(self) -> None:
        self.input.setFocus()

    def run_command(self) -> None:
        command = self.input.text().strip()
        if not command or not self.ready:
            return
        self.history.append(command)
        self.history_index = len(self.history)
        self.output.appendPlainText(f"PS> {command}\n")
        self.input.clear()
        self.process.write((command + "\r\n").encode(self.encoding, errors="replace"))
        self.process.waitForBytesWritten(500)

    def _process_started(self) -> None:
        self.output_timer.start()
        QtCore.QTimer.singleShot(100, self._send_ready_probe)

    def _send_ready_probe(self) -> None:
        if self.ready or self.process.state() != QtCore.QProcess.ProcessState.Running:
            return
        self.ready_probe_attempts += 1
        self.process.write(
            b"Write-Output '__PYFLOW_POWERSHELL_READY__'\r\n"
        )
        self.process.waitForBytesWritten(500)
        self.process.waitForReadyRead(1200)
        self._read_output()
        if not self.ready and self.ready_probe_attempts < 3:
            QtCore.QTimer.singleShot(200, self._send_ready_probe)

    def _read_output(self) -> None:
        raw = bytes(self.process.readAllStandardOutput())
        if not raw:
            return
        text = raw.decode(self.encoding, errors="replace").replace("\r\n", "\n")
        if "__PYFLOW_POWERSHELL_READY__" in text:
            text = text.replace("__PYFLOW_POWERSHELL_READY__", "").lstrip("\n")
            self.ready = True
            self.status.setText(i18n.tr(self.interface_language, "執行中"))
            self.input.setEnabled(True)
            self.output.appendPlainText(
                i18n.tr(self.interface_language, "PowerShell 已啟動")
            )
            self.focus_input()
        self.output.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        if text:
            self.output.insertPlainText(text)
        self.output.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def _poll_output(self) -> None:
        self.process.waitForReadyRead(0)
        if self.process.bytesAvailable():
            self._read_output()

    def _process_finished(self, *_: object) -> None:
        self.output_timer.stop()
        self.ready = False
        self.status.setText(i18n.tr(self.interface_language, "已關閉"))
        self.input.setEnabled(False)

    def _process_error(self, error: QtCore.QProcess.ProcessError) -> None:
        if error == QtCore.QProcess.ProcessError.FailedToStart:
            self.output.appendPlainText(self.process.errorString())
            self.status.setText(i18n.tr(self.interface_language, "無法啟動"))

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self.input and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == QtCore.Qt.Key.Key_Up and self.history:
                self.history_index = max(0, self.history_index - 1)
                self.input.setText(self.history[self.history_index])
                return True
            if event.key() == QtCore.Qt.Key.Key_Down and self.history:
                self.history_index = min(len(self.history), self.history_index + 1)
                self.input.setText(
                    self.history[self.history_index]
                    if self.history_index < len(self.history)
                    else ""
                )
                return True
        return super().eventFilter(watched, event)

    def set_ui_font_size(self, point_size: int) -> None:
        terminal_font = self.output.font()
        terminal_font.setPointSize(max(8, point_size + 1))
        self.output.setFont(terminal_font)
        input_font = self.input.font()
        input_font.setPointSize(max(11, point_size + 3))
        self.prompt.setFont(input_font)
        self.input.setFont(input_font)
        self.input.setMinimumHeight(QtGui.QFontMetrics(input_font).height() + 12)


class SearchPanel(QtWidgets.QWidget):
    resultActivated = QtCore.Signal(str, int)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        interface_language: str = "zh_TW",
    ) -> None:
        super().__init__(parent)
        language = i18n.normalize_language(interface_language)
        self.query = QtWidgets.QLineEdit()
        self.query.setPlaceholderText(i18n.tr(language, "在目前資料夾中搜尋"))
        self.button = QtWidgets.QPushButton(i18n.tr(language, "搜尋"))
        self.case_box = QtWidgets.QCheckBox(i18n.tr(language, "區分大小寫"))
        self.regex_box = QtWidgets.QCheckBox(i18n.tr(language, "正規表示式"))
        self.results = QtWidgets.QTreeWidget()
        self.results.setHeaderLabels(
            [i18n.tr(language, "檔案"), i18n.tr(language, "行"), i18n.tr(language, "內容")]
        )
        self.results.itemDoubleClicked.connect(self._emit_result)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.query, 1)
        row.addWidget(self.case_box)
        row.addWidget(self.regex_box)
        row.addWidget(self.button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(row)
        layout.addWidget(self.results, 1)

    def _emit_result(self, item: QtWidgets.QTreeWidgetItem) -> None:
        path = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        line = item.data(1, QtCore.Qt.ItemDataRole.UserRole) or 1
        if path:
            self.resultActivated.emit(path, int(line))


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self.setWindowTitle(parent.t("設定"))
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(8, 36)
        self.font_size.setValue(parent.editor_font_size)
        self.wrap = QtWidgets.QCheckBox(parent.t("自動換行"))
        self.wrap.setChecked(parent.word_wrap)
        self.auto_save = QtWidgets.QCheckBox(parent.t("自動儲存"))
        self.auto_save.setChecked(parent.auto_save_enabled)
        self.auto_save_delay = QtWidgets.QDoubleSpinBox()
        self.auto_save_delay.setDecimals(1)
        self.auto_save_delay.setRange(0.1, 30.0)
        self.auto_save_delay.setSingleStep(0.1)
        self.auto_save_delay.setValue(parent.auto_save_delay_ms / 1000)
        self.auto_save_delay.setEnabled(self.auto_save.isChecked())
        self.auto_save.toggled.connect(self.auto_save_delay.setEnabled)
        self.syntax_contrast_sliders: dict[str, QtWidgets.QSlider] = {}
        self.interface_language = QtWidgets.QComboBox()
        self.interface_language.addItem("中文", "zh_TW")
        self.interface_language.addItem("English", "en")
        selected = self.interface_language.findData(parent.interface_language)
        self.interface_language.setCurrentIndex(max(0, selected))

        form = QtWidgets.QFormLayout()
        form.addRow(parent.t("介面與程式碼大小"), self.font_size)
        form.addRow("", self.wrap)
        form.addRow("", self.auto_save)
        form.addRow(parent.t("自動儲存延遲（秒）"), self.auto_save_delay)
        for name, label_text in SYNTAX_CONTRAST_OPTIONS:
            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(0, 200)
            slider.setSingleStep(1)
            slider.setPageStep(10)
            slider.setValue(parent.syntax_contrast[name])
            value_label = QtWidgets.QLabel(f"{slider.value()}%")
            value_label.setMinimumWidth(42)
            value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            slider.valueChanged.connect(
                lambda value, output=value_label: output.setText(f"{value}%")
            )
            slider.valueChanged.connect(self._preview_syntax_contrast)
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(slider, 1)
            row_layout.addWidget(value_label)
            self.syntax_contrast_sliders[name] = slider
            form.addRow(parent.t(label_text), row)
        form.addRow(parent.t("介面語言"), self.interface_language)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.rejected.connect(
            lambda: parent._apply_syntax_contrast(parent.syntax_contrast)
        )

    def syntax_contrast_values(self) -> dict[str, int]:
        return {
            name: slider.value()
            for name, slider in self.syntax_contrast_sliders.items()
        }

    def _preview_syntax_contrast(self, _: int) -> None:
        parent = self.parent()
        if isinstance(parent, MainWindow):
            parent._apply_syntax_contrast(self.syntax_contrast_values())


class GraphWorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(int, str, str, object)


class GraphWorker(QtCore.QRunnable):
    def __init__(self, request_id: int, path: str, title: str, code: str) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.request_id = request_id
        self.path = path
        self.title = title
        self.code = code
        self.signals = GraphWorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:
        graph = svc.build_code_graph(self.path, self.code)
        self.signals.finished.emit(self.request_id, self.path, self.title, graph)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        start_dir: str | None = None,
        interface_language: str | None = None,
    ) -> None:
        super().__init__()
        self.settings = QtCore.QSettings("PyFlow", "PyFlow IDE")
        self.interface_language = i18n.normalize_language(
            interface_language
            or self.settings.value("interface_language", "zh_TW")
        )
        self.setWindowTitle(self.t("PyFlow IDE - 中文版"))
        self.resize(1280, 820)

        self.current_dir = start_dir or str(Path.home())
        self.path_to_tab: dict[str, int] = {}
        self.encoding_by_path: dict[str, str] = {}
        self.file_signatures: dict[str, tuple[int, int, int] | None] = {}
        self.pending_auto_save_paths: set[str] = set()
        self.reloading_paths: set[str] = set()
        self.process: QtCore.QProcess | None = None
        self.process_stopping = False
        self.running_path: str | None = None
        self.graph_request_id = 0
        self.graph_workers: dict[int, GraphWorker] = {}
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self.editor_font_size = 11
        self.ui_font_size = 9
        self.word_wrap = False
        self.auto_save_enabled = self.settings.value(
            "auto_save_enabled", False, type=bool
        )
        self.auto_save_delay_ms = max(
            100,
            min(
                30_000,
                self.settings.value("auto_save_delay_ms", 1000, type=int),
            ),
        )
        self.syntax_contrast = {
            name: max(
                0,
                min(
                    200,
                    self.settings.value(
                        f"syntax_contrast/{name}", 100, type=int
                    ),
                ),
            )
            for name, _ in SYNTAX_CONTRAST_OPTIONS
        }

        self._build_ui()
        self._build_actions()
        self._build_menus()
        self.auto_save_timer = QtCore.QTimer(self)
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.timeout.connect(self._perform_auto_save)
        self.file_sync_timer = QtCore.QTimer(self)
        self.file_sync_timer.setInterval(750)
        self.file_sync_timer.timeout.connect(self._check_external_changes)
        self.file_sync_timer.start()
        QtWidgets.QApplication.instance().installEventFilter(self)
        self.open_folder(self.current_dir)
        self.statusBar().showMessage(
            self.t("就緒  |  Ctrl + 滑鼠滾輪可縮放全部介面")
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.file_sync_timer.stop()
        if self.auto_save_enabled:
            self._perform_auto_save()
        self.terminal_panel.stop()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().closeEvent(event)

    def t(self, text: str, **values: object) -> str:
        return i18n.tr(self.interface_language, text, **values)

    def _build_ui(self) -> None:
        self.setStyleSheet(CLAUDE_STYLE)

        self.model = QtWidgets.QFileSystemModel(self)
        self.model.setFilter(
            QtCore.QDir.Filter.AllDirs
            | QtCore.QDir.Filter.Files
            | QtCore.QDir.Filter.NoDotAndDotDot
        )
        self.model.setNameFilters(["*"])
        self.model.setNameFilterDisables(False)
        self.model.setHeaderData(0, QtCore.Qt.Orientation.Horizontal, self.t("名稱"))

        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.clicked.connect(self._tree_clicked)
        self.tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_file_context_menu)

        self.file_dock = QtWidgets.QDockWidget(self.t("檔案"), self)
        self.file_dock.setWidget(self.tree)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.file_dock)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._current_tab_changed)
        self.setCentralWidget(self.tabs)

        self.outline = QtWidgets.QTreeWidget()
        self.outline.setHeaderLabels([self.t("符號"), self.t("行")])
        self.outline.itemDoubleClicked.connect(self._outline_clicked)
        self.outline_dock = QtWidgets.QDockWidget(self.t("大綱"), self)
        self.outline_dock.setWidget(self.outline)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.outline_dock)
        self.outline_dock.hide()

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        output_font = QtGui.QFont("Cascadia Mono")
        if not QtGui.QFontInfo(output_font).fixedPitch():
            output_font = QtGui.QFont("Consolas")
        output_font.setPointSize(10)
        self.output.setFont(output_font)
        self.output_dock = QtWidgets.QDockWidget(self.t("輸出"), self)
        self.output_dock.setWidget(self.output)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)
        self.output_dock.hide()

        self.terminal_panel = PowerShellPanel(
            interface_language=self.interface_language
        )
        self.terminal_panel.closeRequested.connect(self.close_terminal)
        self.terminal_dock = QtWidgets.QDockWidget("PowerShell", self)
        self.terminal_dock.setWidget(self.terminal_panel)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock
        )
        self.tabifyDockWidget(self.output_dock, self.terminal_dock)
        self.terminal_dock.hide()

        self.graph_panel = NodeGraphPanel(interface_language=self.interface_language)
        self.graph_view = self.graph_panel.graph_view
        self.graph_panel.nodeActivated.connect(self._graph_node_clicked)
        self.graph_dock = QtWidgets.QDockWidget(self.t("節點圖"), self)
        self.graph_dock.setWidget(self.graph_panel)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.graph_dock)
        self.tabifyDockWidget(self.output_dock, self.graph_dock)
        self.graph_dock.hide()
        self.graph_dock.visibilityChanged.connect(self._graph_visibility_changed)

        self.search_panel = SearchPanel(interface_language=self.interface_language)
        self.search_panel.button.clicked.connect(self.run_search)
        self.search_panel.query.returnPressed.connect(self.run_search)
        self.search_panel.resultActivated.connect(self.open_file_at_line)
        search_dock = QtWidgets.QDockWidget(self.t("搜尋"), self)
        search_dock.setWidget(self.search_panel)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, search_dock)
        self.tabifyDockWidget(self.output_dock, search_dock)
        search_dock.hide()
        self.search_dock = search_dock

    def _build_actions(self) -> None:
        toolbar = self.addToolBar("Main")
        self.toolbar = toolbar
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        def add_action(
            text: str,
            slot,
            shortcut: str | None = None,
            icon: QtWidgets.QStyle.StandardPixmap | None = None,
            tooltip: str | None = None,
        ) -> QtGui.QAction:
            action = QtGui.QAction(text, self)
            if icon is not None:
                action.setIcon(self.style().standardIcon(icon))
            if shortcut:
                action.setShortcut(QtGui.QKeySequence(shortcut))
            if tooltip:
                action.setToolTip(tooltip)
                action.setStatusTip(tooltip)
            action.triggered.connect(slot)
            toolbar.addAction(action)
            return action

        add_action(self.t("開資料夾"), self.choose_folder, "Ctrl+Shift+O", QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon)
        add_action(self.t("開檔案"), self.choose_file, "Ctrl+O", QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
        self.new_file_action = add_action(
            self.t("新檔案"), self.create_new_file, "Ctrl+N", QtWidgets.QStyle.StandardPixmap.SP_FileIcon
        )
        self.new_folder_action = add_action(
            self.t("新資料夾"), self.create_new_folder, "Ctrl+Shift+N", QtWidgets.QStyle.StandardPixmap.SP_DirIcon
        )
        toolbar.addSeparator()
        add_action(self.t("儲存"), self.save_current, "Ctrl+S", QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton)
        add_action(self.t("另存"), self.save_current_as, "Ctrl+Shift+S")
        toolbar.addSeparator()
        self.run_action = add_action(
            self.t("執行"), self.run_current, "F5", QtWidgets.QStyle.StandardPixmap.SP_MediaPlay
        )
        self.stop_action = add_action(
            self.t("停止"), self.stop_current, "Shift+F5", QtWidgets.QStyle.StandardPixmap.SP_MediaStop
        )
        self.stop_action.setEnabled(False)
        add_action(self.t("分析"), lambda: self.analyze_current(force=True), "Ctrl+R")
        add_action(self.t("節點"), self.show_node_graph, "Ctrl+Shift+G", QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon)
        add_action(self.t("格式化"), self.format_current, "Alt+Shift+F")
        toolbar.addSeparator()
        add_action(self.t("搜尋"), self.show_search, "Ctrl+Shift+F", QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView)
        add_action(self.t("設定"), self.open_settings, "Ctrl+,", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView)

        self.terminal_action = QtGui.QAction("PowerShell", self)
        self.terminal_action.setShortcut(QtGui.QKeySequence("Ctrl+`"))
        self.terminal_action.setShortcutContext(
            QtCore.Qt.ShortcutContext.ApplicationShortcut
        )
        self.terminal_action.triggered.connect(self.show_terminal)
        self.addAction(self.terminal_action)

        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.rename_action = QtGui.QAction(self.t("重新命名"), self)
        self.rename_action.setShortcut(QtGui.QKeySequence("F2"))
        self.rename_action.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.rename_action.triggered.connect(self.rename_selected_path)
        self.tree.addAction(self.rename_action)
        self.delete_action = QtGui.QAction(self.t("刪除"), self)
        self.delete_action.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete))
        self.delete_action.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_action.triggered.connect(self.delete_selected_path)
        self.tree.addAction(self.delete_action)

        zoom_out = add_action("A-", self.zoom_out, tooltip=self.t("縮小全部介面 (Ctrl+-)"))
        zoom_out.setShortcuts([QtGui.QKeySequence.StandardKey.ZoomOut])
        self.zoom_label = QtWidgets.QLabel()
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setToolTip(self.t("全部介面縮放比例；點一下可重設"))
        self.zoom_label.mousePressEvent = lambda _: self.reset_zoom()
        toolbar.addWidget(self.zoom_label)
        zoom_in = add_action("A+", self.zoom_in, tooltip=self.t("放大全部介面 (Ctrl++)"))
        zoom_in.setShortcuts([QtGui.QKeySequence.StandardKey.ZoomIn, QtGui.QKeySequence("Ctrl+=")])

        reset_zoom = QtGui.QAction(self)
        reset_zoom.setShortcut(QtGui.QKeySequence("Ctrl+0"))
        reset_zoom.triggered.connect(self.reset_zoom)
        self.addAction(reset_zoom)
        self._update_zoom_label()

    def _build_menus(self) -> None:
        windows_menu = self.menuBar().addMenu(self.t("視窗 (Windows)"))
        for dock, label in (
            (self.file_dock, self.t("檔案")),
            (self.outline_dock, self.t("大綱")),
            (self.output_dock, self.t("輸出")),
            (self.terminal_dock, "PowerShell"),
            (self.graph_dock, self.t("節點圖")),
            (self.search_dock, self.t("搜尋")),
        ):
            action = dock.toggleViewAction()
            action.setText(label)
            windows_menu.addAction(action)
        windows_menu.addSeparator()
        demo_menu = windows_menu.addMenu(self.t("節點 Demo"))
        for language, (label, _) in NODE_DEMOS.items():
            action = demo_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, value=language: self.show_node_demo(value)
            )
        windows_menu.addSeparator()
        editor_only = windows_menu.addAction(self.t("只顯示編輯器"))
        editor_only.triggered.connect(self._hide_all_panels)
        reset_layout = windows_menu.addAction(self.t("重設視窗"))
        reset_layout.triggered.connect(self._reset_window_layout)

    def _hide_all_panels(self) -> None:
        for dock in (
            self.file_dock,
            self.outline_dock,
            self.output_dock,
            self.terminal_dock,
            self.graph_dock,
            self.search_dock,
        ):
            dock.hide()

    def _reset_window_layout(self) -> None:
        self.file_dock.show()
        self.outline_dock.hide()
        self.output_dock.hide()
        self.terminal_dock.hide()
        self.graph_dock.hide()
        self.search_dock.hide()

    def active_editor(self) -> CodeEditor | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def active_path(self) -> str | None:
        editor = self.active_editor()
        return editor.property("path") if editor else None

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if (
            event.type() == QtCore.QEvent.Type.KeyPress
            and event.key() == QtCore.Qt.Key.Key_QuoteLeft
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.show_terminal()
            return True
        if (
            event.type() == QtCore.QEvent.Type.Wheel
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            steps = int(event.angleDelta().y() / 120)
            if steps:
                self.zoom_by(steps)
            return True
        return super().eventFilter(watched, event)

    def selected_path(self) -> str | None:
        index = self.tree.currentIndex()
        path = self.model.filePath(index) if index.isValid() else ""
        return svc.normalize_path(path) if path else None

    def _target_directory(self) -> str:
        selected = self.selected_path()
        if not selected:
            return self.current_dir
        path = Path(selected)
        return str(path if path.is_dir() else path.parent)

    @staticmethod
    def _same_or_child(candidate: str, parent: str) -> bool:
        child_path = Path(candidate).resolve()
        parent_path = Path(parent).resolve()
        return child_path == parent_path or child_path.is_relative_to(parent_path)

    def _show_file_context_menu(self, position: QtCore.QPoint) -> None:
        index = self.tree.indexAt(position)
        if index.isValid():
            self.tree.setCurrentIndex(index)
        selected = self.selected_path()
        can_change = bool(selected and selected != svc.normalize_path(self.current_dir))
        self.rename_action.setEnabled(can_change)
        self.delete_action.setEnabled(can_change)

        menu = QtWidgets.QMenu(self.tree)
        menu.addAction(self.new_file_action)
        menu.addAction(self.new_folder_action)
        menu.addSeparator()
        menu.addAction(self.rename_action)
        menu.addAction(self.delete_action)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def create_new_file(self) -> None:
        directory = self._target_directory()
        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            self.t("新增檔案"),
            self.t("建立於：{directory}\n\n檔案名稱：", directory=directory),
        )
        if not accepted:
            return
        result = svc.create_file(directory, name.strip(), self.current_dir)
        if not result.ok:
            QtWidgets.QMessageBox.critical(
                self, self.t("新增檔案失敗"), result.error or self.t("未知錯誤")
            )
            return
        path = str(Path(directory) / name.strip())
        self.open_file(path)
        self.statusBar().showMessage(self.t("已新增檔案：{path}", path=path))

    def create_new_folder(self) -> None:
        directory = self._target_directory()
        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            self.t("新增資料夾"),
            self.t("建立於：{directory}\n\n資料夾名稱：", directory=directory),
        )
        if not accepted:
            return
        result = svc.create_directory(directory, name.strip(), self.current_dir)
        if not result.ok:
            QtWidgets.QMessageBox.critical(
                self, self.t("新增資料夾失敗"), result.error or self.t("未知錯誤")
            )
            return
        path = str(Path(directory) / name.strip())
        parent_index = self.model.index(directory)
        self.tree.expand(parent_index)
        self.statusBar().showMessage(self.t("已新增資料夾：{path}", path=path))

    def rename_selected_path(self) -> None:
        source = self.selected_path()
        if not source or source == svc.normalize_path(self.current_dir):
            return
        if self.running_path and self._same_or_child(self.running_path, source):
            QtWidgets.QMessageBox.warning(
                self, self.t("無法重新命名"), self.t("請先停止正在執行的程式。")
            )
            return
        new_name, accepted = QtWidgets.QInputDialog.getText(
            self, self.t("重新命名"), self.t("新名稱："), text=Path(source).name
        )
        if not accepted or new_name.strip() == Path(source).name:
            return
        result, target = svc.rename_path(source, new_name.strip(), self.current_dir)
        if not result.ok or not target:
            QtWidgets.QMessageBox.critical(
                self, self.t("重新命名失敗"), result.error or self.t("未知錯誤")
            )
            return

        for index in range(self.tabs.count()):
            editor = self.tabs.widget(index)
            if not isinstance(editor, CodeEditor):
                continue
            old_editor_path = str(editor.property("path"))
            if not self._same_or_child(old_editor_path, source):
                continue
            relative = Path(old_editor_path).resolve().relative_to(Path(source).resolve())
            new_editor_path = str(Path(target) / relative)
            old_encoding = self.encoding_by_path.pop(old_editor_path, "utf-8")
            self.encoding_by_path[new_editor_path] = old_encoding
            was_pending = old_editor_path in self.pending_auto_save_paths
            self.pending_auto_save_paths.discard(old_editor_path)
            if was_pending:
                self.pending_auto_save_paths.add(new_editor_path)
            self.file_signatures.pop(old_editor_path, None)
            self.file_signatures[new_editor_path] = self._file_signature(new_editor_path)
            editor.setProperty("path", new_editor_path)
            self.tabs.setTabText(
                index,
                ("*" if editor.document().isModified() else "") + Path(new_editor_path).name,
            )
        self._refresh_tab_map()
        self.statusBar().showMessage(
            self.t(
                "已重新命名：{source} → {target}",
                source=Path(source).name,
                target=Path(target).name,
            )
        )

    def delete_selected_path(self) -> None:
        target = self.selected_path()
        if not target or target == svc.normalize_path(self.current_dir):
            return
        if self.running_path and self._same_or_child(self.running_path, target):
            QtWidgets.QMessageBox.warning(
                self, self.t("無法刪除"), self.t("請先停止正在執行的程式。")
            )
            return

        affected_editors = [
            self.tabs.widget(index)
            for index in range(self.tabs.count())
            if isinstance(self.tabs.widget(index), CodeEditor)
            and self._same_or_child(str(self.tabs.widget(index).property("path")), target)
        ]
        modified = sum(editor.document().isModified() for editor in affected_editors)
        extra = (
            "\n" + self.t("其中有 {count} 個尚未儲存的檔案。", count=modified)
            if modified
            else ""
        )
        answer = QtWidgets.QMessageBox.warning(
            self,
            self.t("確認刪除"),
            self.t(
                "確定要刪除「{name}」嗎？\n此動作無法復原。{extra}",
                name=Path(target).name,
                extra=extra,
            ),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        result = svc.delete_path(target, self.current_dir)
        if not result.ok:
            QtWidgets.QMessageBox.critical(
                self, self.t("刪除失敗"), result.error or self.t("未知錯誤")
            )
            return
        for index in reversed(range(self.tabs.count())):
            editor = self.tabs.widget(index)
            if isinstance(editor, CodeEditor) and self._same_or_child(
                str(editor.property("path")), target
            ):
                editor_path = str(editor.property("path"))
                self.encoding_by_path.pop(editor_path, None)
                self.file_signatures.pop(editor_path, None)
                self.pending_auto_save_paths.discard(editor_path)
                self.tabs.removeTab(index)
        self._refresh_tab_map()
        self.statusBar().showMessage(self.t("已刪除：{path}", path=target))

    def _tree_clicked(self, index: QtCore.QModelIndex) -> None:
        path = self.model.filePath(index)
        if not path:
            return
        if self.model.isDir(index):
            if self.tree.isExpanded(index):
                self.tree.collapse(index)
            else:
                self.tree.expand(index)
            return
        self.open_file(path)

    def choose_folder(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.t("開啟資料夾"), self.current_dir
        )
        if directory:
            self.open_folder(directory)

    def open_folder(self, directory: str) -> None:
        directory = svc.normalize_path(directory)
        self.current_dir = directory
        root = self.model.setRootPath(directory)
        self.tree.setRootIndex(root)
        for col in range(1, self.model.columnCount()):
            self.tree.hideColumn(col)
        self.statusBar().showMessage(
            self.t("目前資料夾：{directory}", directory=directory)
        )

    def choose_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.t("開啟檔案"), self.current_dir
        )
        if path:
            self.open_file(path)

    def open_file_at_line(self, path: str, line: int) -> None:
        self.open_file(path)
        editor = self.active_editor()
        if editor:
            editor.goto_line(line)

    def open_file(self, path: str) -> None:
        path = svc.normalize_path(path)
        if Path(path).is_dir():
            self.open_folder(path)
            return
        if not svc.is_likely_text(path):
            answer = QtWidgets.QMessageBox.question(
                self,
                self.t("可能是二進位檔案"),
                self.t("這個檔案可能不是文字格式，仍要以文字方式開啟嗎？"),
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        if path in self.path_to_tab:
            self.tabs.setCurrentIndex(self.path_to_tab[path])
            return

        result = svc.read_text(path)
        if result.error:
            QtWidgets.QMessageBox.critical(self, self.t("開啟失敗"), result.error)
            return

        editor = CodeEditor()
        editor.set_interface_language(self.interface_language)
        editor.setPlainText(result.content)
        editor.document().setModified(False)
        editor.set_language(svc.language_for_path(path))
        editor.set_editor_font_size(self.editor_font_size)
        editor.set_syntax_contrast(self.syntax_contrast)
        editor.setLineWrapMode(
            QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth
            if self.word_wrap
            else QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        editor.setProperty("path", path)
        editor.document().modificationChanged.connect(
            lambda modified, e=editor: self._set_tab_dirty(str(e.property("path")), modified)
        )
        editor.textChanged.connect(lambda e=editor: self._editor_text_changed(e))
        editor.zoomRequested.connect(self.zoom_by)

        idx = self.tabs.addTab(editor, Path(path).name)
        self.tabs.setCurrentIndex(idx)
        self.path_to_tab[path] = idx
        self.encoding_by_path[path] = result.encoding
        self.file_signatures[path] = self._file_signature(path)
        self.statusBar().showMessage(
            self.t("已開啟：{path}（{encoding}）", path=path, encoding=result.encoding)
        )
        self.analyze_current()

    @staticmethod
    def _file_signature(path: str) -> tuple[int, int, int] | None:
        try:
            stat = Path(path).stat()
            return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size
        except OSError:
            return None

    def _editor_text_changed(self, editor: CodeEditor) -> None:
        path = str(editor.property("path") or "")
        if not path or path in self.reloading_paths or not self.auto_save_enabled:
            return
        self.pending_auto_save_paths.add(path)
        self.auto_save_timer.start(self.auto_save_delay_ms)

    def _perform_auto_save(self) -> None:
        pending = list(self.pending_auto_save_paths)
        self.pending_auto_save_paths.clear()
        for path in pending:
            index = self.path_to_tab.get(path)
            editor = self.tabs.widget(index) if index is not None else None
            if not isinstance(editor, CodeEditor) or not editor.document().isModified():
                continue
            if self._file_signature(path) != self.file_signatures.get(path):
                self._sync_external_change(path)
                continue
            self._save_editor(editor, automatic=True)

    def _check_external_changes(self) -> None:
        for path in list(self.path_to_tab):
            if self._file_signature(path) != self.file_signatures.get(path):
                self._sync_external_change(path)

    def _sync_external_change(self, path: str) -> bool:
        current_signature = self._file_signature(path)
        if current_signature == self.file_signatures.get(path):
            return False
        self.file_signatures[path] = current_signature

        index = self.path_to_tab.get(path)
        editor = self.tabs.widget(index) if index is not None else None
        if not isinstance(editor, CodeEditor):
            return True
        if current_signature is None:
            self.pending_auto_save_paths.discard(path)
            editor.document().setModified(True)
            self.statusBar().showMessage(
                self.t("檔案已由外部刪除：{path}", path=path)
            )
            return True

        result = svc.read_text(path)
        if result.error:
            self.statusBar().showMessage(result.error)
            return True
        if result.content == editor.toPlainText():
            self.encoding_by_path[path] = result.encoding
            editor.document().setModified(False)
            self.pending_auto_save_paths.discard(path)
            return True

        if editor.document().isModified():
            dialog = QtWidgets.QMessageBox(self)
            dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            dialog.setWindowTitle(self.t("外部檔案變更"))
            dialog.setText(
                self.t(
                    "外部程式已修改 {name}，但 IDE 內也有尚未儲存的內容。",
                    name=Path(path).name,
                )
            )
            reload_button = dialog.addButton(
                self.t("重新載入外部版本"),
                QtWidgets.QMessageBox.ButtonRole.AcceptRole,
            )
            keep_button = dialog.addButton(
                self.t("保留 IDE 內容"),
                QtWidgets.QMessageBox.ButtonRole.RejectRole,
            )
            dialog.setDefaultButton(reload_button)
            dialog.exec()
            if dialog.clickedButton() is not reload_button:
                self.pending_auto_save_paths.discard(path)
                self.statusBar().showMessage(
                    self.t("已保留 IDE 內的內容：{path}", path=path)
                )
                return True

        self._reload_editor_from_disk(editor, path, result)
        return True

    def _reload_editor_from_disk(
        self,
        editor: CodeEditor,
        path: str,
        result: svc.ReadResult,
    ) -> None:
        cursor = editor.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()
        vertical_scroll = editor.verticalScrollBar().value()
        horizontal_scroll = editor.horizontalScrollBar().value()

        self.reloading_paths.add(path)
        try:
            editor.setPlainText(result.content)
            editor.document().setModified(False)
        finally:
            self.reloading_paths.discard(path)

        maximum = max(0, len(result.content))
        restored = editor.textCursor()
        restored.setPosition(min(anchor, maximum))
        restored.setPosition(
            min(position, maximum), QtGui.QTextCursor.MoveMode.KeepAnchor
        )
        editor.setTextCursor(restored)
        editor.verticalScrollBar().setValue(vertical_scroll)
        editor.horizontalScrollBar().setValue(horizontal_scroll)
        self.encoding_by_path[path] = result.encoding
        self.file_signatures[path] = self._file_signature(path)
        self.pending_auto_save_paths.discard(path)
        self._set_tab_dirty(path, False)
        if editor is self.active_editor():
            self.analyze_current()
        self.statusBar().showMessage(
            self.t("已同步外部變更：{path}", path=path)
        )

    def _mark_dirty(self, path: str) -> None:
        index = self.path_to_tab.get(path)
        editor = self.tabs.widget(index) if index is not None else None
        if isinstance(editor, CodeEditor):
            editor.document().setModified(True)
        else:
            self._set_tab_dirty(path, True)

    def _set_tab_dirty(self, path: str, dirty: bool) -> None:
        idx = self.path_to_tab.get(path)
        if idx is None:
            return
        title = Path(path).name
        self.tabs.setTabText(idx, ("*" if dirty else "") + title)

    def _current_tab_changed(self, _: int) -> None:
        self.analyze_current()

    def _refresh_tab_map(self) -> None:
        self.path_to_tab.clear()
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            path = widget.property("path") if widget else None
            if path:
                self.path_to_tab[path] = i

    def close_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, CodeEditor) and widget.document().isModified():
            answer = QtWidgets.QMessageBox.question(
                self,
                self.t("尚未儲存的變更"),
                self.t(
                    "要儲存 {name} 的變更嗎？",
                    name=Path(widget.property("path")).name,
                ),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
                | QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Cancel:
                return
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                self.tabs.setCurrentIndex(index)
                if not self.save_current():
                    return
        path = str(widget.property("path") or "") if widget else ""
        self.tabs.removeTab(index)
        if path:
            self.encoding_by_path.pop(path, None)
            self.file_signatures.pop(path, None)
            self.pending_auto_save_paths.discard(path)
        self._refresh_tab_map()

    def save_current(self) -> bool:
        editor = self.active_editor()
        if not editor:
            return False
        return self._save_editor(editor)

    def _save_editor(self, editor: CodeEditor, automatic: bool = False) -> bool:
        path = str(editor.property("path") or "")
        if not path:
            return False
        encoding = self.encoding_by_path.get(path, "utf-8")
        result = svc.write_text(path, editor.toPlainText(), encoding)
        if not result.ok:
            QtWidgets.QMessageBox.critical(
                self, self.t("儲存失敗"), result.error or self.t("未知錯誤")
            )
            return False
        editor.document().setModified(False)
        self.file_signatures[path] = self._file_signature(path)
        self.pending_auto_save_paths.discard(path)
        idx = self.path_to_tab.get(path)
        if idx is not None:
            self.tabs.setTabText(idx, Path(path).name)
        message = "已自動儲存：{path}" if automatic else "已儲存：{path}"
        self.statusBar().showMessage(self.t(message, path=path))
        return True

    def save_current_as(self) -> bool:
        editor = self.active_editor()
        if not editor:
            return False
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self.t("另存新檔"), self.current_dir
        )
        if not path:
            return False
        old_path = self.active_path()
        new_path = svc.normalize_path(path)
        editor.setProperty("path", new_path)
        if old_path:
            self.path_to_tab.pop(old_path, None)
            old_encoding = self.encoding_by_path.pop(old_path, "utf-8")
            self.encoding_by_path[new_path] = old_encoding
            self.file_signatures.pop(old_path, None)
            self.pending_auto_save_paths.discard(old_path)
        self._refresh_tab_map()
        return self.save_current()

    def analyze_current(self, force: bool = False) -> None:
        editor = self.active_editor()
        path = self.active_path()
        self.outline.clear()
        if not editor or not path:
            return
        code = editor.toPlainText()
        language = svc.language_for_path(path)
        if self.graph_dock.isVisible():
            if language in GRAPH_LANGUAGES:
                self._request_node_graph(
                    path, code, self.t("呼叫流程：{name}", name=Path(path).name)
                )
            else:
                self._show_unsupported_graph(path, language)
        if len(code) > 400_000 and not force:
            self.statusBar().showMessage(
                self.t(
                    "大型檔案已開啟：{name}；需要大綱時請按「分析」",
                    name=Path(path).name,
                )
            )
            return
        result = svc.parse_source(path, code)
        if result.get("error"):
            self.output.appendPlainText(f"[{self.t('分析')}] {result['error']}")
        for definition in result.get("definitions") or []:
            label = str(definition.get("label") or definition.get("id") or "symbol")
            line = int(definition.get("line") or 0)
            item = QtWidgets.QTreeWidgetItem([label, str(line or "")])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, line)
            self.outline.addTopLevelItem(item)
            for method in definition.get("methods") or []:
                m_label = str(method.get("label") or method.get("name") or "method")
                m_line = int(method.get("line") or line or 0)
                child = QtWidgets.QTreeWidgetItem([m_label, str(m_line or "")])
                child.setData(0, QtCore.Qt.ItemDataRole.UserRole, m_line)
                item.addChild(child)
        self.statusBar().showMessage(
            self.t(
                "已分析 {name}：{count} 個符號",
                name=Path(path).name,
                count=len(result.get("definitions") or []),
            )
        )

    def show_node_graph(self) -> None:
        editor = self.active_editor()
        path = self.active_path()
        if not editor or not path:
            self.show_node_demo()
            return
        blocker = QtCore.QSignalBlocker(self.graph_dock)
        self.graph_dock.show()
        self.graph_dock.raise_()
        del blocker
        self.resizeDocks([self.graph_dock], [360], QtCore.Qt.Orientation.Vertical)
        language = svc.language_for_path(path)
        if language not in GRAPH_LANGUAGES:
            self._show_unsupported_graph(path, language)
            return
        self._request_node_graph(
            path,
            editor.toPlainText(),
            self.t("呼叫流程：{name}", name=Path(path).name),
        )

    def show_node_demo(self, language: str = "python") -> None:
        label, filename = NODE_DEMOS.get(language, NODE_DEMOS["python"])
        demo = Path(__file__).resolve().parent / "samples" / filename
        if not demo.exists():
            QtWidgets.QMessageBox.warning(self, self.t("找不到 Demo"), str(demo))
            return
        self.open_file(str(demo))
        editor = self.active_editor()
        if not editor:
            return
        blocker = QtCore.QSignalBlocker(self.graph_dock)
        self.graph_dock.show()
        self.graph_dock.raise_()
        del blocker
        self.resizeDocks([self.graph_dock], [380], QtCore.Qt.Orientation.Vertical)
        self._request_node_graph(
            str(demo),
            editor.toPlainText(),
            self.t("節點 Demo：{language} 資料處理流程", language=label),
        )

    def _graph_visibility_changed(self, visible: bool) -> None:
        if not visible:
            return
        editor = self.active_editor()
        path = self.active_path()
        if not editor or not path:
            return
        language = svc.language_for_path(path)
        if language in GRAPH_LANGUAGES:
            self._request_node_graph(
                path,
                editor.toPlainText(),
                self.t("呼叫流程：{name}", name=Path(path).name),
            )
        else:
            self._show_unsupported_graph(path, language)

    def _show_unsupported_graph(self, path: str, language: str) -> None:
        self.graph_request_id += 1
        language_name = (
            language
            or Path(path).suffix.lstrip(".")
            or self.t("此檔案格式")
        )
        self.graph_panel.set_graph(
            {
                "nodes": [],
                "edges": [],
                "error": self.t(
                    "{language} 目前沒有節點呼叫圖。支援 Python、Rust、Go、C、C++、ZyenLang。",
                    language=language_name,
                ),
            },
            self.t("呼叫流程：{name}", name=Path(path).name),
        )
        self.statusBar().showMessage(
            self.t("節點圖支援 Python、Rust、Go、C、C++、ZyenLang")
        )

    def _request_node_graph(self, path: str, code: str, title: str) -> None:
        self.graph_request_id += 1
        request_id = self.graph_request_id
        self.graph_panel.set_graph(
            {"nodes": [], "edges": [], "error": self.t("正在建立節點圖...")},
            title,
        )
        worker = GraphWorker(request_id, path, title, code)
        worker.signals.finished.connect(self._node_graph_ready)
        self.graph_workers[request_id] = worker
        self.thread_pool.start(worker)
        self.statusBar().showMessage(
            self.t("正在分析節點：{name}", name=Path(path).name)
        )

    def _node_graph_ready(
        self,
        request_id: int,
        path: str,
        title: str,
        graph: object,
    ) -> None:
        self.graph_workers.pop(request_id, None)
        if request_id != self.graph_request_id or not isinstance(graph, dict):
            return
        self.graph_panel.set_graph(graph, title)
        node_count = len(graph.get("nodes") or [])
        edge_count = len(graph.get("edges") or [])
        suffix = (
            f" ({self.t('已限制顯示數量')})" if graph.get("truncated") else ""
        )
        self.statusBar().showMessage(
            self.t(
                "節點圖：{name}，{nodes} 個節點、{edges} 條關係{suffix}",
                name=Path(path).name,
                nodes=node_count,
                edges=edge_count,
                suffix=suffix,
            )
        )

    def _graph_node_clicked(self, line: int) -> None:
        editor = self.active_editor()
        if editor and line:
            editor.goto_line(line)

    def _outline_clicked(self, item: QtWidgets.QTreeWidgetItem) -> None:
        line = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        editor = self.active_editor()
        if editor and line:
            editor.goto_line(int(line))

    def format_current(self) -> None:
        editor = self.active_editor()
        path = self.active_path()
        if not editor or not path:
            return
        result = svc.format_source(path, editor.toPlainText())
        if result.get("error"):
            self.output.appendPlainText(
                f"[{self.t('格式化')}:{result.get('tool', '')}] {result['error']}"
            )
            return
        formatted = result.get("formatted")
        if formatted is not None and formatted != editor.toPlainText():
            cursor = editor.textCursor()
            editor.setPlainText(formatted)
            editor.setTextCursor(cursor)
            self._mark_dirty(path)
        self.statusBar().showMessage(
            self.t(
                "已使用 {tool} 完成格式化",
                tool=result.get("tool") or self.t("格式化工具"),
            )
        )

    def run_current(self) -> None:
        path = self.active_path()
        if not path:
            return
        if svc.language_for_path(path) != "python":
            self.output.appendPlainText(
                f"[{self.t('執行')}] {self.t('目前只支援直接執行 Python 檔案。')}"
            )
            return
        if self.process and self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            self.statusBar().showMessage(self.t("程式正在執行；請先按停止"))
            return
        if not self.save_current():
            return

        runtime = python_runtime_command()
        if runtime is None:
            QtWidgets.QMessageBox.warning(
                self,
                self.t("找不到 Python"),
                self.t(
                    "找不到可執行 Python。請安裝 Python 3，或用 PYFLOW_PYTHON 指定 python.exe。"
                ),
            )
            return
        program, runtime_args = runtime
        process_args = [*runtime_args, "-u", path]

        self.output.clear()
        self.output_dock.show()
        self.output.appendPlainText(
            "$ " + subprocess.list2cmdline([program, *process_args]) + "\n"
        )
        proc = QtCore.QProcess(self)
        proc.setWorkingDirectory(str(Path(path).parent))
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        proc.setProcessEnvironment(env)
        proc.readyReadStandardOutput.connect(lambda: self._append_process(proc, False))
        proc.readyReadStandardError.connect(lambda: self._append_process(proc, True))
        proc.finished.connect(
            lambda code, status, p=proc: self._process_finished(p, code, status)
        )
        self.process = proc
        self.running_path = path
        self.process_stopping = False
        self.run_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        proc.start(program, process_args)
        self.statusBar().showMessage(self.t("正在執行：{name}", name=Path(path).name))

    def stop_current(self) -> None:
        proc = self.process
        if not proc or proc.state() == QtCore.QProcess.ProcessState.NotRunning:
            self.run_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            return

        self.process_stopping = True
        self.stop_action.setEnabled(False)
        self.output.appendPlainText(f"\n[{self.t('執行')}] {self.t('正在停止...')}")
        self.statusBar().showMessage(self.t("正在停止程式..."))
        proc.terminate()
        QtCore.QTimer.singleShot(
            1500,
            lambda p=proc: p.kill()
            if p.state() != QtCore.QProcess.ProcessState.NotRunning
            else None,
        )

    def _process_finished(
        self,
        proc: QtCore.QProcess,
        code: int,
        _: QtCore.QProcess.ExitStatus,
    ) -> None:
        if proc is not self.process:
            return
        if self.process_stopping:
            self.output.appendPlainText(f"[{self.t('執行')}] {self.t('已停止')}")
            self.statusBar().showMessage(self.t("程式已停止"))
        else:
            self.output.appendPlainText(
                "\n" + self.t("回傳碼 {code}", code=code)
            )
            self.statusBar().showMessage(
                self.t("程式執行結束，回傳碼：{code}", code=code)
            )
        self.process = None
        self.running_path = None
        self.process_stopping = False
        self.run_action.setEnabled(True)
        self.stop_action.setEnabled(False)

    def _append_process(self, proc: QtCore.QProcess, stderr: bool) -> None:
        data = proc.readAllStandardError() if stderr else proc.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        self.output.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.output.insertPlainText(text)
        self.output.moveCursor(QtGui.QTextCursor.MoveOperation.End)

    def show_terminal(self) -> None:
        self.terminal_dock.show()
        self.terminal_dock.raise_()
        self.terminal_panel.start(self.current_dir)
        self.terminal_panel.focus_input()

    def close_terminal(self) -> None:
        self.terminal_panel.stop()
        self.terminal_dock.hide()

    def show_search(self) -> None:
        self.search_dock.show()
        self.search_panel.query.setFocus()

    def run_search(self) -> None:
        query = self.search_panel.query.text()
        self.search_panel.results.clear()
        if not query:
            return
        result = svc.search_in_directory(
            self.current_dir,
            query,
            case_sensitive=self.search_panel.case_box.isChecked(),
            use_regex=self.search_panel.regex_box.isChecked(),
        )
        if result.get("error"):
            self.output.appendPlainText(f"[{self.t('搜尋')}] {result['error']}")
            return
        for row in result.get("results", []):
            item = QtWidgets.QTreeWidgetItem(
                [os.path.relpath(row["file"], self.current_dir), str(row["line"]), row["text"]]
            )
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, row["file"])
            item.setData(1, QtCore.Qt.ItemDataRole.UserRole, row["line"])
            self.search_panel.results.addTopLevelItem(item)
        self.search_panel.results.resizeColumnToContents(0)
        self.statusBar().showMessage(
            self.t("搜尋完成：{count} 筆結果", count=result.get("total", 0))
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.editor_font_size = dialog.font_size.value()
        self.word_wrap = dialog.wrap.isChecked()
        self.auto_save_enabled = dialog.auto_save.isChecked()
        self.auto_save_delay_ms = round(dialog.auto_save_delay.value() * 1000)
        self.settings.setValue("auto_save_enabled", self.auto_save_enabled)
        self.settings.setValue("auto_save_delay_ms", self.auto_save_delay_ms)
        self.syntax_contrast = dialog.syntax_contrast_values()
        for name, value in self.syntax_contrast.items():
            self.settings.setValue(f"syntax_contrast/{name}", value)
        if self.auto_save_enabled:
            for index in range(self.tabs.count()):
                editor = self.tabs.widget(index)
                if isinstance(editor, CodeEditor) and editor.document().isModified():
                    path = str(editor.property("path") or "")
                    if path:
                        self.pending_auto_save_paths.add(path)
            if self.pending_auto_save_paths:
                self.auto_save_timer.start(self.auto_save_delay_ms)
        else:
            self.auto_save_timer.stop()
            self.pending_auto_save_paths.clear()
        selected_language = str(dialog.interface_language.currentData())
        if selected_language != self.interface_language:
            self.settings.setValue("interface_language", selected_language)
            QtWidgets.QMessageBox.information(
                self,
                self.t("語言變更"),
                self.t("介面語言會在下次啟動 PyFlow IDE 時套用。"),
            )
        self.settings.sync()
        self._apply_editor_preferences()

    def _apply_syntax_contrast(self, values: dict[str, int]) -> None:
        for index in range(self.tabs.count()):
            editor = self.tabs.widget(index)
            if isinstance(editor, CodeEditor):
                editor.set_syntax_contrast(values)

    def zoom_by(self, steps: int) -> None:
        self.editor_font_size = max(8, min(36, self.editor_font_size + steps))
        self._apply_editor_preferences()
        self.statusBar().showMessage(
            self.t("全部介面縮放：{percent}%", percent=self._zoom_percent())
        )

    def zoom_in(self) -> None:
        self.zoom_by(1)

    def zoom_out(self) -> None:
        self.zoom_by(-1)

    def reset_zoom(self) -> None:
        self.editor_font_size = 11
        self._apply_editor_preferences()
        self.statusBar().showMessage(self.t("全部介面縮放已重設為 100%"))

    def _zoom_percent(self) -> int:
        return round(self.editor_font_size / 11 * 100)

    def _update_zoom_label(self) -> None:
        if hasattr(self, "zoom_label"):
            self.zoom_label.setText(f"{self._zoom_percent()}%")

    def _apply_editor_preferences(self) -> None:
        ratio = self.editor_font_size / 11
        self.ui_font_size = max(8, min(30, round(9 * ratio)))
        app_font = QtGui.QFont("Microsoft JhengHei UI", self.ui_font_size)
        app = QtWidgets.QApplication.instance()
        app.setFont(app_font)
        self.setFont(app_font)
        for widget in (
            self.toolbar,
            self.tree,
            self.file_dock,
            self.tabs,
            self.outline,
            self.outline_dock,
            self.output_dock,
            self.terminal_panel,
            self.terminal_dock,
            self.graph_dock,
            self.search_panel,
            self.search_dock,
            self.statusBar(),
        ):
            widget.setFont(app_font)

        icon_size = max(16, min(34, round(18 * ratio)))
        self.toolbar.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.tree.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.tree.setIndentation(max(16, min(38, round(20 * ratio))))

        output_font = self.output.font()
        output_font.setPointSize(max(8, self.editor_font_size - 1))
        self.output.setFont(output_font)
        self.terminal_panel.set_ui_font_size(self.ui_font_size)
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if isinstance(editor, CodeEditor):
                editor.set_editor_font_size(self.editor_font_size)
                editor.set_syntax_contrast(self.syntax_contrast)
                mode = (
                    QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth
                    if self.word_wrap
                    else QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
                )
                editor.setLineWrapMode(mode)
        self.graph_panel.set_ui_font_size(self.ui_font_size)
        self._update_zoom_label()


def smoke() -> int:
    sample = Path(__file__).resolve().parent / "samples" / "demo_flow.py"
    text = svc.read_text(str(sample))
    parsed = svc.parse_source(str(sample), text.content)
    print(json.dumps({"read_ok": text.error is None, "lang": parsed.get("lang"), "defs": len(parsed.get("definitions") or [])}))
    return 0 if text.error is None else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="")
    parser.add_argument("--demo", choices=tuple(NODE_DEMOS))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return smoke()
    if args.self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("PyFlow Qt IDE")
    app.setApplicationVersion(APP_VERSION)
    app_font = QtGui.QFont("Microsoft JhengHei UI")
    app_font.setPointSize(9)
    app.setFont(app_font)
    window = MainWindow(
        args.folder or None,
        interface_language="zh_TW" if args.self_test else None,
    )
    if args.self_test:
        window.auto_save_enabled = False
        window.auto_save_timer.stop()
        window.show()
        window.open_file(
            str(Path(__file__).resolve().parent / "samples" / "demo_flow.py")
        )
        editor = window.active_editor()
        if editor is None:
            raise RuntimeError("self-test could not open the editor")
        font_before = editor.font().pointSize()
        metrics_before = editor.fontMetrics().height()
        line_area_before = editor.line_number_area_width()
        tree_font_before = window.tree.font().pointSize()
        tree_icon_before = window.tree.iconSize().width()
        window.zoom_by(3)
        app.processEvents()
        font_after = editor.font().pointSize()
        metrics_after = editor.fontMetrics().height()
        line_area_after = editor.line_number_area_width()
        tree_font_after = window.tree.font().pointSize()
        tree_icon_after = window.tree.iconSize().width()
        editor.setPlainText("")
        editor.set_language("python")
        editor.setFocus()
        QtTest.QTest.keyClicks(editor, "pri")
        app.processEvents()
        suggestions = [
            editor.completer.completionModel().data(
                editor.completer.completionModel().index(row, 0)
            )
            for row in range(editor.completer.completionModel().rowCount())
        ]
        if font_after <= font_before or metrics_after <= metrics_before:
            raise RuntimeError("editor zoom did not change the rendered font")
        if tree_font_after <= tree_font_before or tree_icon_after <= tree_icon_before:
            raise RuntimeError(
                "file tree did not follow the global zoom: "
                f"font={tree_font_before}->{tree_font_after}, "
                f"icon={tree_icon_before}->{tree_icon_after}"
            )
        if line_area_after <= line_area_before:
            raise RuntimeError("line number area did not follow zoom")
        if any(
            dock.isVisible()
            for dock in (
                window.outline_dock,
                window.output_dock,
                window.terminal_dock,
                window.graph_dock,
                window.search_dock,
            )
        ):
            raise RuntimeError("optional panels should be hidden by default")
        if "print" not in suggestions:
            raise RuntimeError("python print completion is missing")
        if editor.completer.completionPrefix() != "pri":
            raise RuntimeError("python completion did not react to typed text")
        completion_index = editor.completer.popup().currentIndex()
        completion_preselected = (
            completion_index.isValid()
            and completion_index.row() == 0
            and editor.completer.popup().selectionModel().isSelected(
                completion_index
            )
        )
        if not completion_preselected:
            raise RuntimeError("first completion item was not preselected")
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key.Key_Return)
        app.processEvents()
        if editor.toPlainText() != "print()":
            raise RuntimeError(
                "accepting print completion did not insert print(): "
                f"{editor.toPlainText()!r}, popup={editor.completer.popup().isVisible()}"
            )
        print_completion_text = editor.toPlainText()

        editor_language_cases = {
            "python": ("def demo():\n    # note", "pri", "print", "if True:"),
            "rust": ("fn main() {\n    // note\n}", "prin", "println!", "fn main() {"),
            "go": ("func main() {\n    // note\n}", "app", "append", "func main() {"),
            "c": ("int main(void) {\n    // note\n}", "pri", "printf", "int main(void) {"),
            "cpp": ("int main() {\n    // note\n}", "cou", "cout", "int main() {"),
            "zyenlang": ("fn main() {\n    // note\n}", "pri", "print", "fn main() {"),
        }
        editor_language_results: dict[str, dict[str, object]] = {}
        for language, (sample, prefix, expected, indent_line) in editor_language_cases.items():
            language_editor = CodeEditor()
            language_editor.set_language(language)
            language_editor.setPlainText(sample)
            language_editor.highlighter.rehighlight()
            app.processEvents()
            first_formats = language_editor.document().firstBlock().layout().formats()
            second_formats = language_editor.document().findBlockByNumber(1).layout().formats()
            if not first_formats or not any(
                item.format.foreground().color().name() == "#77756e"
                for item in second_formats
            ):
                raise RuntimeError(f"{language} syntax highlighting is incomplete")

            language_editor.setPlainText("")
            language_editor.set_language(language)
            language_editor.setFocus()
            QtTest.QTest.keyClicks(language_editor, prefix)
            app.processEvents()
            completions = [
                language_editor.completer.completionModel().data(
                    language_editor.completer.completionModel().index(row, 0)
                )
                for row in range(language_editor.completer.completionModel().rowCount())
            ]
            if expected not in completions:
                raise RuntimeError(
                    f"{language} completion {expected!r} missing for {prefix!r}"
                )

            language_editor.completer.popup().hide()
            language_editor.setPlainText(indent_line)
            cursor = language_editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            language_editor.setTextCursor(cursor)
            QtTest.QTest.keyClick(language_editor, QtCore.Qt.Key.Key_Return)
            app.processEvents()
            if not language_editor.toPlainText().endswith("\n    "):
                raise RuntimeError(f"{language} automatic indentation failed")

            comment_prefix = "#" if language == "python" else "//"
            original_comment_code = "    first\n\n    second"
            language_editor.setPlainText(original_comment_code)
            language_editor.selectAll()
            QtTest.QTest.keyClick(
                language_editor,
                QtCore.Qt.Key.Key_Slash,
                QtCore.Qt.KeyboardModifier.ControlModifier,
            )
            expected_comment_code = (
                f"    {comment_prefix} first\n\n    {comment_prefix} second"
            )
            if language_editor.toPlainText() != expected_comment_code:
                raise RuntimeError(f"{language} Ctrl+/ did not comment selected lines")
            QtTest.QTest.keyClick(
                language_editor,
                QtCore.Qt.Key.Key_Slash,
                QtCore.Qt.KeyboardModifier.ControlModifier,
            )
            if language_editor.toPlainText() != original_comment_code:
                raise RuntimeError(f"{language} Ctrl+/ did not uncomment selected lines")
            editor_language_results[language] = {
                "completion": expected,
                "indent": 4,
                "highlight": True,
                "comment_toggle": True,
            }

        contrast_editor = CodeEditor()
        contrast_editor.set_language("python")
        contrast_editor.setPlainText("if True:\n    # note")
        contrast_values = {
            "keyword": 35,
            "comment": 160,
            "string": 100,
            "function": 100,
            "type": 100,
            "number": 100,
        }
        contrast_editor.set_syntax_contrast(contrast_values)
        contrast_editor.highlighter.rehighlight()
        app.processEvents()
        keyword_contrast_color = (
            contrast_editor.highlighter.keyword_format.foreground().color().name()
        )
        comment_contrast_color = (
            contrast_editor.highlighter.comment_format.foreground().color().name()
        )
        expected_keyword_color = qlang.LanguageHighlighter._contrast_color(
            qlang.LanguageHighlighter.BASE_COLORS["keyword"], 35
        ).name()
        expected_comment_color = qlang.LanguageHighlighter._contrast_color(
            qlang.LanguageHighlighter.BASE_COLORS["comment"], 160
        ).name()
        if (
            keyword_contrast_color != expected_keyword_color
            or comment_contrast_color != expected_comment_color
        ):
            raise RuntimeError("syntax contrast colors were not applied")
        syntax_contrast_result = {
            "keyword": keyword_contrast_color,
            "comment": comment_contrast_color,
        }

        def completion_values(test_editor: CodeEditor) -> list[str]:
            model = test_editor.completer.completionModel()
            return [model.data(model.index(row, 0)) for row in range(model.rowCount())]

        zyen_args_code = (
            "fn add(a: int, beta: int) -> int {\n"
            "    return \n"
            "}\n"
        )
        editor.set_language("zyenlang")
        editor.setPlainText(zyen_args_code)
        args_position = zyen_args_code.index("return ") + len("return ")
        cursor = editor.textCursor()
        cursor.setPosition(args_position)
        editor.setTextCursor(cursor)
        editor._refresh_completion_model()
        editor.setFocus()
        QtTest.QTest.keyClicks(editor, "a")
        app.processEvents()
        argument_row = next(
            (
                row
                for row in range(editor.completion_model.rowCount())
                if editor.completion_model.item(row, 0).text() == "a"
            ),
            -1,
        )
        argument_detail = (
            editor.completion_model.item(argument_row, 1).text()
            if argument_row >= 0
            else ""
        )
        if (
            not editor.completer.popup().isVisible()
            or editor.completer.currentCompletion() != "a"
            or "a: int" not in argument_detail
        ):
            raise RuntimeError("single-character ZyenLang argument completion failed")
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key.Key_Return)
        if "return a" not in editor.toPlainText():
            raise RuntimeError("ZyenLang argument completion was not inserted")

        closure_context_code = (
            "fn make(factor: int) -> fn(int)->int {\n"
            "    fn inner(value: int) -> int {\n"
            "        return value;\n"
            "    }\n"
            "    return inner;\n"
            "}\n"
        )
        closure_position = closure_context_code.index("return value")
        closure_details = qlang.context_completion_details(
            "zyenlang", closure_context_code, closure_position
        )
        if (
            "factor" not in closure_details
            or "value" not in closure_details
            or "parameter" not in closure_details["factor"]
        ):
            raise RuntimeError("ZyenLang closure arguments were not inherited")
        zyen_argument_result = {
            "single": argument_detail,
            "closure": sorted(closure_details),
        }
        editor.completer.popup().hide()
        editor.set_language("python")
        editor.setPlainText("print()")

        python_symbol_results: dict[str, str] = {}
        symbol_cases = {
            "variable": ("my_variable = 42", "my_v", "my_variable", False),
            "function": ("def my_function(value):", "my_f", "my_function", True),
            "async_function": (
                "async def my_async_function(value):",
                "my_a",
                "my_async_function",
                True,
            ),
            "class": ("class MyClass:", "MyC", "MyClass", True),
        }
        for kind, (declaration, prefix, expected, callable_symbol) in symbol_cases.items():
            symbol_editor = CodeEditor()
            symbol_editor.set_language("python")
            symbol_editor.setPlainText(declaration)
            cursor = symbol_editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            symbol_editor.setTextCursor(cursor)
            symbol_editor.setFocus()
            QtTest.QTest.keyClick(symbol_editor, QtCore.Qt.Key.Key_Return)
            QtTest.QTest.keyClicks(symbol_editor, prefix)
            app.processEvents()
            if expected not in completion_values(symbol_editor):
                raise RuntimeError(f"python {kind} symbol completion is missing")
            QtTest.QTest.keyClick(symbol_editor, QtCore.Qt.Key.Key_Return)
            app.processEvents()
            inserted = symbol_editor.toPlainText().splitlines()[-1].strip()
            expected_inserted = expected + ("()" if callable_symbol else "")
            if inserted != expected_inserted:
                raise RuntimeError(
                    f"python {kind} completion inserted {inserted!r}, "
                    f"expected {expected_inserted!r}"
                )
            python_symbol_results[kind] = inserted

        decorator_editor = CodeEditor()
        decorator_editor.set_language("python")
        decorator_editor.setPlainText("def my_decorator(func):\n    return func\n\n@")
        decorator_editor._refresh_completion_model()
        cursor = decorator_editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        decorator_editor.setTextCursor(cursor)
        decorator_editor.setFocus()
        QtTest.QTest.keyClicks(decorator_editor, "my_d")
        app.processEvents()
        if "my_decorator" not in completion_values(decorator_editor):
            raise RuntimeError("python decorator completion is missing")
        QtTest.QTest.keyClick(decorator_editor, QtCore.Qt.Key.Key_Return)
        if not decorator_editor.toPlainText().endswith("@my_decorator"):
            raise RuntimeError("decorator completion incorrectly added call parentheses")
        python_symbol_results["decorator"] = "@my_decorator"

        function_detail_code = (
            'def typed_function(value: int, label: str = "item", raw=None) -> bool:\n'
            '    """Return whether the value is enabled."""\n'
            "    return bool(value)\n\n"
            "def untyped_function(payload):\n"
            "    return payload\n"
        )
        function_detail_graph = svc.build_python_graph(function_detail_code)
        function_nodes = {
            str(node.get("id")): node
            for node in function_detail_graph.get("nodes") or []
            if isinstance(node, dict)
        }
        typed_node = function_nodes.get("typed_function") or {}
        untyped_node = function_nodes.get("untyped_function") or {}
        typed_parameters = typed_node.get("parameters") or []
        if (
            typed_node.get("return_type") != "bool"
            or len(typed_parameters) != 3
            or typed_parameters[0].get("type") != "int"
            or typed_parameters[1].get("default") != "'item'"
            or typed_parameters[2].get("type") != "Any"
            or typed_parameters[2].get("default") != "None"
            or untyped_node.get("return_type") != "Any"
            or (untyped_node.get("parameters") or [{}])[0].get("type") != "Any"
        ):
            raise RuntimeError("Python function type details are incomplete")

        completion_signature = qlang.completion_details(
            "python", function_detail_code
        ).get("typed_function", "")
        if not all(
            part in completion_signature
            for part in (
                "value: int",
                "label: str",
                "raw: Any",
                "-> bool",
            )
        ):
            raise RuntimeError(
                f"Python completion signature is incomplete: {completion_signature!r}"
            )

        original_tab_index = window.tabs.currentIndex()
        sync_directory = QtCore.QTemporaryDir()
        if not sync_directory.isValid():
            raise RuntimeError("could not create external-sync test directory")
        sync_path = Path(sync_directory.path()) / "external_sync.py"
        sync_path.write_text("value = 1\n", encoding="utf-8")
        window.open_file(str(sync_path))
        sync_editor = window.active_editor()
        if sync_editor is None:
            raise RuntimeError("could not open external-sync test file")
        sync_cursor = sync_editor.textCursor()
        sync_cursor.setPosition(4)
        sync_editor.setTextCursor(sync_cursor)
        sync_path.write_text("external_value = 2\n", encoding="utf-8")
        window._check_external_changes()
        app.processEvents()
        external_sync_result = (
            sync_editor.toPlainText() == "external_value = 2\n"
            and sync_editor.textCursor().position() == 4
            and not sync_editor.document().isModified()
        )
        if not external_sync_result:
            raise RuntimeError("external file changes were not synchronized")

        sync_editor.setPlainText("auto_saved = True\n")
        sync_editor.document().setModified(True)
        window.auto_save_enabled = True
        auto_save_delay = window.auto_save_delay_ms
        window.auto_save_delay_ms = 100
        window._editor_text_changed(sync_editor)
        auto_save_deadline = QtCore.QElapsedTimer()
        auto_save_deadline.start()
        while (
            sync_editor.document().isModified()
            and auto_save_deadline.elapsed() < 1000
        ):
            app.processEvents()
            QtTest.QTest.qWait(10)
        auto_save_result = (
            sync_path.read_text(encoding="utf-8") == "auto_saved = True\n"
            and not sync_editor.document().isModified()
        )
        if not auto_save_result:
            raise RuntimeError("auto-save did not write the edited file")
        window.auto_save_delay_ms = auto_save_delay
        window.auto_save_enabled = False
        sync_index = window.path_to_tab.get(str(sync_path))
        if sync_index is not None:
            window.close_tab(sync_index)
        window.tabs.setCurrentIndex(original_tab_index)
        sync_directory.remove()

        english_window = MainWindow(args.folder or None, interface_language="en")
        english_settings = SettingsDialog(english_window)
        english_actions = {action.text() for action in english_window.toolbar.actions()}
        if (
            english_window.windowTitle() != "PyFlow IDE"
            or english_window.file_dock.windowTitle() != "Files"
            or english_window.search_panel.button.text() != "Search"
            or english_window.graph_panel.relations.headerItem().text(0)
            != "Relationship and node"
            or english_window.graph_panel.node_search.placeholderText()
            != "Search nodes or functions..."
            or english_window.terminal_panel.input.placeholderText()
            != "Enter a PowerShell command"
            or english_settings.windowTitle() != "Settings"
            or english_settings.auto_save.text() != "Auto save"
            or english_settings.auto_save_delay.minimum() != 0.1
            or english_settings.auto_save_delay.singleStep() != 0.1
            or set(english_settings.syntax_contrast_sliders)
            != {name for name, _ in SYNTAX_CONTRAST_OPTIONS}
            or any(
                slider.minimum() != 0 or slider.maximum() != 200
                for slider in english_settings.syntax_contrast_sliders.values()
            )
            or "Open File" not in english_actions
        ):
            raise RuntimeError("English interface translation is incomplete")
        english_settings.close()
        english_window.close()
        demo_code = (Path(__file__).resolve().parent / "samples" / "demo_flow.py").read_text(
            encoding="utf-8"
        )
        demo_graph = svc.build_python_graph(demo_code)
        if len(demo_graph.get("nodes") or []) < 5 or len(demo_graph.get("edges") or []) < 3:
            raise RuntimeError("node demo graph is incomplete")
        window._request_node_graph("demo_flow.py", demo_code, "節點 Demo")
        deadline = QtCore.QElapsedTimer()
        deadline.start()
        while window.graph_workers and deadline.elapsed() < 3000:
            app.processEvents()
            QtTest.QTest.qWait(10)
        if window.graph_workers:
            raise RuntimeError("background node graph worker timed out")
        if not window.graph_view.graph_scene.items():
            raise RuntimeError("node demo did not render")
        large_code = "\n".join(
            (
                "def func_0(value: int) -> int:\n    return value"
                if index == 0
                else f"def func_{index}(value: int) -> int:\n"
                f"    return func_{index - 1}(value) if value else 0"
            )
            for index in range(1200)
        )
        window._request_node_graph("large_demo.py", large_code, "大型節點測試")
        deadline.restart()
        while window.graph_workers and deadline.elapsed() < 3000:
            app.processEvents()
            QtTest.QTest.qWait(10)
        large_graph = window.graph_view.graph
        if window.graph_workers or not large_graph.get("truncated"):
            raise RuntimeError("large node graph did not complete with bounded output")
        if len(large_graph.get("nodes") or []) != 120:
            raise RuntimeError("large node graph node limit is incorrect")

        samples_dir = Path(__file__).resolve().parent / "samples"
        language_samples = {
            filename: (samples_dir / filename).read_text(encoding="utf-8")
            for language, (_, filename) in NODE_DEMOS.items()
            if language != "python"
        }
        language_graphs: dict[str, dict[str, object]] = {}
        language_counts: dict[str, list[int]] = {}
        for sample_path, sample_code in language_samples.items():
            graph = svc.build_code_graph(sample_path, sample_code)
            if graph.get("error"):
                raise RuntimeError(f"{sample_path} graph failed: {graph['error']}")
            nodes = list(graph.get("nodes") or [])
            edges = list(graph.get("edges") or [])
            if len(nodes) < 8 or len(edges) < 7:
                raise RuntimeError(
                    f"{sample_path} graph is incomplete: {len(nodes)} nodes, {len(edges)} edges"
                )
            language = str(graph.get("language"))
            language_graphs[language] = graph
            language_counts[language] = [len(nodes), len(edges)]

        zyen_graph = language_graphs["zyenlang"]
        zyen_nodes = {
            str(node.get("id")): node
            for node in zyen_graph.get("nodes") or []
            if isinstance(node, dict)
        }
        zyen_edges = {
            (str(edge.get("source")), str(edge.get("target")))
            for edge in zyen_graph.get("edges") or []
            if isinstance(edge, dict)
        }
        expected_zyen_edges = {
            ("Pipeline.process", "Pipeline.normalize"),
            ("Pipeline.process", "Pipeline.summarize"),
            ("Pipeline.normalize", "Record.scaled"),
            ("make_mapper.map_value", "clamp"),
            ("main", "make_mapper"),
        }
        pipeline_node = zyen_nodes.get("Pipeline") or {}
        mapper_node = zyen_nodes.get("make_mapper") or {}
        if (
            not expected_zyen_edges.issubset(zyen_edges)
            or mapper_node.get("return_type") != "fn(int)->int"
            or (pipeline_node.get("parameters") or [{}, {}])[1].get("type")
            != "fn(int)->int"
            or "make_mapper.map_value" not in zyen_nodes
        ):
            raise RuntimeError("ZyenLang node graph metadata is incomplete")

        recursive_zyen_code = (
            "struct Holder {\n"
            "    let this.callback: ptr<ptr<fn(int)->void>>;\n"
            "}\n\n"
            "fn convert(callback: ptr<fn(int,int)->int>, "
            "fallback: ptr<ptr<int>> = None) -> fn(str)->fn(int)->int;\n\n"
            "fn convert(callback: ptr<fn(int,int)->int>, "
            "fallback: ptr<ptr<int>> = None) -> fn(str)->fn(int)->int {\n"
            "    fn nested(value: int) -> int {\n"
            "        return value;\n"
            "    }\n"
            "    return None;\n"
            "}\n"
        )
        recursive_graph = svc.build_code_graph("recursive.zy", recursive_zyen_code)
        recursive_nodes = {
            str(node.get("id")): node
            for node in recursive_graph.get("nodes") or []
            if isinstance(node, dict)
        }
        convert_node = recursive_nodes.get("convert") or {}
        holder_node = recursive_nodes.get("Holder") or {}
        zyen_completion_details = qlang.completion_details(
            "zyenlang", recursive_zyen_code
        )
        zyen_completion_signature = zyen_completion_details.get("convert", "")
        zyen_print_signature = zyen_completion_details.get("print", "")
        if (
            convert_node.get("return_type") != "fn(str)->fn(int)->int"
            or (convert_node.get("parameters") or [{}])[0].get("type")
            != "ptr<fn(int,int)->int>"
            or (holder_node.get("parameters") or [{}])[0].get("type")
            != "ptr<ptr<fn(int)->void>>"
            or "convert.nested" not in recursive_nodes
            or "fallback: ptr<ptr<int>> = None" not in zyen_completion_signature
            or zyen_print_signature != "print(value: str) -> void"
        ):
            raise RuntimeError("recursive ZyenLang type parsing failed")

        large_zyen_code = "\n\n".join(
            (
                "fn zfunc_0(value: int) -> int { return value; }"
                if index == 0
                else f"fn zfunc_{index}(value: int) -> int {{ "
                f"return zfunc_{index - 1}(value); }}"
            )
            for index in range(1200)
        )
        large_zyen_graph = svc.build_code_graph("large.zy", large_zyen_code)
        if (
            len(large_zyen_graph.get("nodes") or []) != 120
            or not large_zyen_graph.get("truncated")
        ):
            raise RuntimeError("large ZyenLang graph was not bounded")

        zyen_completion_editor = CodeEditor()
        zyen_completion_editor.set_language("zyenlang")
        zyen_completion_editor.setPlainText(
            "struct Holder {\n}\n\nHol"
        )
        cursor = zyen_completion_editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        zyen_completion_editor.setTextCursor(cursor)
        zyen_completion_editor.completer.setCompletionPrefix("Hol")
        zyen_completion_editor._insert_completion("Holder")
        if not zyen_completion_editor.toPlainText().endswith("Holder"):
            raise RuntimeError("ZyenLang struct completion incorrectly added parentheses")

        window.graph_panel.set_graph(zyen_graph, "ZyenLang relationship test")
        window.graph_panel.node_search.setText("map_value")
        window.graph_panel._activate_node_search()
        if (
            window.graph_panel.current_node_id != "make_mapper.map_value"
            or "int" not in window.graph_panel.return_type.text()
        ):
            raise RuntimeError("ZyenLang node search did not select the closure")

        go_graph = language_graphs["go"]
        helper_id = next(
            str(node["id"])
            for node in go_graph.get("nodes") or []
            if isinstance(node, dict) and node.get("label") == "normalizeRecord"
        )
        blocker = QtCore.QSignalBlocker(window.graph_dock)
        window.graph_dock.show()
        del blocker
        window.graph_panel.set_graph(go_graph, "Go 關係測試")
        app.processEvents()
        QtTest.QTest.qWait(50)
        window.graph_panel.node_search.setText("normalize")
        if window.graph_panel.node_search_matches != [helper_id]:
            raise RuntimeError("node search did not find the matching function")
        window.graph_panel._activate_node_search()
        if window.graph_panel.current_node_id != helper_id:
            raise RuntimeError("node search did not focus the matching function")
        helper_item = next(
            item
            for item in window.graph_view.graph_scene.items()
            if str(item.data(1) or "") == helper_id
        )
        helper_position = window.graph_view.mapFromScene(
            helper_item.sceneBoundingRect().center()
        )
        QtTest.QTest.mouseClick(
            window.graph_view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=helper_position,
        )
        app.processEvents()
        caller_group = window.graph_panel.relations.topLevelItem(1)
        if (
            window.graph_panel.current_node_id != helper_id
            or caller_group is None
            or caller_group.childCount() != 1
            or caller_group.child(0).text(0) != "Pipeline.process"
            or window.graph_panel.detail_tabs.count() != 2
            or window.graph_panel.parameters.topLevelItemCount() != 2
            or window.graph_panel.parameters.topLevelItem(0).text(1) != "Record"
            or "Record" not in window.graph_panel.return_type.text()
        ):
            raise RuntimeError("function details did not follow node selection")

        node_width_before = (
            helper_item.sceneBoundingRect().width()
            * abs(window.graph_view.transform().m11())
        )
        relation_font_before = window.graph_panel.node_name.font().pointSize()
        window.zoom_by(2)
        app.processEvents()
        QtTest.QTest.qWait(50)
        helper_item_after = next(
            item
            for item in window.graph_view.graph_scene.items()
            if str(item.data(1) or "") == helper_id
        )
        node_width_after = (
            helper_item_after.sceneBoundingRect().width()
            * abs(window.graph_view.transform().m11())
        )
        relation_font_after = window.graph_panel.node_name.font().pointSize()
        if (
            node_width_after <= node_width_before * 1.1
            or relation_font_after <= relation_font_before
        ):
            raise RuntimeError(
                "node graph did not follow global zoom: "
                f"card={node_width_before:.1f}->{node_width_after:.1f}, "
                f"details={relation_font_before}->{relation_font_after}"
            )

        caller_name = caller_group.child(0).text(0)
        caller_line = next(
            int(node.get("line") or 0)
            for node in go_graph.get("nodes") or []
            if isinstance(node, dict) and node.get("id") == "Pipeline.process"
        )
        relation_lines: list[int] = []
        window.graph_panel.nodeActivated.connect(relation_lines.append)
        window.graph_panel._activate_relation(caller_group.child(0))
        window.graph_panel._activate_current_node()
        if (
            window.graph_panel.current_node_id != "Pipeline.process"
            or relation_lines[-2:] != [caller_line, caller_line]
        ):
            raise RuntimeError(
                "relation activation did not update the current node before Go to Code"
            )

        find_editor = CodeEditor()
        find_editor.resize(800, 420)
        find_editor.show()
        find_editor.setPlainText("alpha beta\nalpha gamma\nalpha delta\n")
        find_editor.setFocus()
        QtTest.QTest.keyClick(
            find_editor,
            QtCore.Qt.Key.Key_F,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        app.processEvents()
        QtTest.QTest.keyClicks(find_editor.find_input, "alpha")
        app.processEvents()
        first_find_status = find_editor.find_status.text()
        QtTest.QTest.keyClick(find_editor.find_input, QtCore.Qt.Key.Key_Return)
        second_find_status = find_editor.find_status.text()
        QtTest.QTest.keyClick(find_editor.find_input, QtCore.Qt.Key.Key_Escape)
        if (
            first_find_status != "1/3"
            or second_find_status != "2/3"
            or find_editor.find_bar.isVisible()
        ):
            raise RuntimeError("Ctrl+F editor find workflow failed")
        find_editor.close()

        window.activateWindow()
        QtTest.QTest.keyClick(
            window,
            QtCore.Qt.Key.Key_QuoteLeft,
            QtCore.Qt.KeyboardModifier.ControlModifier,
        )
        deadline.restart()
        while (
            (
                window.terminal_panel.process.state()
                != QtCore.QProcess.ProcessState.Running
                or not window.terminal_panel.input.isEnabled()
            )
            and deadline.elapsed() < 3000
        ):
            app.processEvents()
            QtTest.QTest.qWait(10)
        QtTest.QTest.qWait(150)
        if (
            not window.terminal_dock.isVisible()
            or window.terminal_panel.process.state()
            != QtCore.QProcess.ProcessState.Running
        ):
            raise RuntimeError(
                "Ctrl+` did not open PowerShell: "
                f"visible={window.terminal_dock.isVisible()}, "
                f"state={window.terminal_panel.process.state().name}, "
                f"status={window.terminal_panel.status.text()!r}"
            )
        window.terminal_panel.input.setText("$x = 41")
        window.terminal_panel.run_command()
        window.terminal_panel.input.setText("Write-Output ($x + 1)")
        window.terminal_panel.run_command()
        deadline.restart()
        while "42" not in window.terminal_panel.output.toPlainText() and deadline.elapsed() < 3000:
            app.processEvents()
            QtTest.QTest.qWait(10)
        terminal_output = window.terminal_panel.output.toPlainText()
        terminal_input_font = window.terminal_panel.input.font().pointSize()
        terminal_output_font = window.terminal_panel.output.font().pointSize()
        terminal_output_separated = "PS> Write-Output ($x + 1)\n42" in terminal_output
        window.terminal_panel.close_button.click()
        app.processEvents()
        if (
            "42" not in terminal_output
            or not terminal_output_separated
            or terminal_input_font <= terminal_output_font
            or window.terminal_dock.isVisible()
            or window.terminal_panel.process.state()
            != QtCore.QProcess.ProcessState.NotRunning
        ):
            raise RuntimeError(
                "PowerShell state or quick close failed: "
                f"has_42={'42' in terminal_output}, "
                f"output_separated={terminal_output_separated}, "
                f"fonts={[terminal_output_font, terminal_input_font]}, "
                f"visible={window.terminal_dock.isVisible()}, "
                f"state={window.terminal_panel.process.state().name}, "
                f"output={terminal_output!r}"
            )
        print(
            json.dumps(
                {
                    "zoom": [font_before, font_after],
                    "font_height": [metrics_before, metrics_after],
                    "line_numbers": [line_area_before, line_area_after],
                    "tree_zoom": [tree_font_before, tree_font_after],
                    "tree_icons": [tree_icon_before, tree_icon_after],
                    "print_completion": print_completion_text,
                    "completion_preselected": completion_preselected,
                    "language_editor": editor_language_results,
                    "zyenlang_arguments": zyen_argument_result,
                    "python_symbols": python_symbol_results,
                    "function_details": {
                        "parameters": [
                            [
                                parameter.get("name"),
                                parameter.get("type"),
                                parameter.get("default"),
                            ]
                            for parameter in typed_parameters
                        ],
                        "return": typed_node.get("return_type"),
                        "unknown": untyped_node.get("return_type"),
                    },
                    "completion_signature": completion_signature,
                    "interface_languages": ["zh_TW", "en"],
                    "file_sync": external_sync_result,
                    "auto_save": [auto_save_result, auto_save_delay],
                    "syntax_contrast": syntax_contrast_result,
                    "node_demo": [
                        len(demo_graph.get("nodes") or []),
                        len(demo_graph.get("edges") or []),
                    ],
                    "large_node_graph": [
                        len(large_graph.get("nodes") or []),
                        len(large_graph.get("edges") or []),
                    ],
                    "language_graphs": language_counts,
                    "zyenlang": {
                        "recursive_return": convert_node.get("return_type"),
                        "closure": "convert.nested" in recursive_nodes,
                        "completion": zyen_completion_signature,
                        "print": zyen_print_signature,
                        "large_nodes": len(large_zyen_graph.get("nodes") or []),
                    },
                    "selected_node_callers": [caller_name],
                    "relation_go_to_code": relation_lines[-2:],
                    "node_search": [helper_id, window.graph_panel.node_search_status.text()],
                    "editor_find": [first_find_status, second_find_status],
                    "powershell": {
                        "result": "42" in terminal_output,
                        "shortcut": "Ctrl+`",
                        "fonts": [terminal_output_font, terminal_input_font],
                        "output_separated": terminal_output_separated,
                    },
                    "node_zoom": [
                        round(node_width_before),
                        round(node_width_after),
                    ],
                    "node_detail_font": [relation_font_before, relation_font_after],
                }
            )
        )
        QtCore.QTimer.singleShot(250, app.quit)
    else:
        window.show()
        if args.demo:
            QtCore.QTimer.singleShot(0, lambda: window.show_node_demo(args.demo))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
