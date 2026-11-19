"""Native, resolution independent controls following the shared web layout."""
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPointF
from PySide6.QtGui import QIconEngine, QIcon, QPainter, QPen, QColor, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QButtonGroup, QFrame


class SymbolEngine(QIconEngine):
    def __init__(self, kind, color):
        super().__init__(); self.kind=kind; self.color=color
    def clone(self): return SymbolEngine(self.kind,self.color)
    def paint(self,painter,rect,mode,state):
        painter.save(); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(rect.x(),rect.y()); painter.scale(rect.width()/20,rect.height()/20)
        color=QColor(self.color)
        if mode==QIcon.Mode.Disabled: color.setAlpha(100)
        painter.setPen(QPen(color,1.6)); painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.kind=='검색':
            painter.drawEllipse(QRectF(3,3,10,10));painter.drawLine(12,12,18,18)
        elif self.kind in ('undo','redo'):
            if self.kind=='redo':painter.translate(20,0);painter.scale(-1,1)
            path=QPainterPath();path.moveTo(5,14);path.cubicTo(2,4,19,3,17,15);painter.drawPath(path)
            painter.drawLine(5,14,3,8);painter.drawLine(5,14,11,12)
        elif self.kind=='파일':
            path=QPainterPath();path.moveTo(2,6);path.lineTo(2,16);path.lineTo(18,16);path.lineTo(18,7);path.lineTo(9,7);path.lineTo(7.5,4.5);path.lineTo(2,4.5);path.closeSubpath();painter.drawPath(path)
        elif self.kind=='설정':
            for y,x in ((5,7),(10,13),(15,8)):painter.drawLine(2,y,18,y);painter.setBrush(QColor(self.color));painter.drawEllipse(QPointF(x,y),2,2);painter.setBrush(Qt.BrushStyle.NoBrush)
        elif self.kind=='표':
            painter.drawRoundedRect(QRectF(2.5,3.5,15,13),2,2);painter.drawLine(2,8,18,8);painter.drawLine(8,8,8,16.5)
        elif self.kind=='더보기':
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(color)
            for x in (4,10,16):painter.drawEllipse(QPointF(x,10),1.7,1.7)
        elif self.kind in ('접기','펼치기'):
            path=QPainterPath();path.moveTo(5,12 if self.kind=='접기' else 8);path.lineTo(10,7 if self.kind=='접기' else 13);path.lineTo(15,12 if self.kind=='접기' else 8);painter.drawPath(path)
        elif self.kind=='편집':
            body=QPainterPath();body.moveTo(4,16);body.lineTo(4.8,12.4);body.lineTo(13,4.2);body.lineTo(15.8,7);body.lineTo(7.6,15.2);body.closeSubpath();painter.drawPath(body);painter.drawLine(11.4,5.8,14.2,8.6)
        else:
            painter.drawEllipse(QRectF(2,2,16,16))
            if self.kind in ('추가','삭제'):painter.drawLine(6,10,14,10)
            if self.kind=='추가':painter.drawLine(10,6,10,14)
            if self.kind=='수정':
                painter.translate(10,10);painter.scale(.8,.8);painter.translate(-10,-10);painter.setPen(QPen(color,1.2));body=QPainterPath();body.moveTo(6,12);body.lineTo(12,6);body.lineTo(14,8);body.lineTo(8,14);body.lineTo(5,15);body.closeSubpath();painter.drawPath(body);painter.drawLine(11,7,13,9);painter.drawLine(6,12,8,14)
        painter.restore()
    def pixmap(self,size,mode,state):return self.scaledPixmap(size,mode,state,1)
    def scaledPixmap(self,size,mode,state,scale):
        result=QPixmap(size*scale);result.setDevicePixelRatio(scale);result.fill(Qt.GlobalColor.transparent)
        painter=QPainter(result);self.paint(painter,QRectF(0,0,size.width(),size.height()),mode,state);painter.end();return result


def symbol(kind,color):return QIcon(SymbolEngine(kind,color))


