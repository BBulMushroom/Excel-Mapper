"""Native dialogs use standard Qt tooltips and open only when requested."""
import json
from pathlib import Path
import time
from PySide6.QtCore import Qt,QEvent,QRect,QTimer
from PySide6.QtGui import QFont,QColor
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QCheckBox,QComboBox,QLineEdit,QSpinBox,QTableWidget,QTableWidgetItem,QMessageBox,QListWidget,QListWidgetItem,QFileDialog,QInputDialog,QPushButton,QFontComboBox,QWidget,QGridLayout,QToolButton,QButtonGroup,QApplication,QHeaderView,QAbstractItemView,QStyledItemDelegate)
import comparison_rules
from compare import sheet_names,is_sequence
from settings_store import FileSettingsStore,import_settings,export_settings
from display_theme import palettes
from .widgets import ThemeButton,AnimatedCombo as QComboBox,AnimatedFontCombo as QFontComboBox


class Dialog(QDialog):
    def __init__(self,parent,title):
        super().__init__(parent,Qt.WindowType.Popup);self.setWindowTitle(title);self.setObjectName('popover');self.setMinimumWidth(440);self.setToolTipDuration(15000);self.body=QVBoxLayout(self);self.body.setContentsMargins(16,16,16,16);self.body.setSpacing(12)
        # A new top-level window can flash black before its first frame is painted: stay invisible until then.
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground,False);self.setAutoFillBackground(True);self.setWindowOpacity(0.0)
    def reveal_after_first_paint(self):
        try:self.repaint();self.setWindowOpacity(1.0)
        except RuntimeError:pass
    def showEvent(self,event):
        super().showEvent(event)
        QTimer.singleShot(0,self.reveal_after_first_paint)
        if not self.isWindow():return
        owner=self.parentWidget();self.request_key=getattr(owner,'popup_request',None);owner.active_popover=self;QApplication.instance().installEventFilter(self);anchor=getattr(owner,'popup_anchor',None)
        if not anchor:anchor=getattr(owner,'rules_button',None)
        self.anchor=anchor
        self.trigger_rect=getattr(owner,'popup_trigger_rect',None) or (QRect(anchor.mapToGlobal(anchor.rect().topLeft()),anchor.size()) if anchor else QRect())
        if anchor:
            point=getattr(owner,'popup_position',None) or anchor.mapToGlobal(anchor.rect().bottomLeft());screen=anchor.screen().availableGeometry()
            self.move(max(screen.left(),min(point.x(),screen.right()-self.width())),max(screen.top(),min(point.y()+6,screen.bottom()-self.height())))
        if anchor:getattr(anchor,'viewport',lambda:anchor)().update()
    def exec(self):
        result=super().exec()
        # Callers can read the accepted fields before the next event turn.
        QTimer.singleShot(0,self.deleteLater)
        return result
    def eventFilter(self,watched,event):
        if self.isWindow() and self.isVisible() and event.type()==QEvent.Type.MouseButtonPress:
            point=event.globalPosition().toPoint()
            if not self.frameGeometry().contains(point) and self.trigger_rect.contains(point):
                # Eat only a repeated trigger; other buttons retain Qt's replay.
                self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay,True);self.reject();return True
        return False
    def hideEvent(self,event):
        QApplication.instance().removeEventFilter(self)
        owner=self.parentWidget()
        if getattr(owner,'active_popover',None) is self:owner.active_popover=None;owner.closed_popover=(self.request_key,time.monotonic())
        if getattr(self,'anchor',None):getattr(self.anchor,'viewport',lambda:self.anchor)().update()
        super().hideEvent(event)
    def buttons(self,validate=None):
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('적용');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('취소')
        buttons.accepted.connect(validate or self.accept);buttons.rejected.connect(self.reject);self.body.addWidget(buttons)
    def error(self,error):QMessageBox.warning(self,'확인',str(error))


