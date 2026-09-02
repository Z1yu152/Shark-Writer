# -*- coding: utf-8 -*-
"""应用级 Qt 样式。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle

from ..core.config import PALETTE


class WenshaCheckStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None) -> int:
        if metric in {QStyle.PixelMetric.PM_IndicatorWidth, QStyle.PixelMetric.PM_IndicatorHeight}:
            return 16
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(self, element, option, painter, widget=None) -> None:
        check_elements = {
            QStyle.PrimitiveElement.PE_IndicatorCheckBox,
            QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
        }
        if element not in check_elements:
            super().drawPrimitive(element, option, painter, widget)
            return

        state = option.state
        enabled = bool(state & QStyle.StateFlag.State_Enabled)
        checked = bool(state & QStyle.StateFlag.State_On)
        partial = bool(state & QStyle.StateFlag.State_NoChange)
        hovered = bool(state & QStyle.StateFlag.State_MouseOver)

        rect = option.rect.adjusted(1, 1, -1, -1)
        side = min(rect.width(), rect.height(), 16)
        left = rect.x() + (rect.width() - side) / 2
        top = rect.y() + (rect.height() - side) / 2
        box = rect.__class__(round(left), round(top), side, side)

        border = QColor(PALETTE["ink"] if enabled else PALETTE["muted"])
        background = QColor(PALETTE["panel"] if enabled and hovered else PALETTE["paper"])
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(border, 1.4))
        painter.setBrush(QBrush(background))
        painter.drawRoundedRect(box, 3, 3)

        if checked:
            pen = QPen(border, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(QPointF(box.left() + side * 0.25, box.top() + side * 0.52), QPointF(box.left() + side * 0.43, box.top() + side * 0.70))
            painter.drawLine(QPointF(box.left() + side * 0.43, box.top() + side * 0.70), QPointF(box.left() + side * 0.76, box.top() + side * 0.30))
        elif partial:
            pen = QPen(border, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(box.left() + side * 0.25, box.center().y()), QPointF(box.left() + side * 0.75, box.center().y()))
        painter.restore()


def install_wensha_check_style(app: QApplication | None) -> None:
    if app is None or app.property("wensha_check_style_installed"):
        return
    app.setStyle(WenshaCheckStyle(app.style()))
    app.setProperty("wensha_check_style_installed", True)