class Choices(QWidget):
    """Inline exclusive pills, with the small combo API used by the controller."""
    currentIndexChanged=Signal(int)
    def __init__(self,values,tips=()):
        super().__init__();self.values=list(values);self.buttons=[];self.group=QButtonGroup(self)
        box=QHBoxLayout(self);box.setContentsMargins(0,0,0,0);box.setSpacing(3)
        for i,value in enumerate(values):
            button=QToolButton();button.setText(value);button.setCheckable(True);button.setObjectName('choice')
            button.setToolTip(tips[i] if i<len(tips) else value);button.setToolTipDuration(15000)
            box.addWidget(button);self.group.addButton(button,i);self.buttons.append(button)
        self.buttons[0].setChecked(True);self.group.idClicked.connect(self.currentIndexChanged)
    def setCurrentIndex(self,index):
        if 0<=index<len(self.buttons):self.buttons[index].setChecked(True)
    def currentIndex(self):return self.group.checkedId()
    def currentText(self):return self.values[self.currentIndex()]
    def findText(self,text):return self.values.index(text) if text in self.values else -1


class ThemeButton(QToolButton):
    """The explicitly requested image preview; ordinary help stays Qt tooltips."""
    previews={}
    def __init__(self,theme):
        super().__init__();self.theme=theme;self.preview=None
        from PySide6.QtCore import QTimer
        self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.setInterval(70);self.preview_timer.timeout.connect(self.show_preview)
    def show_preview(self):
        import sys
        from pathlib import Path
        from PySide6.QtWidgets import QLabel
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]));path=root/'desktop'/'previews'/(self.theme+'.png')
        if not path.exists():return
        if self.preview is None:
            self.preview=QLabel(self,Qt.WindowType.ToolTip|Qt.WindowType.FramelessWindowHint);self.preview.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating);self.preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);self.preview.setMargin(3)
        # Read and scale each theme image once; hovering again then only has to show the cached pixmap.
        pixmap=ThemeButton.previews.get(self.theme)
        if pixmap is None:pixmap=ThemeButton.previews[self.theme]=QPixmap(str(path)).scaled(QSize(400,250),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(pixmap);self.preview.adjustSize()
        screen=self.screen().availableGeometry();point=self.mapToGlobal(self.rect().bottomLeft());point.setX(max(screen.left(),min(point.x(),screen.right()-self.preview.width())));point.setY(max(screen.top(),min(point.y()+6,screen.bottom()-self.preview.height())))
        self.preview.move(point);self.preview.show();self.preview.raise_()
    def hide_preview(self):
        self.preview_timer.stop()
        if self.preview:self.preview.hide()
    def enterEvent(self,event):self.preview_timer.start();super().enterEvent(event)
    def leaveEvent(self,event):self.hide_preview();super().leaveEvent(event)
    def focusInEvent(self,event):self.preview_timer.start();super().focusInEvent(event)
    def focusOutEvent(self,event):self.hide_preview();super().focusOutEvent(event)
    def hideEvent(self,event):self.hide_preview();super().hideEvent(event)


class SearchEdit(__import__('PySide6.QtWidgets',fromlist=['QLineEdit']).QLineEdit):
    compositionChanged=Signal(bool)
    def __init__(self):super().__init__();self.composing=False
    def inputMethodEvent(self,event):
        self.composing=bool(event.preeditString());self.compositionChanged.emit(self.composing);super().inputMethodEvent(event)


class PopupMotion:
    """Combo drop-downs open instantly, kept inside the screen below or above the box."""
    def showPopup(self):
        super().showPopup()
        popup=self.view().window()
        screen=self.screen().availableGeometry();below=self.mapToGlobal(self.rect().bottomLeft());above=self.mapToGlobal(self.rect().topLeft())
        height=min(popup.height(),max(screen.bottom()-below.y(),above.y()-screen.top()));popup.resize(max(self.width(),popup.width()),height)
        popup.move(max(screen.left(),min(below.x(),screen.right()-popup.width())),below.y()+1 if screen.bottom()-below.y()>=height else above.y()-height)
        self.view().setCurrentIndex(self.model().index(self.currentIndex(),self.modelColumn(),self.rootModelIndex()))


from PySide6.QtWidgets import QComboBox,QFontComboBox
from PySide6.QtWidgets import QStyledItemDelegate
class FontNameDelegate(QStyledItemDelegate):
    """Qt appends a sample string after each family name; show only the name."""
    def initStyleOption(self,option,index):
        super().initStyleOption(option,index);option.text=str(index.data(Qt.ItemDataRole.DisplayRole) or '')
    def paint(self,painter,option,index):
        from PySide6.QtWidgets import QStyleOptionViewItem,QStyle
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);style=opt.widget.style() if opt.widget else None
        if style:style.drawControl(QStyle.ControlElement.CE_ItemViewItem,opt,painter,opt.widget)
    def sizeHint(self,option,index):
        size=super().sizeHint(option,index);size.setHeight(max(size.height(),30));return size