class RulesDialog(Dialog):
    def __init__(self,parent,rules):
        super().__init__(parent,'비교 설정');self.rules=rules
        self.case=QCheckBox('대소문자 무시');self.case.setChecked(rules['ignore_case']);self.case.setToolTip('ABC와 abc를 같은 값으로 봅니다. 기준 키·수식은 제외합니다.')
        self.trim=QCheckBox('앞뒤 공백 무시');self.trim.setChecked(rules['trim']);self.trim.setToolTip('값 양끝의 공백만 무시합니다.')
        self.body.addWidget(self.case);self.body.addWidget(self.trim)
        form=QFormLayout();self.mode=QComboBox();self.mode.addItems(['연/월/일','월/일/년','일/월/년','사용자 설정']);self.mode.setCurrentIndex(comparison_rules.DATE_MODES.index(rules['dates']));form.addRow('날짜 읽는 형식',self.mode)
        self.example=QLabel();self.example.setObjectName('supportText');self.body.addLayout(form);self.body.addWidget(self.example)
        self.pattern=QLineEdit(rules['date_pattern']);self.pattern.setPlaceholderText('YYYYMMDD');self.pattern.setToolTip('YYYY/YY: 연도, MM: 월, DD: 일 · YY는 2000~2099년');self.body.addWidget(self.pattern)
        self.ignore=QCheckBox('날짜 표기 차이 무시');self.ignore.setChecked(rules['ignore_date_format']);self.body.addWidget(self.ignore);self.date_help=QLabel('예: 2026-11-02와 2026/11/02를 같은 날짜로 봅니다.');self.date_help.setObjectName('supportText');self.date_help.setWordWrap(True);self.body.addWidget(self.date_help)
        self.mode.currentIndexChanged.connect(self.example_changed);self.example_changed();self.buttons(self.submit)
    def example_changed(self):
        i=self.mode.currentIndex();self.pattern.setVisible(i==3);self.example.setText(['예: 2026-11-02, 2026/11/02','예: 11/02/2026 → 2026년 11월 2일','예: 02/11/2026 → 2026년 11월 2일','YYYYMMDD → 20261102 · YY-MM-DD → 26-11-02'][i])
    def submit(self):
        try:self.rules=comparison_rules.clean({'ignore_case':self.case.isChecked(),'trim':self.trim.isChecked(),'dates':comparison_rules.DATE_MODES[self.mode.currentIndex()],'date_pattern':self.pattern.text(),'ignore_date_format':self.ignore.isChecked()});self.accept()
        except ValueError as exc:self.error(exc)


class RangesDialog(Dialog):
    def __init__(self,parent,s):
        super().__init__(parent,'데이터 위치');self.fields={};row=QHBoxLayout();self.body.addLayout(row)
        for side,label,data in [('old','원본',s.old),('new','비교',s.new)]:
            form=QFormLayout();form.addRow(QLabel(label));sheet=QComboBox();sheet.addItems([n for n in sheet_names(data) if n!='변경 이력']);sheet.setCurrentText(s.layout[side+'_sheet']);form.addRow('시트',sheet);self.fields[side+'_sheet']=sheet
            for suffix,title,minimum in [('header','제목 행',1),('start','시작 행',2)]:
                value=QSpinBox();value.setRange(minimum,1048576);value.setValue(s.layout[side+'_'+suffix]);value.setToolTip('엑셀 파일에서 '+title+'의 실제 행 번호입니다.');form.addRow(title,value);self.fields[side+'_'+suffix]=value
            row.addLayout(form)
        self.buttons()
    def values(self):return {k:v.currentText() if k.endswith('sheet') else v.value() for k,v in self.fields.items()}


class KeyChoice(QTableWidgetItem):
    def __init__(self,on):
        super().__init__('');self.setFlags(Qt.ItemFlag.ItemIsEnabled);self.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
    def isChecked(self):return self.checkState()==Qt.CheckState.Checked


class KeyChoiceDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        from PySide6.QtWidgets import QStyleOptionButton,QStyle
        from PySide6.QtCore import QSize
        check=QStyleOptionButton();check.palette=option.palette;check.rect=QRect(option.rect.center()-__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(8,8),QSize(16,16));check.state=QStyle.StateFlag.State_Enabled|(QStyle.StateFlag.State_On if index.data(Qt.ItemDataRole.CheckStateRole) in (Qt.CheckState.Checked,Qt.CheckState.Checked.value) else QStyle.StateFlag.State_Off)
        option.widget.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,check,painter,option.widget)
    def editorEvent(self,event,model,option,index):return False


