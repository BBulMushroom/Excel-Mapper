"""Keep Qt's standard tooltip design while making hover help easier to read."""
from PySide6.QtWidgets import QProxyStyle,QStyle


class NativeStyle(QProxyStyle):
    def __init__(self):super().__init__('Fusion')
    def styleHint(self,hint,option=None,widget=None,returnData=None):
        if hint==QStyle.StyleHint.SH_ComboBox_Popup:return 0
        if hint==QStyle.StyleHint.SH_ToolTip_WakeUpDelay:return 350
        return super().styleHint(hint,option,widget,returnData)

    def drawPrimitive(self,element,option,painter,widget=None):
        if element in (QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,QStyle.PrimitiveElement.PE_IndicatorCheckBox):
            from PySide6.QtCore import Qt,QRectF
            from PySide6.QtGui import QColor,QPen,QPainter,QPainterPath
            checked=bool(option.state&(QStyle.StateFlag.State_On|QStyle.StateFlag.State_NoChange));rect=QRectF(option.rect).adjusted(1,1,-1,-1)
            painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setPen(QPen(QColor('#2563eb') if checked else QColor('#94a3b8' if option.palette.base().color().lightness()<128 else '#64748b'),1));painter.setBrush(QColor('#2563eb') if checked else option.palette.base());painter.drawRoundedRect(rect,2,2)
            if checked:
                painter.setPen(QPen(QColor('white'),1.8))
                if option.state&QStyle.StateFlag.State_NoChange:painter.drawLine(rect.left()+3,rect.center().y(),rect.right()-3,rect.center().y())
                else:
                    path=QPainterPath();path.moveTo(rect.left()+rect.width()*.2,rect.top()+rect.height()*.5);path.lineTo(rect.left()+rect.width()*.43,rect.top()+rect.height()*.73);path.lineTo(rect.left()+rect.width()*.82,rect.top()+rect.height()*.24);painter.drawPath(path)
            painter.restore();return
        super().drawPrimitive(element,option,painter,widget)