class AnimatedCombo(PopupMotion,QComboBox):pass
class AnimatedFontCombo(PopupMotion,QFontComboBox):
    def __init__(self,*args):
        super().__init__(*args);self.view().setItemDelegate(FontNameDelegate(self.view()))


class CountButton(QToolButton):
    def __init__(self):
        super().__init__();self.setMinimumWidth(80)
        from PySide6.QtWidgets import QLabel
        self.icon_label=QLabel();self.icon_label.setFixedWidth(18);self.number_label=QLabel();self.number_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter);box=QHBoxLayout(self);box.setContentsMargins(10,0,10,0);box.setSpacing(5);box.addWidget(self.icon_label);box.addWidget(self.number_label,1)
        for label in [self.icon_label,self.number_label]:label.setStyleSheet('border:0;background:transparent;padding:0;min-height:0');label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def setText(self,text):self.number_label.setText(text);self.setAccessibleName(self.toolTip()+' '+text)
    def text(self):return self.number_label.text()
    def setIcon(self,icon):self.icon_label.setPixmap(icon.pixmap(QSize(18,18)))


class Divider(QFrame):
    """Thin vertical separator between toolbar groups (colour comes from QFrame#divider in the theme)."""
    def __init__(self):
        super().__init__();self.setObjectName('divider');self.setFixedSize(1,22);self.setFrameShape(QFrame.Shape.NoFrame)


class BusyOverlay(QWidget):
    """Dim the window while a background job runs, with a moving bar, elapsed seconds and (optionally) Cancel."""
    cancelled=Signal()
    def __init__(self,parent):
        from PySide6.QtCore import QTimer,QElapsedTimer
        from PySide6.QtWidgets import QProgressBar,QLabel,QVBoxLayout,QFrame
        super().__init__(parent);self.setObjectName('busyOverlay');self.hide()
        self.delay=QTimer(self);self.delay.setSingleShot(True);self.delay.setInterval(100);self.delay.timeout.connect(self.reveal)
        self.tick=QTimer(self);self.tick.setInterval(500);self.tick.timeout.connect(self.update_text);self.clock=QElapsedTimer();self.label_text=''
        self.panel=QFrame(self);self.panel.setObjectName('busyPanel');box=QVBoxLayout(self.panel);box.setContentsMargins(24,20,24,20);box.setSpacing(12)
        self.label=QLabel();self.label.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(self.label)
        self.bar=QProgressBar();self.bar.setRange(0,0);self.bar.setTextVisible(False);self.bar.setFixedHeight(8);box.addWidget(self.bar)
        self.cancel=QToolButton();self.cancel.setText('취소');self.cancel.setToolTip('작업을 중단하고 이전 상태로 돌아갑니다.');self.cancel.clicked.connect(self.cancelled);box.addWidget(self.cancel,0,Qt.AlignmentFlag.AlignCenter)
        self.panel.setMinimumWidth(320)
    def start(self,text,cancellable):
        self.label_text=text;self.cancel.setVisible(cancellable);self.clock.start();self.update_text();self.delay.start()
    def reveal(self):
        self.setGeometry(self.parentWidget().rect());self.panel.adjustSize();self.panel.move((self.width()-self.panel.width())//2,(self.height()-self.panel.height())//2)
        self.show();self.raise_();self.tick.start()
    def reveal_now(self):
        self.cancel.hide()
        if not self.isVisible():self.delay.stop();self.reveal()
    def stop(self):
        self.delay.stop();self.tick.stop();self.hide()
    def update_text(self):
        seconds=self.clock.elapsed()//1000;self.label.setText(self.label_text+(f'  {seconds}초' if seconds>=1 else ''))
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor(0,0,0,70));painter.end()
    def mousePressEvent(self,event):event.accept()
    def mouseReleaseEvent(self,event):event.accept()
    def wheelEvent(self,event):event.accept()