class SortItem(QTableWidgetItem):
    """Sorts by the value stored in UserRole (column order, status rank) instead of the shown text."""
    def __lt__(self,other):
        a,b=self.data(Qt.ItemDataRole.UserRole+1),other.data(Qt.ItemDataRole.UserRole+1)
        return a<b if a is not None and b is not None else super().__lt__(other)


class TargetDelegate(QStyledItemDelegate):
    """Comparison column chooser: a searchable drop-down that only exists while a cell is being edited."""
    def __init__(self,dialog):super().__init__(dialog.table);self.dialog=dialog
    def createEditor(self,parent,option,index):
        from PySide6.QtWidgets import QCompleter
        editor=QComboBox(parent);editor.setEditable(True);editor.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        row=index.row();owners=self.dialog.owners(exclude=row)
        editor.addItem('연결 안 함','')
        for h in self.dialog.right_headers:editor.addItem(h+(f'   (이미 연결: {owners[h]})' if h in owners else ''),h)
        completer=QCompleter([editor.itemText(n) for n in range(editor.count())],editor);completer.setFilterMode(Qt.MatchFlag.MatchContains);completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive);editor.setCompleter(completer)
        return editor
    def setEditorData(self,editor,index):
        editor.setCurrentIndex(max(0,editor.findData(index.data(Qt.ItemDataRole.UserRole) or '')))
        def open_list():
            try:editor.showPopup()
            except RuntimeError:pass       # the editor was closed before the list could open
        QTimer.singleShot(0,open_list)
    def setModelData(self,editor,model,index):
        text=editor.currentText().split('   (이미 연결:')[0].strip();choice=editor.itemData(editor.findText(editor.currentText())) if editor.findText(editor.currentText())>=0 else None
        if choice is None:choice=text if text in self.dialog.right_headers else None
        if choice is not None:self.dialog.choose(index.row(),choice)


