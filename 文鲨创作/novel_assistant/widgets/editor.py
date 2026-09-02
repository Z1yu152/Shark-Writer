# -*- coding: utf-8 -*-
"""正文编辑器控件。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QTextBlockFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit, QWidget

from ..core.config import (
    DEFAULT_BODY_FONT_FAMILY,
    DEFAULT_BODY_FONT_SIZE,
    DEFAULT_LETTER_SPACING,
    DEFAULT_LINE_SPACING,
    DEFAULT_TITLE_FONT_SIZE,
    PARAGRAPH_INDENT,
    PALETTE,
)



class ManuscriptEditor(QTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_font_family = DEFAULT_BODY_FONT_FAMILY
        self.body_font_size = DEFAULT_BODY_FONT_SIZE
        self.title_font_size = DEFAULT_TITLE_FONT_SIZE
        self.line_spacing = DEFAULT_LINE_SPACING
        self.letter_spacing = DEFAULT_LETTER_SPACING
        self.canvas_background = PALETTE["paper"]
        self.setAcceptRichText(True)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(28)
        self.apply_editor_defaults()

    def set_canvas_background(self, color: str) -> None:
        self.canvas_background = color
        self.viewport().update()

    def set_editor_style(self, font_family: str, font_size: int, line_spacing: int, letter_spacing: int | None = None) -> None:
        self.body_font_family = font_family or self.body_font_family
        self.body_font_size = font_size
        self.line_spacing = line_spacing
        if letter_spacing is not None:
            self.letter_spacing = letter_spacing
        self.apply_line_spacing_to_document()
        self.viewport().update()

    def body_char_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamily(self.body_font_family)
        fmt.setFontPointSize(self.body_font_size)
        fmt.setFontWeight(QFont.Normal)
        fmt.setFontLetterSpacingType(QFont.PercentageSpacing)
        fmt.setFontLetterSpacing(self.letter_spacing)
        return fmt

    def title_char_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamily(self.body_font_family)
        fmt.setFontPointSize(self.title_font_size)
        fmt.setFontWeight(QFont.Bold)
        fmt.setFontLetterSpacingType(QFont.PercentageSpacing)
        fmt.setFontLetterSpacing(self.letter_spacing)
        return fmt

    def body_block_format(self) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setAlignment(Qt.AlignLeft)
        fmt.setLineHeight(float(self.line_spacing), QTextBlockFormat.FixedHeight.value)
        fmt.setTopMargin(0)
        fmt.setBottomMargin(0)
        return fmt

    def title_block_format(self) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setAlignment(Qt.AlignHCenter)
        fmt.setLineHeight(float(max(self.line_spacing, self.title_font_size + 12)), QTextBlockFormat.FixedHeight.value)
        fmt.setTopMargin(4)
        fmt.setBottomMargin(6)
        return fmt

    def apply_editor_defaults(self) -> None:
        font = QFont(self.body_font_family, self.body_font_size)
        font.setLetterSpacing(QFont.PercentageSpacing, self.letter_spacing)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.apply_line_spacing_to_document()

    def apply_line_spacing_to_document(self) -> None:
        block = self.document().firstBlock()
        while block.isValid():
            cursor = QTextCursor(block)
            block_format = block.blockFormat()
            block_format.setLineHeight(float(self.line_spacing), QTextBlockFormat.FixedHeight.value)
            block_format.setTopMargin(0)
            block_format.setBottomMargin(0)
            cursor.setBlockFormat(block_format)
            block = block.next()

    def apply_document_structure(self) -> None:
        block = self.document().firstBlock()
        is_title = True
        while block.isValid():
            cursor = QTextCursor(block)
            if is_title:
                cursor.mergeBlockFormat(self.title_block_format())
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.mergeCharFormat(self.title_char_format())
                is_title = False
            else:
                cursor.mergeBlockFormat(self.body_block_format())
            block = block.next()

    def format_current_block_as_title(self) -> None:
        cursor = self.textCursor()
        cursor.mergeBlockFormat(self.title_block_format())
        cursor.mergeCharFormat(self.title_char_format())
        self.setTextCursor(cursor)

    def format_current_block_as_body(self) -> None:
        cursor = self.textCursor()
        cursor.mergeBlockFormat(self.body_block_format())
        cursor.mergeCharFormat(self.body_char_format())
        self.setTextCursor(cursor)

    def ensure_body_cursor(self) -> None:
        cursor = self.textCursor()
        if cursor.blockNumber() > 0:
            cursor.mergeBlockFormat(self.body_block_format())
            cursor.mergeCharFormat(self.body_char_format())
            self.setTextCursor(cursor)

    def line_start_y(self) -> int:
        return int(self.first_body_top_y())

    def first_body_top_y(self) -> float:
        first = self.document().firstBlock()
        if not first.isValid():
            return self.document().documentMargin()
        second = first.next()
        if second.isValid():
            return self.document().documentLayout().blockBoundingRect(second).top()
        title_rect = self.document().documentLayout().blockBoundingRect(first)
        return title_rect.top() + max(self.line_spacing, self.title_font_size + 12) + 6

    def ensure_current_body_indent(self) -> None:
        cursor = self.textCursor()
        if cursor.blockNumber() == 0:
            return
        if cursor.block().text().strip():
            return
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.insertText(PARAGRAPH_INDENT)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            block_number = cursor.blockNumber()
            cursor.insertBlock()
            self.setTextCursor(cursor)
            if block_number == 0:
                self.format_current_block_as_body()
            else:
                self.ensure_body_cursor()
            cursor = self.textCursor()
            cursor.insertText(PARAGRAPH_INDENT)
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        raw_pos = event.position() if hasattr(event, "position") else event.pos()
        click_y = raw_pos.y() + self.verticalScrollBar().value()
        line_start = self.line_start_y()
        target_block = 0 if click_y < line_start else int((click_y - line_start) // self.line_spacing) + 1
        if target_block >= self.document().blockCount():
            cursor = QTextCursor(self.document())
            cursor.movePosition(QTextCursor.End)
            while self.document().blockCount() <= target_block:
                cursor.insertBlock(self.body_block_format(), self.body_char_format())
                cursor.insertText(PARAGRAPH_INDENT)
            self.setTextCursor(cursor)
            self.setFocus()
            return
        super().mousePressEvent(event)
        self.ensure_current_body_indent()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), QColor(self.canvas_background))
        painter.end()
        super().paintEvent(event)