class DropOverlay(QWidget):
    """Two drop targets shown while files are dragged over the window: original (left), comparison (right)."""
    def __init__(self,parent):
        super().__init__(parent);self.setObjectName('dropOverlay');self.hide();self.zone=0;self.colors={'panel':'#f3f6fa','text':'#243247','muted':'#64748b'}
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def show_over(self,tokens):
        self.colors={'panel':tokens['panel'],'text':tokens['text'],'muted':tokens['muted']};self.zone=0;self.setGeometry(self.parentWidget().rect());self.show();self.raise_()
    def zone_at(self,x):return 0 if x<self.width()/2 else 1
    def set_zone(self,zone):
        if zone!=self.zone:self.zone=zone;self.update()
    def paintEvent(self,event):
        from PySide6.QtCore import QRectF
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.fillRect(self.rect(),QColor(0,0,0,60))
        half=self.width()/2;titles=[('원본','파일 1개를 놓으세요'),('비교 파일','여러 개를 한꺼번에 놓을 수 있어요')]
        for index,(title,hint) in enumerate(titles):
            rect=QRectF(index*half+24,24,half-48,self.height()-48);active=index==self.zone
            fill=QColor('#2563eb' if active else self.colors['panel']);fill.setAlpha(205 if active else 215);painter.setBrush(fill)
            pen=QPen(QColor('#60a5fa' if active else self.colors['muted']),2,Qt.PenStyle.DashLine);painter.setPen(pen);painter.drawRoundedRect(rect,14,14)
            painter.setPen(QColor('white' if active else self.colors['text']));font=painter.font();font.setPixelSize(26);font.setBold(True);painter.setFont(font)
            painter.drawText(rect.adjusted(0,0,0,-20),Qt.AlignmentFlag.AlignCenter,title)
            font.setPixelSize(14);font.setBold(False);painter.setFont(font);painter.drawText(rect.adjusted(0,50,0,0),Qt.AlignmentFlag.AlignCenter,hint)
        painter.end()


class WelcomeCard(QWidget):
    """First screen: explains what to do instead of three blank tables."""
    openRequested=Signal()
    def __init__(self,parent):
        from PySide6.QtWidgets import QLabel,QVBoxLayout,QFrame
        super().__init__(parent);self.setObjectName('welcome');self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        box=QVBoxLayout(self);box.setContentsMargins(40,32,40,32);box.setSpacing(16)
        title=QLabel('비교할 엑셀 파일을 불러오세요');title.setObjectName('welcomeTitle');title.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(title)
        sub=QLabel('원본과 비교 파일을 창에 끌어다 놓거나 아래 [파일 열기]를 누르세요.');sub.setObjectName('welcomeSub');sub.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(sub)
        row=QHBoxLayout();row.setSpacing(16)
        for head,hint in (('① 원본','기준이 되는 파일 1개'),('② 비교 파일','바뀐 내용이 담긴 파일 (여러 개 가능)')):
            zone=QFrame();zone.setObjectName('welcomeZone');inner=QVBoxLayout(zone);inner.setContentsMargins(16,24,16,24);inner.setSpacing(6)
            a=QLabel(head);a.setObjectName('welcomeZoneTitle');a.setAlignment(Qt.AlignmentFlag.AlignCenter);b=QLabel(hint);b.setObjectName('welcomeSub');b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(a);inner.addWidget(b);row.addWidget(zone)
        box.addLayout(row)
        self.open_button=QToolButton();self.open_button.setObjectName('primary');self.open_button.setText('파일 열기');self.open_button.clicked.connect(self.openRequested);box.addWidget(self.open_button,0,Qt.AlignmentFlag.AlignCenter)
        tips=QLabel('연습해 보려면  더보기 → 테스트 샘플');tips.setObjectName('welcomeSub');tips.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(tips)
        self.hide()