class MappingDialog(Dialog):
    """Original columns with their key flag and linked comparison column; search, views and bulk actions for wide sheets."""
    VIEWS=['전체','연결됨','연결 안 함','이름이 다르게 연결됨','기준 키']
    LINK,KEY,LETTER,NAME,TARGET,STATUS=range(6)
    def __init__(self,parent,s):
        from openpyxl.utils import get_column_letter
        from ui_helpers import suggested_mapping
        from PySide6.QtWidgets import QAbstractItemView
        super().__init__(parent,'기준 키·열 연결');self.resize(880,600);self.s=s;self.updating=False;self.note=''
        self.right_headers=[h for h in s.right.headers if not is_sequence(h)]
        try:self.auto=suggested_mapping(s.left,s.right)
        except Exception:self.auto={}
        bar=QHBoxLayout();self.body.addLayout(bar)
        self.search=QLineEdit();self.search.setPlaceholderText('열 이름 검색 (원본·비교)');self.search.setClearButtonEnabled(True);bar.addWidget(self.search,3)
        self.view=QComboBox();self.view.addItems(self.VIEWS);bar.addWidget(self.view,1)
        self.summary=QLabel();bar.addWidget(self.summary)
        tools=QHBoxLayout();self.body.addLayout(tools)
        for text,tip,action in [('보이는 열 모두 연결','검색·보기 결과에 보이는 열을 모두 연결합니다. 고른 비교 열이 없으면 이름이 맞는 열로 연결합니다.',lambda:self.link_rows(self.visible_rows(),True)),
                                ('보이는 열 모두 해제','검색·보기 결과에 보이는 열의 연결을 모두 끊습니다. 기준 키 열은 그대로 둡니다.',lambda:self.link_rows(self.visible_rows(),False)),
                                ('자동 연결로 되돌리기','모든 열을 처음 자동으로 고른 연결로 되돌립니다.',self.reset_auto)]:
            button=QPushButton(text);button.setToolTip(tip);button.clicked.connect(action);tools.addWidget(button)
        tools.addStretch()
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['연결','기준 키','열','원본 열 이름','비교 열','상태'])
        self.table.verticalHeader().hide();self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked|QAbstractItemView.EditTrigger.DoubleClicked);self.table.setItemDelegateForColumn(self.TARGET,TargetDelegate(self))
        for col,width in enumerate([64,64,44,230,250]):self.table.setColumnWidth(col,width)
        self.table.horizontalHeader().setStretchLastSection(True);self.table.horizontalHeader().setSectionsClickable(True);self.table.horizontalHeader().sectionClicked.connect(self.sort_by);self.sorted=(None,Qt.SortOrder.AscendingOrder)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.table.customContextMenuRequested.connect(self.menu);self.table.installEventFilter(self)
        columns=[(n,h) for n,h in enumerate(s.headers,1) if not is_sequence(h)]
        self.table.setRowCount(len(columns))
        for row,(number,name) in enumerate(columns):
            target=s.mapping.get(name,'')
            link=SortItem();link.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsSelectable);link.setCheckState(Qt.CheckState.Checked if target else Qt.CheckState.Unchecked)
            key=SortItem();key.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsSelectable);key.setCheckState(Qt.CheckState.Checked if name in s.keys else Qt.CheckState.Unchecked)
            letter=SortItem(get_column_letter(number));letter.setData(Qt.ItemDataRole.UserRole+1,number)
            label=SortItem(name);label.setData(Qt.ItemDataRole.UserRole,name);label.setData(Qt.ItemDataRole.UserRole+1,number)
            chosen=SortItem();chosen.setData(Qt.ItemDataRole.UserRole,target or self.auto.get(name,''));chosen.setToolTip('누르면 비교 열을 고를 수 있습니다. 입력해서 찾을 수 있습니다.')
            for col,item in enumerate([link,key,letter,label,chosen,SortItem()]):
                if col not in (self.LINK,self.KEY):item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|(Qt.ItemFlag.ItemIsEditable if col==self.TARGET else Qt.ItemFlag.NoItemFlags))
                self.table.setItem(row,col,item)
        self.table.itemChanged.connect(self.changed);self.search.textChanged.connect(self.apply);self.view.currentIndexChanged.connect(self.apply)
        self.body.addWidget(self.table);self.buttons(self.check);self.apply()
    # --- state ---------------------------------------------------------------------------------
    def name(self,row):return self.table.item(row,self.NAME).data(Qt.ItemDataRole.UserRole)
    def target(self,row):return self.table.item(row,self.TARGET).data(Qt.ItemDataRole.UserRole) or ''
    def linked(self,row):return self.table.item(row,self.LINK).checkState()==Qt.CheckState.Checked
    def is_key(self,row):return self.table.item(row,self.KEY).checkState()==Qt.CheckState.Checked
    def owners(self,exclude=None):return {self.target(r):self.name(r) for r in range(self.table.rowCount()) if r!=exclude and self.linked(r) and self.target(r)}
    def set_linked(self,row,on):self.table.item(row,self.LINK).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
    def choose(self,row,target):
        """Pick a comparison column for one row; a column already used elsewhere moves here."""
        self.updating=True
        try:
            if target:
                for other in range(self.table.rowCount()):
                    if other!=row and self.linked(other) and self.target(other)==target:
                        self.set_linked(other,False);self.note=f"비교 '{target}' 연결을 '{self.name(other)}'에서 옮겼습니다."
            self.table.item(row,self.TARGET).setData(Qt.ItemDataRole.UserRole,target);self.set_linked(row,bool(target))
        finally:self.updating=False
        self.apply()
    def changed(self,item):
        if self.updating:return
        row=item.row();self.updating=True
        try:
            if item.column()==self.LINK and self.linked(row):
                if not self.target(row):self.set_linked(row,False);self.note=f"'{self.name(row)}'에 연결할 비교 열을 먼저 고르세요(비교 열 칸을 누르세요)."
                else:self.choose_conflicts(row)
            elif item.column()==self.LINK and self.is_key(row):self.set_linked(row,True);self.note='기준 키 열은 연결을 끊을 수 없습니다. 먼저 기준 키 표시를 해제하세요.'
            elif item.column()==self.KEY and self.is_key(row) and not self.linked(row):
                if self.target(row):self.set_linked(row,True);self.choose_conflicts(row)
                else:self.table.item(row,self.KEY).setCheckState(Qt.CheckState.Unchecked);self.note='기준 키는 비교 열이 연결된 열에서만 고를 수 있습니다.'
        finally:self.updating=False
        self.apply()
    def choose_conflicts(self,row):
        target=self.target(row)
        for other in range(self.table.rowCount()):
            if other!=row and self.linked(other) and self.target(other)==target:
                self.set_linked(other,False);self.note=f"비교 '{target}' 연결을 '{self.name(other)}'에서 옮겼습니다."
    def toggle_key(self,row,col=1):
        item=self.table.item(row,self.KEY);item.setCheckState(Qt.CheckState.Unchecked if self.is_key(row) else Qt.CheckState.Checked)
    def link_rows(self,rows,on):
        self.updating=True;skipped=0
        try:
            for row in rows:
                if on and not self.linked(row):
                    if not self.target(row):
                        guess=self.auto.get(self.name(row)) or (self.name(row) if self.name(row) in self.right_headers else '')
                        if not guess:skipped+=1;continue
                        self.table.item(row,self.TARGET).setData(Qt.ItemDataRole.UserRole,guess)
                    self.set_linked(row,True);self.choose_conflicts(row)
                elif not on and self.linked(row) and not self.is_key(row):self.set_linked(row,False)
            if skipped:self.note=f'맞는 비교 열을 찾지 못해 {skipped}개 열은 연결하지 않았습니다. 비교 열 칸을 눌러 직접 고르세요.'
        finally:self.updating=False
        self.apply()
    def reset_auto(self):
        self.updating=True
        try:
            for row in range(self.table.rowCount()):
                target=self.auto.get(self.name(row),'')
                if self.is_key(row) and not target:continue
                self.table.item(row,self.TARGET).setData(Qt.ItemDataRole.UserRole,target);self.set_linked(row,bool(target))
            self.note='자동 연결로 되돌렸습니다.'
        finally:self.updating=False
        self.apply()
    def status(self,row):
        name,target=self.name(row),self.target(row)
        if not self.linked(row):return '연결 안 함',4
        if self.is_key(row):return '기준 키',0
        if target==name:return '이름 같음',3
        if target==self.auto.get(name):return '자동 · 이름 다름',1
        return '직접 연결',2
    def visible_rows(self):return [r for r in range(self.table.rowCount()) if not self.table.isRowHidden(r)]
    def apply(self):
        tokens=self.parent().tokens;query=self.search.text().strip().casefold();mode=self.view.currentText();shown=0;self.updating=True
        try:
            for row in range(self.table.rowCount()):
                text,rank=self.status(row);linked=self.linked(row);target=self.target(row)
                status=self.table.item(row,self.STATUS);status.setText(text);status.setData(Qt.ItemDataRole.UserRole+1,rank)
                status.setForeground(QColor(tokens['edit-text'] if rank in (1,2) else tokens['muted'] if rank==4 else tokens['text']))
                cell=self.table.item(row,self.TARGET);cell.setText(target if target else '—');cell.setData(Qt.ItemDataRole.UserRole+1,(not linked,target))
                cell.setForeground(QColor(tokens['text'] if linked else tokens['muted']))
                self.table.item(row,self.LINK).setData(Qt.ItemDataRole.UserRole+1,int(not linked));self.table.item(row,self.KEY).setData(Qt.ItemDataRole.UserRole+1,int(not self.is_key(row)))
                ok=(not query or query in self.name(row).casefold() or query in target.casefold()) and (mode=='전체' or mode=='연결됨' and linked or mode=='연결 안 함' and not linked or mode=='이름이 다르게 연결됨' and rank in (1,2) or mode=='기준 키' and self.is_key(row))
                self.table.setRowHidden(row,not ok);shown+=ok
        finally:self.updating=False
        total=self.table.rowCount();linked=sum(self.linked(r) for r in range(total));keys=sum(self.is_key(r) for r in range(total))
        self.summary.setText(f'연결 {linked} / 원본 열 {total} · 기준 키 {keys} · 보이는 열 {shown}'+(f'\n{self.note}' if self.note else ''));self.note=''
    def sort_by(self,column):
        order=Qt.SortOrder.DescendingOrder if self.sorted==(column,Qt.SortOrder.AscendingOrder) else Qt.SortOrder.AscendingOrder
        self.sorted=(column,order);self.table.sortItems(column,order)
        labels=['연결','기준 키','열','원본 열 이름','비교 열','상태']
        self.table.setHorizontalHeaderLabels([t+((' ↑' if order==Qt.SortOrder.AscendingOrder else ' ↓') if n==column else '') for n,t in enumerate(labels)])
    def selected(self):return sorted({i.row() for i in self.table.selectedIndexes()})
    def menu(self,point):
        from PySide6.QtWidgets import QMenu
        rows=self.selected() or ([self.table.rowAt(point.y())] if self.table.rowAt(point.y())>=0 else [])
        if not rows:return
        menu=QMenu(self);menu.addAction(f'선택한 열 연결 ({len(rows)})',lambda:self.link_rows(rows,True));menu.addAction(f'선택한 열 연결 안 함 ({len(rows)})',lambda:self.link_rows(rows,False))
        if len(rows)==1:menu.addSeparator();menu.addAction('기준 키 해제' if self.is_key(rows[0]) else '이 열을 기준 키로',lambda:self.toggle_key(rows[0]))
        menu.exec(self.table.viewport().mapToGlobal(point))
    def eventFilter(self,watched,event):
        if watched is self.table and event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Space and self.selected():
            rows=self.selected();self.link_rows(rows,not all(self.linked(r) for r in rows));return True
        return super().eventFilter(watched,event)
    def check(self):
        keys,mapping=self.values()
        if not keys:self.error('기준 키를 하나 이상 고르세요. 행을 구분할 열(예: 자산코드)의 기준 키 칸을 체크하세요.');return
        self.accept()
    def values(self):
        rows=range(self.table.rowCount())
        return [self.name(r) for r in sorted(rows,key=lambda r:self.table.item(r,self.LETTER).data(Qt.ItemDataRole.UserRole+1)) if self.is_key(r) and self.linked(r)],{self.name(r):self.target(r) for r in rows if self.linked(r) and self.target(r)}


