"""Small native motion helpers and an external transparent change rail."""
from PySide6.QtCore import Qt,QObject,QVariantAnimation,QEasingCurve,QTimer,QRectF,QRect,QPoint,QSize
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget,QHBoxLayout,QScrollBar

MARK_COLORS={'추가':'#22c55e','수정':'#f59e0b','삭제':'#ef4444'}


class SmoothScroll(QObject):
    def __init__(self,view):
        super().__init__(view);self.view=view;self.animations={};self.targets={}
    def stop(self):
        for animation in self.animations.values():animation.stop()
        self.targets.clear()
    def wheel(self,event):
        modifiers=event.modifiers();view=self.view
        owner=view.window if not callable(view.window) else view.window()
        if modifiers&Qt.KeyboardModifier.ControlModifier and hasattr(owner,'zoom'):
            self.stop();owner.zoom(1 if event.angleDelta().y()>0 else -1);event.accept();return
        horizontal=bool(modifiers&Qt.KeyboardModifier.ShiftModifier) or abs(event.angleDelta().x())>abs(event.angleDelta().y())
        bar=view.horizontalScrollBar() if horizontal else view.verticalScrollBar()
        pixels=event.pixelDelta();angles=event.angleDelta()
        amount=(pixels.x() or pixels.y()) if horizontal else pixels.y()
        if amount:
            self.stop();bar.setValue(bar.value()-amount);event.accept();return
        amount=(angles.x() or angles.y()) if horizontal else angles.y()
        if not amount:event.ignore();return
        timer=self.animations.get(horizontal)
        if timer is None:
            timer=QTimer(self);timer.setInterval(16);self.animations[horizontal]=timer
            def advance():
                target=self.targets.get(horizontal,bar.value());distance=target-bar.value()
                if abs(distance)<=1:bar.setValue(round(target));timer.stop();return
                move=distance*.48
                if abs(move)<1:move=1 if move>0 else -1
                bar.setValue(round(bar.value()+move))
            timer.timeout.connect(advance)
        active=timer.isActive();step=80 if horizontal else 96;target=self.targets.get(horizontal,bar.value()) if active else bar.value()
        if active and (target-bar.value())*amount>0:target=bar.value()
        self.targets[horizontal]=max(bar.minimum(),min(bar.maximum(),target-amount/120*step))
        if not active:timer.start()
        event.accept()


class ChangeRail(QScrollBar):
    """18px outside the grid: three colored lanes behind a translucent thumb."""
    def __init__(self,window,view,parent=None):
        super().__init__(Qt.Orientation.Vertical,parent);self.window=window;self.view=view;self.marks=[];self.revision=None;self.drag_offset=None;self.hover=False
        self.setFixedWidth(18);self.setMouseTracking(True);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip('드래그하여 스크롤 · 초록: 추가 / 주황: 수정 / 빨강: 삭제')
        bar=view.verticalScrollBar();bar.rangeChanged.connect(self.range_changed);bar.valueChanged.connect(self.setValue);self.valueChanged.connect(bar.setValue)
        self.range_changed(bar.minimum(),bar.maximum())
    def range_changed(self,low,high):self.setRange(low,high);self.update()
    def thumb_rect(self):
        bar=self.view.verticalScrollBar();page=max(1,bar.pageStep());length=max(28,self.height()*page/max(1,bar.maximum()-bar.minimum()+page));length=min(self.height(),length)
        top=(self.height()-length)*(self.value()-self.minimum())/max(1,self.maximum()-self.minimum())
        return QRectF(1,top,16,length)
    def marker_rects(self):
        w=self.window
        if not w.session:return []
        revision=(getattr(w,'review_revision',0),getattr(w,'geometry_revision',0),self.height(),self.view.verticalHeader().length())
        if revision==self.revision:return self.marks
        self.revision=revision;self.marks=w.rail_marks(self.height(),self.view);return self.marks
    def paintEvent(self,event):
        from PySide6.QtGui import QPixmap
        marks=self.marker_rects();revision=(self.revision,self.devicePixelRatioF())
        if getattr(self,'image_revision',None)!=revision:
            self.image_revision=revision;dpr=self.devicePixelRatioF();self.marker_image=QPixmap(round(self.width()*dpr),round(self.height()*dpr));self.marker_image.setDevicePixelRatio(dpr);self.marker_image.fill(Qt.GlobalColor.transparent)
            image_painter=QPainter(self.marker_image)
            for kind,rect in marks:image_painter.fillRect(rect,QColor(MARK_COLORS[kind]))
            image_painter.end()
        painter=QPainter(self);painter.drawPixmap(0,0,self.marker_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark=self.window.theme in ('dark','navy','charcoal');color=QColor('#b4c4d9' if dark else '#64748b')
        color.setAlpha(115 if self.hover or self.drag_offset is not None else 76)
        if self.maximum()==self.minimum():color.setAlpha(25)
        painter.setBrush(color);border=QColor('#cbd5e1' if dark else '#425269');border.setAlpha(100);painter.setPen(QPen(border,1));painter.drawRoundedRect(self.thumb_rect(),6,6);painter.end()
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        self.view.smooth.stop();thumb=self.thumb_rect();y=event.position().y();self.drag_offset=y-thumb.top() if thumb.contains(event.position()) else thumb.height()/2;self.move_thumb(y);event.accept()
    def move_thumb(self,y):
        travel=self.height()-self.thumb_rect().height()
        if travel>0:self.setValue(round((y-self.drag_offset)/travel*(self.maximum()-self.minimum())+self.minimum()))
        self.update()
    def mouseMoveEvent(self,event):
        if self.drag_offset is not None:self.move_thumb(event.position().y());event.accept()
    def mouseReleaseEvent(self,event):self.drag_offset=None;self.update();event.accept()
    def wheelEvent(self,event):self.view.smooth.wheel(event)
    def enterEvent(self,event):self.hover=True;self.update();super().enterEvent(event)
    def leaveEvent(self,event):self.hover=False;self.update();super().leaveEvent(event)


class ReviewPane(QWidget):
    def __init__(self,window,frame,view):
        super().__init__();self.view=view;self.frame=frame;box=QHBoxLayout(self);box.setContentsMargins(0,0,20,0);box.setSpacing(0);box.addWidget(frame)
        self.rail=ChangeRail(window,view,self);view.external_rail=self.rail;view.viewport().installEventFilter(self)
    def place(self):
        top=self.view.viewport().mapTo(self,QPoint(0,0)).y();self.rail.setGeometry(self.width()-18,top,18,self.view.viewport().height());self.rail.raise_();self.rail.update()
    def resizeEvent(self,event):super().resizeEvent(event);self.place()
    def eventFilter(self,watched,event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.Resize,QEvent.Type.Move):self.place()
        return False