class FilterDialog(Dialog):
    def __init__(self,parent,s,pane,col):
        super().__init__(parent,{'__row__':'행','__key__':'기준값'}.get(col,col)+' 정렬·필터');self.setMinimumWidth(300);self.resize(340,520);self.pane=pane
        sort=QHBoxLayout();self.body.addLayout(sort)
        for label,descending in [('오름차순',False),('내림차순',True)]:
            button=QPushButton(label);sort.addWidget(button)
            button.clicked.connect(lambda checked=False,d=descending:(parent.mutate(lambda s:s.set_view_sort((pane,col,d))),self.reject()))
        reset_sort=QPushButton('정렬 해제');self.body.addWidget(reset_sort);reset_sort.clicked.connect(lambda:(parent.mutate(lambda s:s.set_view_sort(None)),self.reject()))
        clear=QPushButton('이 열 필터 지우기');self.body.addWidget(clear);clear.clicked.connect(lambda:(parent.mutate(lambda s:s.filters.pop(col,None)),self.reject()))
        self.op=QComboBox();self.op.addItems(['선택값','포함','포함하지 않음','같음','같지 않음','시작 문자','끝 문자','빈 셀','빈 셀 아님','보다 큼','크거나 같음','보다 작음','작거나 같음','추가만','수정만','삭제만']);self.body.addWidget(self.op)
        self.text=QLineEdit();self.text.setPlaceholderText('검색 또는 조건값');self.body.addWidget(self.text)
        self.all=QCheckBox('전체 선택');self.all.setChecked(True);self.body.addWidget(self.all)
        self.items=QListWidget();self.items.setUniformItemSizes(True);self.body.addWidget(self.items)
        values=sorted({s.value(i,pane,col) for i in range(len(s.rows))},key=s.sort_value)
        old=s.filters.get(col);
        if old:self.op.setCurrentText(old.get('op','선택값'));self.text.setText(old.get('text',''))
        picked=set(old['values']) if old and old.get('op')=='선택값' else set(values)
        for value in values:
            item=QListWidgetItem(value or '(빈 셀)');item.setData(Qt.ItemDataRole.UserRole,value);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked if value in picked else Qt.CheckState.Unchecked);self.items.addItem(item)
        self.text.textChanged.connect(self.search);self.all.toggled.connect(self.select_all);self.op.currentTextChanged.connect(self.resize_condition);self.items.setVisible(self.op.currentText()=='선택값');self.buttons();self.resize_condition(self.op.currentText())
    def resize_condition(self,name):
        selected=name=='선택값';self.items.setVisible(selected);self.all.setVisible(selected);self.text.setVisible(name not in ('빈 셀','빈 셀 아님','추가만','수정만','삭제만'));self.body.setSizeConstraint(__import__('PySide6.QtWidgets',fromlist=['QLayout']).QLayout.SizeConstraint.SetMinimumSize);self.body.activate();self.resize(self.width(),520 if selected else self.sizeHint().height())
    def select_all(self,on):
        for i in range(self.items.count()):
            item=self.items.item(i)
            if not item.isHidden():item.setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
    def search(self,text):
        if self.op.currentText()=='선택값':
            for i in range(self.items.count()):self.items.item(i).setHidden(text.casefold() not in self.items.item(i).text().casefold())
    def values(self):
        return {'pane':self.pane,'op':self.op.currentText(),'text':self.text.text(),'values':[self.items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.items.count()) if self.items.item(i).checkState()==Qt.CheckState.Checked and not self.items.item(i).isHidden()]}


class ScreenDialog(Dialog):
    def __init__(self,parent):
        super().__init__(parent,'화면 설정');form=QFormLayout();self.theme=QComboBox()
        for id,p in palettes().items():self.theme.addItem(p['label'],id)
        self.theme.setCurrentIndex(self.theme.findData(parent.theme));self.theme.hide()
        grid=QGridLayout();self.theme_group=QButtonGroup(self)
        for i,(name,palette) in enumerate(palettes().items()):
            button=ThemeButton(name);button.setText(palette['label']);button.setCheckable(True);button.setChecked(name==parent.theme);button.setToolTip(palette['label']);button.setMinimumWidth(130);t=palette['tokens'];button.setStyleSheet("QToolButton{background:"+t['input']+";color:"+t['text']+";border:2px solid "+t['border']+";border-radius:6px;padding:6px 10px;min-height:20px}QToolButton:hover{background:"+t['hover']+";color:"+t['text']+"}QToolButton:checked{background:"+t['input']+";color:"+t['text']+";border:2px solid #2563eb;font-weight:600}");grid.addWidget(button,i//3,i%3);self.theme_group.addButton(button,i)
        self.theme_group.idClicked.connect(lambda i:(self.theme.setCurrentIndex(i),parent.apply_theme(self.theme.currentData())));self.body.addLayout(grid)
        self.font=QFontComboBox();self.font.setEditable(False);self.font.setMinimumWidth(230);self.font.setCurrentFont(parent.font());self.font.currentFontChanged.connect(parent.apply_font);form.addRow('글꼴',self.font);self.body.addLayout(form)
        self.wrap=QCheckBox('긴 내용 줄바꿈');self.wrap.setChecked(parent.wrap);self.hide=QCheckBox('변경 없는 열 숨기기');self.hide.setChecked(parent.hide_columns);self.body.addWidget(self.wrap);self.body.addWidget(self.hide);self.start=QComboBox();self.start.addItems(['마지막 보기','나눠보기','합쳐보기']);self.start.setCurrentText(str(parent.preferences.value('startView','마지막 보기')));form.addRow('시작 화면',self.start);self.buttons()


class PresetsDialog(Dialog):
    def __init__(self,parent):
        super().__init__(parent,'프리셋');self.parent_window=parent;self.store=FileSettingsStore();self.library=self.store.read();self.list=QListWidget();self.body.addWidget(self.list);self.selected_profile=None
        row=QHBoxLayout();self.body.addLayout(row)
        for label,callback in [('저장',self.save),('불러오기',self.load),('이름 변경',self.rename),('삭제',self.remove),('Import',self.import_file),('Export',self.export_file)]:
            button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(self.reject);self.body.addWidget(close);self.summary=QLabel();self.summary.setWordWrap(True);self.body.addWidget(self.summary);self.details_button=QPushButton('상세 보기');self.details_button.setCheckable(True);self.details=QLabel();self.details.setWordWrap(True);self.details.hide();self.details_button.toggled.connect(self.details.setVisible);self.body.addWidget(self.details_button);self.body.addWidget(self.details);self.list.currentRowChanged.connect(self.show_summary);self.refresh()
    def refresh(self):
        self.list.clear()
        for item in self.library['items']:self.list.addItem(item['profile']['name'])
    def show_summary(self,*args):
        item=self.current()
        if not item:self.summary.clear();return
        p=item['profile'];rules=p.get('comparison_rules',{});enabled=[title for name,title in [('trim','앞뒤 공백 무시'),('ignore_case','대소문자 무시'),('ignore_date_format','날짜 표기 차이 무시')] if rules.get(name)]
        self.summary.setText('기준 키: '+' + '.join(p.get('keys',[]))+'\n합치기 방식: '+p.get('mode','셀 단위')+'\n복사 방식: '+p.get('copy_mode','일반 복사')+'\n비교 조건: '+(' · '.join(enabled) or '그대로 비교')+'\n결과 순서: '+p.get('order','원본 순서 유지'))
        self.details.setText('열 연결\n'+'\n'.join(k+' ↔ '+v for k,v in p.get('mapping',{}).items())+'\n원본: '+str(p.get('old_sheet',''))+' · 제목 '+str(p.get('old_header',1))+'행 / 시작 '+str(p.get('old_start',2))+'행\n비교: '+str(p.get('new_sheet',''))+' · 제목 '+str(p.get('new_header',1))+'행 / 시작 '+str(p.get('new_start',2))+'행')
    def current(self):
        i=self.list.currentRow();return self.library['items'][i] if i>=0 else None
    def save(self):
        if not self.parent_window.session:return
        name,ok=QInputDialog.getText(self,'프리셋 저장','이름')
        if ok and name.strip():
            try:self.library=import_settings(self.parent_window.profile(name.strip()),self.library);self.store.write(self.library);self.refresh()
            except ValueError as exc:self.error(exc)
    def load(self):
        item=self.current()
        if item:self.selected_profile=item['profile'];self.accept()
    def rename(self):
        item=self.current()
        if not item:return
        name,ok=QInputDialog.getText(self,'이름 변경','이름',text=item['profile']['name'])
        if ok and name.strip():
            try:item['profile']['name']=name.strip();self.store.write(self.library);self.refresh()
            except ValueError as exc:self.error(exc)
    def remove(self):
        item=self.current()
        if item and QMessageBox.question(self,'삭제','선택한 프리셋을 삭제할까요?')==QMessageBox.StandardButton.Yes:
            self.library['items'].remove(item);self.store.write(self.library);self.refresh()
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'프리셋 Import','','JSON (*.json)')
        if path:
            try:self.library=import_settings(Path(path).read_bytes(),self.library);self.store.write(self.library);self.refresh()
            except (ValueError,OSError) as exc:self.error(exc)
    def export_file(self):
        path,_=QFileDialog.getSaveFileName(self,'프리셋 Export','프리셋.json','JSON (*.json)')
        if path:
            try:Path(path).write_text(export_settings(self.library),encoding='utf-8')
            except OSError as exc:self.error(exc)
