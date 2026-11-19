"""Native Qt desktop shell; no web page, HTTP listener or browser runtime."""
from copy import deepcopy
from pathlib import Path
import json,os,re,tempfile,time
from PySide6.QtCore import QRectF,Qt,QPoint,QObject,Signal,QRunnable,QThreadPool,QTimer,QSettings,QRect,QEvent,QItemSelection,QItemSelectionModel,QSize
from PySide6.QtGui import QAction,QKeySequence,QFont,QTextDocument,QPalette,QColor,QIcon,QPixmap,QPainter,QPen
from PySide6.QtWidgets import (QMainWindow,QApplication,QWidget,QVBoxLayout,QHBoxLayout,QToolButton,QMenu,QFrame,QLabel,QComboBox,QLineEdit,QSplitter,QFileDialog,QMessageBox,QScrollArea,QHeaderView,QAbstractItemView,QStyle)
import collection_flow
from compare import VERSION,normalized
from display_theme import palettes
from settings_store import clean_profile
from workspace import effective_selection
from .widgets import Choices,symbol,Divider,SearchEdit,CountButton,BusyOverlay,DropOverlay,WelcomeCard,AnimatedCombo as QComboBox
from compare import is_sequence
from .motion import ReviewPane
from .session import Session
from .version import APP_NAME,APP_VERSION
from .models import GridView,ChangeModel,ChangeView,ChangeDelegate,ChangeRail
from .dialogs import RulesDialog,RangesDialog,MappingDialog,FilterDialog,ScreenDialog,PresetsDialog,Dialog


def app_icon():
    """Window/taskbar icon; packaged builds find it next to the other bundled data."""
    import sys
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    return QIcon(str(root/'desktop'/'icons'/'app.png'))


class Signals(QObject):
    result=Signal(object);failed=Signal(str)


class Task(QRunnable):
    def __init__(self,work):super().__init__();self.work=work;self.signals=Signals();self.cancelled=False
    def run(self):
        try:self.signals.result.emit(self.work())
        except Exception as exc:self.signals.failed.emit(str(exc) or type(exc).__name__)


NUMBER_TEXT=re.compile(r'^[-+]?(0|[1-9]\d*|\d{1,3}(,\d{3})+)(\.\d+)?$')   # '007' and codes stay left-aligned text


class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle(f'{APP_NAME} {APP_VERSION}');self.setWindowIcon(app_icon());self.resize(1550,930);self.setMinimumSize(960,620)
        self.session=None;self.visible_rows=[];self.columns=[];self.combined=False;self.edit_enabled=False;self.wrap=False;self.hide_columns=False;self.collapsed=False;self.focused=None;self.scale=100
        self.overlay_connected=False;self.undo_stack=[];self.redo_stack=[];self.pool=QThreadPool.globalInstance();self.tasks=[];self.busy=False;self.syncing=False;self.resizing=False;self.source_paths=set();self.review_revision=0;self.geometry_revision=0;self.active_popover=None;self.popup_trigger_rect=None;self.row_heights={};self.previous_mode=None;self.manual_columns=set();self.needs_fit=False;self.hidden_columns=set();self.hidden_rows=set();self.rows_were_hidden=False;self.row_gaps_above=set();self.row_gap_last=None;self.last_visible_column=None;self.rail_cache=None;self.heights_dirty=True;self.color_cache={};self.hover_row=-1;self.numeric_key=None;self.numeric_set=frozenset();self.numeric_pos=frozenset()
        self.preferences=QSettings(QSettings.defaultFormat(),QSettings.Scope.UserScope,'ExcelMapper','Native');self.migrate_old_preferences();self.theme=str(self.preferences.value('theme','light'));self.wrap=self.preferences.value('wrap',False,type=bool);self.hide_columns=self.preferences.value('hideColumns',False,type=bool)
        self.show_unlinked=str(self.preferences.value('show_unlinked','false')).lower()=='true'
        start=str(self.preferences.value('startView','마지막 보기'));self.combined=(start=='합쳐보기' or start=='마지막 보기' and self.preferences.value('combined',False,type=bool))
        font=QFont(QApplication.font());saved_font=str(self.preferences.value('font',''));
        if saved_font:font.fromString(saved_font)
        self.setFont(font)
        self.root=QWidget();self.setCentralWidget(self.root);self.overlay=BusyOverlay(self.root);self.drop_overlay=DropOverlay(self.root);self.pending_original=None;self.pending_comparisons=None;self.toast=QLabel(self.root);self.toast.setObjectName('toast');self.toast.hide();self.setAcceptDrops(True);layout=QVBoxLayout(self.root);layout.setContentsMargins(16,8,16,8);layout.setSpacing(8)
        self.menu_row=QWidget();menu=QHBoxLayout(self.menu_row);menu.setContentsMargins(0,0,0,0);menu.setSpacing(4);self.menu_row.setObjectName('menuRow');self.menu_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True);layout.addWidget(self.menu_row)
        self.file_button=self.button('파일',menu);file_menu=QMenu(self);file_menu.setToolTipsVisible(True)
        for label,callback,tip in [('열기',lambda:self.open_files('all'),'원본 1개와 비교파일 여러 개를 엽니다.'),('원본 교체',lambda:self.open_files('original'),'비교파일은 유지하고 원본만 바꿉니다.'),('비교 교체',lambda:self.open_files('comparison'),'원본은 유지하고 비교 목록을 바꿉니다.')]:self.action(file_menu,label,callback,tip)
        self.file_button.setText('파일');self.file_button.clicked.connect(self.files_popup)
        self.rules_button=self.button('비교 설정',menu,self.rules_dialog,'같은 값으로 판단할 공백·대소문자·날짜 조건입니다.')
        self.ranges_button=self.button('데이터 위치',menu,self.ranges_dialog,'원본과 비교의 시트·제목 행·시작 행을 정합니다.')
        more=self.button('더보기',menu,tip='화면 설정·프리셋·단축키·테스트 샘플');more_menu=QMenu(self);more_menu.setToolTipsVisible(True)
        self.action(more_menu,'화면 설정',self.screen_dialog,'테마·글꼴·긴 내용 줄바꿈·변경 없는 열 숨기기')
        self.action(more_menu,'프리셋',self.presets_dialog,'비교 설정을 앱에 보관하거나 Import/Export합니다.')
        self.action(more_menu,'단축키',lambda:QMessageBox.information(self,'단축키','Ctrl+S 저장\nCtrl+F 검색\nCtrl+Enter 반영 후 다음\nCtrl+Z 실행 취소\nCtrl+Y 다시 실행\nCtrl+C 선택 셀 복사\nCtrl+휠 표 배율'))
        self.action(more_menu,'프로그램 정보·라이선스',self.about)
        samples_menu=more_menu.addMenu('테스트 샘플')
        from sample_catalog import CATALOG as SAMPLE_SETS
        for sid,entry in SAMPLE_SETS.items():self.action(samples_menu,entry['label'],lambda sid=sid:self.open_sample(sid))
        self.more_menu=more_menu;self.more_button=more;more.clicked.connect(self.more_popup)
        menu.addStretch();self.fold_button=self.button('설정 접기',menu,self.fold,'기준 키·합치기 방식·복사 방식·결과 순서를 접거나 펼칩니다.')
        self.edit_button=self.button('편집 꺼짐',menu,self.toggle_edit,'수정본/합쳐보기 셀을 더블클릭해 내용만 편집합니다.');self.edit_button.setCheckable(True);self.edit_button.setObjectName('editToggle')
        self.options=QFrame();options=QHBoxLayout(self.options);options.setContentsMargins(16,8,16,8);options.setSpacing(24);self.options.setObjectName('options');layout.addWidget(self.options)
        key_area=QWidget();key_layout=QVBoxLayout(key_area);key_layout.setContentsMargins(0,0,0,0);key_top=QHBoxLayout();key_top.setContentsMargins(0,0,0,0);key_top.addWidget(QLabel('기준 키'));key_top.addStretch();key_layout.addLayout(key_top)
        self.key_scroll=QScrollArea();self.key_scroll.setWidgetResizable(True);self.key_scroll.setFixedHeight(34);self.key_scroll.horizontalScrollBar().rangeChanged.connect(self.fit_key_scroll);self.key_scroll.setFrameShape(QFrame.Shape.NoFrame);self.key_widget=QWidget();self.key_layout=QHBoxLayout(self.key_widget);self.key_layout.setContentsMargins(0,0,0,0);self.key_scroll.setWidget(self.key_widget);key_layout.addWidget(self.key_scroll);options.addWidget(key_area,1)
        self.key_apply=self.button('적용',key_top,self.apply_keys,'선택한 기준 키로 다시 비교하며 반영 선택이 초기화됩니다.');self.key_apply.setFixedHeight(22);self.key_apply.setStyleSheet('padding:0 6px;min-height:0;font-size:11px');policy=self.key_apply.sizePolicy();policy.setRetainSizeWhenHidden(True);self.key_apply.setSizePolicy(policy);self.key_apply.hide();key_top.insertWidget(1,self.key_apply)
        self.mapping_button=self.button('열 연결 ∨',key_top,self.mapping_dialog,'원본 열과 비교 열을 연결합니다.');self.mapping_button.setFixedHeight(22);self.mapping_button.setStyleSheet('padding:0 4px;min-height:0;border:0;font-size:11px');key_top.setSpacing(4)
        self.mode=self.option(options,'합치기 방식',['셀 단위','행 단위'],self.change_mode)
        self.copy=self.option(options,'복사 방식',['일반 복사','값만 복사'],self.change_copy)
        self.order=self.option(options,'결과 순서',['원본 유지','직접 정렬'],self.change_order)
        controls=QHBoxLayout();controls.setSpacing(8);controls.setContentsMargins(0,8,0,0);layout.addLayout(controls)
        self.undo_button=self.button('',controls,self.undo,'실행 취소 (Ctrl+Z)');self.undo_button.setIcon(self.native_icon('undo','#64748b'));self.redo_button=self.button('',controls,self.redo,'다시 실행 (Ctrl+Y)');self.redo_button.setIcon(self.native_icon('redo','#64748b'));
        for b in [self.undo_button,self.redo_button]:b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly);b.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(24,24));b.setFixedWidth(38);b.setStyleSheet('padding:3px;min-height:24px')
        self.category_buttons={}
        for kind in ['추가','수정','삭제']:
            button=self.button('0/0',controls,lambda kind=kind:self.bulk(kind),kind+' 전체 선택·해제');button.setIcon(self.native_icon(kind,'#64748b'));self.category_buttons[kind]=button
        self.kind=QComboBox();self.kind.setFixedWidth(149);self.kind.addItems(['전체 항목','변경 항목','추가','수정','삭제']);self.kind.currentTextChanged.connect(lambda value:self.filter_change('kind',value));controls.addWidget(self.kind)
        self.save_button=self.button('수정 다운로드',controls,self.save_dialog,'현재 선택과 직접 편집한 내용으로 별도 파일 저장 (Ctrl+S)')
        self.save_button.setObjectName('primary');self.reset_button=self.button('필터 초기화',controls,self.clear_filters)
        self.search=SearchEdit();self.search.setPlaceholderText('검색');self.search.setStyleSheet('QLineEdit QToolButton{padding:0;min-height:0;border:0;background:transparent}') ;self.search.addAction(self.native_icon('검색','#64748b'),QLineEdit.ActionPosition.LeadingPosition);self.search.setClearButtonEnabled(True);self.search.setFixedWidth(160);self.search.setToolTip('기준값과 원본·비교·최종 내용에서 검색합니다.');controls.addWidget(self.search)
        self.search_timer=QTimer(self);self.search_timer.setSingleShot(True);self.search_timer.setInterval(180);self.search.textChanged.connect(self.schedule_search);self.search.compositionChanged.connect(self.composition_changed);self.search_timer.timeout.connect(self.apply_search)
        controls.addStretch();self.previous_button=self.button('← 이전 파일',controls,self.previous);self.queue_label=QLabel('');controls.addWidget(self.queue_label);self.skip_button=self.button('건너뛰기',controls,lambda:self.advance(True));self.next_button=self.button('반영 후 다음 →',controls,lambda:self.advance(False),'Ctrl+Enter')
        self.regroup_controls(controls)
        nav_widget=QWidget();nav_widget.setObjectName('navRow');nav=QHBoxLayout(nav_widget);nav.setContentsMargins(0,0,0,0);nav.setSpacing(8);layout.addWidget(nav_widget);self.view_button=self.button('합쳐보기',nav,self.toggle_combined);self.zoom_combo=QComboBox();self.zoom_combo.addItems(['60%','75%','85%','100%','115%','125%']);self.zoom_combo.setCurrentText('100%');self.zoom_combo.setFixedWidth(75);self.zoom_combo.setToolTip('表 배율 · Ctrl+휠'.replace('表','표'));self.zoom_combo.currentTextChanged.connect(lambda text:self.set_zoom(int(text.rstrip('%'))));nav.addWidget(self.zoom_combo);self.button('← 이전 변경',nav,lambda:self.navigate(-1));self.button('다음 변경 →',nav,lambda:self.navigate(1));self.build_hide_menu(nav);nav.addStretch()
        nav.insertWidget(2,Divider());nav.insertWidget(5,Divider())
        self.visibility=[]
        for i,name in enumerate(['원본','비교','수정']):
            b=self.button(name,nav,lambda i=i:self.toggle_pane(i));b.setCheckable(True);b.setChecked(True);self.visibility.append(b)
        self.split=QSplitter(Qt.Orientation.Horizontal);self.split.setHandleWidth(2);layout.addWidget(self.split,1);self.tables=QSplitter(Qt.Orientation.Horizontal);self.tables.setHandleWidth(2);self.split.addWidget(self.tables)
        self.views=[];self.frames=[];self.titles=[]
        for pane,title in enumerate(['① 원본','② 비교','③ 수정']):
            frame=QFrame();box=QVBoxLayout(frame);box.setContentsMargins(0,0,0,0);label=QLabel(title);label.setMargin(14);label.setFixedHeight(45);label.setObjectName('paneTitle');frame.setObjectName('pane');box.setSpacing(0);box.addWidget(label);view=GridView(self,pane);box.addWidget(view);wrapper=ReviewPane(self,frame,view);self.views.append(view);self.frames.append(wrapper);self.titles.append(label);self.tables.addWidget(wrapper)
        self.list_frame=QFrame();box=QVBoxLayout(self.list_frame);box.setContentsMargins(0,0,0,0);self.list_title=QLabel('변경사항');self.list_frame.setObjectName('pane');box.setSpacing(0);self.list_title.setMargin(14);self.list_title.setFixedHeight(45);self.list_title.setObjectName('paneTitle');box.addWidget(self.list_title);self.change_list=ChangeView();self.change_list.setToolTipDuration(15000);self.change_list.setUniformItemSizes(False);self.change_list.setWordWrap(True);self.change_model=ChangeModel(self);self.change_list.setModel(self.change_model);self.change_list.setItemDelegate(ChangeDelegate(self.change_list));box.addWidget(self.change_list);self.split.addWidget(self.list_frame);self.list_frame.hide();self.split.setSizes([1000,500]);self.welcome=WelcomeCard(self.root);self.welcome.openRequested.connect(lambda:self.guard(lambda:self.open_files('all')))
        self.change_list.clicked.connect(self.list_focus);self.change_list.toggleRequested.connect(self.list_toggle)
        self.action(self,'저장',self.save_dialog,shortcut='Ctrl+S');self.action(self,'다음',lambda:self.advance(False),shortcut='Ctrl+Return');self.action(self,'실행 취소',self.undo,shortcut='Ctrl+Z');self.action(self,'다시 실행',self.redo,shortcut='Ctrl+Y');self.action(self,'다시 실행',self.redo,shortcut='Ctrl+Shift+Z');self.action(self,'복사',self.copy_cells,shortcut='Ctrl+C')
        for widget in self.findChildren(QWidget):widget.setToolTipDuration(15000)
        self.action(self,'검색',self.focus_search,shortcut='Ctrl+F');self.action(self,'열 숨기기',self.hide_selected_columns,shortcut='Ctrl+0');self.action(self,'행 숨기기',self.hide_selected_rows,shortcut='Ctrl+9');self.action(self,'이전 변경',lambda:self.review_shortcut(-1),shortcut='Ctrl+Q');self.action(self,'다음 변경',lambda:self.review_shortcut(1),shortcut='Ctrl+E');self.action(self,'반영 전환',self.toggle_focused,shortcut='Space');self.build_status_bar();self.apply_theme(self.theme);self.refresh();QTimer.singleShot(0,self.root.setFocus)

    def migrate_old_preferences(self):
        """The program was called Excel Review before; keep a user's saved screen settings."""
        if self.preferences.allKeys():return
        old=QSettings(QSettings.defaultFormat(),QSettings.Scope.UserScope,'ExcelReview','Native')
        for key in old.allKeys():self.preferences.setValue(key,old.value(key))
    @staticmethod
    def native_icon(kind,color):return symbol(kind,color)
    def place_welcome(self):
        """Centre the first-screen card over the (empty) tables."""
        if not self.welcome.isVisible():return
        area=self.split.geometry();self.welcome.setFixedWidth(max(320,min(720,area.width()-48)));self.welcome.adjustSize()
        self.welcome.move(area.x()+max(0,(area.width()-self.welcome.width())//2),area.y()+max(0,(area.height()-self.welcome.height())//2));self.welcome.raise_()
    def resizeEvent(self,event):
        super().resizeEvent(event);QTimer.singleShot(0,self.place_welcome)
        if hasattr(self,'overlay') and self.overlay.isVisible():self.overlay.setGeometry(self.root.rect());self.overlay.reveal()
    def about(self):
        import sys
        from PySide6.QtWidgets import QPlainTextEdit,QDialogButtonBox
        dialog=Dialog(self,f'{APP_NAME} 정보');dialog.resize(650,500)
        root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'desktop'/'licenses'
        text=QPlainTextEdit();text.setReadOnly(True);parts=[f'{APP_NAME} {APP_VERSION} · engine '+VERSION+'\n외부 서버나 웹 브라우저 없이 이 컴퓨터에서만 실행됩니다.']
        if root.exists():
            for path in sorted(root.glob('*.txt')):parts.append(path.name+'\n'+path.read_text(encoding='utf-8'))
        text.setPlainText('\n\n'.join(parts));dialog.body.addWidget(text);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);dialog.body.addWidget(buttons);dialog.exec()
    def guard(self,callback):
        try:
            if not self.busy:callback()
        except Exception as exc:QMessageBox.warning(self,'처리할 수 없음',str(exc))
    def refresh_menu_icons(self):
        """Vector icons for the top menu, re-coloured with the theme."""
        color=self.tokens['muted'];size=QSize(16,16)
        for button,kind in ((self.file_button,'파일'),(self.rules_button,'설정'),(self.ranges_button,'표'),(self.more_button,'더보기'),(self.fold_button,'펼치기' if self.collapsed else '접기'),(self.edit_button,'편집')):
            button.setIcon(self.native_icon(kind,'#ffffff' if button is self.edit_button and button.isChecked() else color));button.setIconSize(size)
    def numeric_columns(self):
        """Column names whose non-empty values are all numbers (right-aligned like Excel); cached per comparison."""
        s=self.session;key=(id(s),len(s.rows),tuple(self.columns)) if s else None
        if key!=self.numeric_key:
            found=set()
            if s:
                for col in self.columns:
                    seen=False;ok=True
                    for row in s.rows:
                        for side in ('before','incoming'):
                            value=row[side].get(col) if row[side] else None
                            if value is None or value=='':continue
                            if isinstance(value,bool) or not (isinstance(value,(int,float)) or NUMBER_TEXT.match(str(value).strip())):ok=False;break
                            seen=True
                        if not ok:break
                    if ok and seen:found.add(col)
            self.numeric_key=key;self.numeric_set=frozenset(found);self.numeric_pos=frozenset(i for i,col in enumerate(self.columns) if col in found)
        return self.numeric_set
    def numeric_positions(self):
        self.numeric_columns();return self.numeric_pos
    def set_hover_row(self,row):
        if row==self.hover_row:return
        self.hover_row=row
        for view in self.views:view.viewport().update()
    def regroup_controls(self,controls):
        """Semantic groups with thin dividers: history | change counters | filters … queue | save / next."""
        while controls.count():controls.takeAt(0)
        self.queue_divider=Divider()
        order=[self.undo_button,self.redo_button,Divider(),*self.category_buttons.values(),Divider(),self.kind,self.search,self.reset_button,None,self.previous_button,self.queue_label,self.skip_button,self.queue_divider,self.save_button,self.next_button]
        for item in order:
            if item is None:controls.addStretch()
            else:controls.addWidget(item)
        self.next_button.setObjectName('accent')
    def button(self,label,layout,callback=None,tip=''):
        b=CountButton() if tip.endswith('전체 선택·해제') else QToolButton();b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);b.setText(label);b.setToolTip(tip);b.setToolTipDuration(15000)
        if callback:b.clicked.connect(lambda checked=False:self.guard(callback))
        layout.addWidget(b);return b
    def action(self,owner,label,callback,tip='',shortcut=None):
        action=QAction(label,self);action.setToolTip(tip or label);action.triggered.connect(lambda checked=False:self.guard(callback))
        if shortcut:action.setShortcut(QKeySequence(shortcut));self.addAction(action)
        elif isinstance(owner,QMenu):owner.addAction(action)
        return action
    def option(self,layout,label,values,callback):
        box=QWidget();stack=QVBoxLayout(box);stack.setContentsMargins(0,0,0,0);stack.setSpacing(10);stack.addWidget(QLabel(label))
        tips={'합치기 방식':['변경된 셀을 개별 선택합니다.','같은 행의 수정사항을 함께 선택합니다.'],
              '복사 방식':['수식과 기본 서식을 복사하며 상대참조를 조정합니다.','수식 대신 파일에 저장된 계산값을 복사합니다.'],
              '결과 순서':['원본 행 순서를 유지합니다.','저장할 파일의 행 순서를 지정합니다.']}
        choices=Choices(values,tips.get(label,()));choices.currentIndexChanged.connect(callback);stack.addWidget(choices);layout.addWidget(box);return choices
    def fit_key_scroll(self,low,high):
        """Keep the key chips fully visible: grow the strip by the scrollbar's height only while it scrolls."""
        bar=self.key_scroll.horizontalScrollBar();self.key_scroll.setFixedHeight(34+(bar.sizeHint().height() if high>low else 0))
    def build_status_bar(self):
        """Bottom bar: a transient message on the left, the file/row/change summary on the right."""
        bar=self.statusBar();bar.setSizeGripEnabled(False);self.status_summary=QLabel('');self.status_summary.setObjectName('statusSummary')
        bar.addPermanentWidget(self.status_summary);bar.showMessage('준비됨');self.root.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def update_status_summary(self,s):
        if not s:self.status_summary.setText('파일을 열어 시작하세요');return
        changes=s.all_changes();chosen=sum(c['id'] in s.selected for c in changes)
        self.status_summary.setText(f"원본 {Path(s.names[0]).name}  ·  비교 {Path(s.names[1]).name}  │  행 {len(self.visible_rows):,}/{len(s.rows):,}  │  변경 {len(changes):,}건 중 {chosen:,}건 반영  │  배율 {self.scale}%")
    def focus_search(self):
        self.search.setFocus();self.search.selectAll()
    def schedule_search(self):
        if not self.search.composing:self.search_timer.start()
    def composition_changed(self,composing):
        if composing:self.search_timer.stop()
        else:self.search_timer.start()
    def apply_search(self):
        if not self.search.composing:self.filter_change('search',self.search.text())
    def review_shortcut(self,direction):
        if not self.busy and not isinstance(QApplication.focusWidget(),QLineEdit):self.navigate(direction)
    def toggle_focused(self):
        if self.busy or not self.session or isinstance(QApplication.focusWidget(),QLineEdit) or self.active_popover:return
        if self.change_list.hasFocus():self.list_toggle(self.change_list.currentIndex());return
        view=next((v for v in self.views if v.hasFocus()),None)
        if view and view.currentIndex().isValid():view.toggle_index(view.currentIndex());return
        # Focus can be on a button/menu after Ctrl+E; toggle the change the review cursor is on.
        view=self.views[0]
        if self.focused in self.visible_rows and view.currentIndex().isValid():view.toggle_index(view.currentIndex())
    def apply_font(self,font):
        font=QFont(font);font.setPixelSize(13);QApplication.instance().setFont(font);self.setFont(font)
        for widget in self.findChildren(QWidget):
            child=QFont(font);child.setPixelSize(round(12*self.scale/100) if widget in self.views else 13);widget.setFont(child)
        self.needs_fit=True;self.heights_dirty=True;self.preferences.setValue('font',font.toString());self.apply_theme(self.theme);self.refresh(self.session)
    def change_order(self,index):
        if index:self.order_dialog()
        else:self.mutate(lambda s:setattr(s,'sort_columns',[]))
        if self.session:self.order.setCurrentIndex(bool(self.session.sort_columns))
    MAX_HISTORY=1000;MAX_FULL_SNAPSHOTS=5
    def snapshot(self):return (self.session,self.combined,self.edit_enabled,self.collapsed)
    def push_history(self,entry):
        """Undo stack of small entries: view toggles and selection/edit patches cost almost nothing;
        only structural changes (opening files, next/previous file, re-analysis) keep a whole session."""
        self.undo_stack.append(entry);self.redo_stack=[]
        full=[index for index,item in enumerate(self.undo_stack) if item['kind']=='full']
        if len(full)>self.MAX_FULL_SNAPSHOTS:del self.undo_stack[:full[-self.MAX_FULL_SNAPSHOTS]]     # older steps cannot be replayed without it
        if len(self.undo_stack)>self.MAX_HISTORY:del self.undo_stack[:len(self.undo_stack)-self.MAX_HISTORY]
    def record(self,before):
        """`before` is a snapshot taken ahead of a change that already happened."""
        after=self.snapshot()
        if before[0] is self.session:self.push_history({'kind':'ui','before':before[1:],'after':after[1:]})
        else:self.push_history({'kind':'full','before':before,'after':after})
    def mutate(self,operation):
        if self.busy or not self.session:return
        before=self.snapshot();new=self.session.clone();changed=operation(new)
        if changed is False:return
        old=self.session;diff=new.diff_from(old);self.session=new;after=self.snapshot()
        self.push_history({'kind':'patch','diff':diff,'before':before[1:],'after':after[1:]} if diff is not None else {'kind':'full','before':before,'after':after})
        self.refresh(old)
    def lock_ui(self,busy):
        self.busy=busy;self.menu_row.setEnabled(not busy);self.options.setEnabled(not busy)
        for view in [*self.views,self.change_list]:view.setEnabled(not busy)
    def run(self,work,label='처리하는 중…',cancellable=True,done=None):
        """Run work in a thread. Cancel only discards the result, so use it for jobs that change nothing on disk."""
        if self.busy:return
        before=self.snapshot();self.lock_ui(True)
        self.save_button.setEnabled(False);self.next_button.setEnabled(False);self.statusBar().showMessage(label);task=Task(work);self.tasks.append(task)
        self.overlay.start(label,cancellable)
        def cancel():
            task.cancelled=True;self.overlay.stop();self.lock_ui(False);self.refresh(self.session);self.statusBar().showMessage('취소했습니다.')
        self.overlay.cancelled.disconnect() if self.overlay_connected else None
        self.overlay.cancelled.connect(cancel);self.overlay_connected=True
        def finish(result=None,error=None):
            self.tasks.remove(task)
            if task.cancelled:return
            self.lock_ui(False)
            if error:
                self.overlay.stop()
                self.last_error=error;self.statusBar().showMessage(error)
                if QApplication.platformName()!='offscreen':QMessageBox.warning(self,'저장할 수 없음' if '저장' in label else '불러올 수 없음',error)
                self.refresh();return
            self.overlay.reveal_now();QApplication.processEvents()   # the redraw below blocks the window: keep the progress bar up for it
            old=self.session;self.session=result;fresh=old is None or old.flow.get('collection_session')!=result.flow.get('collection_session')
            if fresh:self.row_heights={};self.manual_columns.clear();self.hidden_columns.clear();self.hidden_rows.clear()
            self.record(before);self.refresh(old)
            if fresh:
                self.focused=None
                for view in [*self.views,self.change_list]:view.smooth.stop();view.verticalScrollBar().setValue(0)
            self.statusBar().showMessage(self.session.issue or '준비됨')
            self.overlay.stop()
            if done:done()
            if fresh and self.session.warnings:self.show_toast('이 원본에는 저장 후 유지되지 않을 수 있는 개체가 있습니다: '+', '.join(self.session.warnings)+'. 값과 서식은 그대로 유지됩니다. 중요한 파일은 원본을 따로 보관하세요.',12000,'warn')
            if self.session.issue:self.show_toast(self.session.issue+' — 열 연결에서 기준 키와 연결할 열을 맞춰 주세요.',0,'warn')
            if self.session.issue and QApplication.platformName()!='offscreen':self.mapping_dialog()
        task.signals.result.connect(lambda value:finish(value));task.signals.failed.connect(lambda error:finish(error=error));self.pool.start(task)
    def undo(self):
        if self.busy or not self.undo_stack:return
        entry=self.undo_stack.pop();self.redo_stack.append(entry);self.apply_entry(entry,False)
    def redo(self):
        if self.busy or not self.redo_stack:return
        entry=self.redo_stack.pop();self.undo_stack.append(entry);self.apply_entry(entry,True)
    def apply_entry(self,entry,forward):
        old=self.session;state=entry['after' if forward else 'before']
        if entry['kind']=='full':self.session,self.combined,self.edit_enabled,self.collapsed=state
        else:
            if entry['kind']=='patch':
                new=self.session.clone();new.apply_diff(entry['diff'],forward);self.session=new
            self.combined,self.edit_enabled,self.collapsed=state
        self.refresh(old)
    def refresh(self,old=None):
        s,new,columns,reset=self._sync_models(old)
        self._update_chrome(s)
        self._update_row_heights(s,reset)
        self._update_controls(s,old)
        self._refresh_headers()
        self._fit_columns(s,old,new,columns,reset)
        self._fit_edited_columns(s,old)
        self.apply_hidden()
    def _sync_models(self,old):
        """Recompute visible rows/columns and notify the three grids and the change list."""
        self.review_revision+=1
        s=self.session;previous=self.visible_rows;new=s.visible() if s else [];columns=list(s.headers) if s else []
        if s and s.mapping and not self.show_unlinked:columns=[c for c in columns if c in s.mapping or c in s.keys or is_sequence(c)]   # unlinked columns are hidden unless asked for
        if s and self.hide_columns and not any(c['kind']!='수정' for c in s.changes):columns=[c for c in columns if any(change['column']==c for change in s.changes) or any(edit['column']==c for edit in s.edits)]
        reset=old is None or old.rows is not getattr(s,'rows',None) or previous!=new or columns!=self.columns
        if reset:
            for v in self.views:v.model().beginResetModel()
        self.visible_rows=new;self.columns=columns
        if reset:
            for v in self.views:v.model().endResetModel()
        else:
            for v in self.views:
                m=v.model()
                if m.rowCount() and m.columnCount():m.dataChanged.emit(m.index(0,0),m.index(m.rowCount()-1,m.columnCount()-1))
        rebuild=reset or old is None or old.row_mode!=s.row_mode or old.edits!=s.edits
        if rebuild:self.change_model.rebuild()
        elif self.change_model.rowCount():self.change_model.dataChanged.emit(self.change_model.index(0),self.change_model.index(self.change_model.rowCount()-1))
        return s,new,columns,reset
    def _update_chrome(self,s):
        self.welcome.setVisible(s is None);self.place_welcome()
        """Pane visibility, titles and the edit/combined toggles."""
        self.list_frame.setVisible(self.combined);self.view_button.setText('나눠보기' if self.combined else '합쳐보기');self.options.setVisible(not self.collapsed);self.fold_button.setText('설정 펼치기' if self.collapsed else '설정 접기')
        self.edit_button.setChecked(self.edit_enabled);self.edit_button.setText('편집 켜짐' if self.edit_enabled else '편집 꺼짐');self.refresh_menu_icons()
        for i,frame in enumerate(self.frames):
            frame.setVisible(i==0 if self.combined else self.visibility[i].isChecked());self.visibility[i].setEnabled(not self.combined);self.visibility[i].setVisible(not self.combined)
        self.titles[0].setText('합쳐보기' if self.combined else '① 원본'+(' · '+Path(s.names[0]).name if s else ''));self.titles[1].setText('② 비교'+(' · '+Path(s.names[1]).name if s else ''))
    def _update_row_heights(self,s,reset):
        self.resizing=True
        changed_keys={tuple(c['key']) for c in s.all_changes() if c['kind']=='수정'} if s and self.combined else set()
        mode_changed=self.previous_mode!=self.combined;self.previous_mode=self.combined
        # Row heights only depend on the view mode, zoom, wrapping and the row set, not on which changes are ticked.
        refit=reset or mode_changed or self.heights_dirty;self.heights_dirty=False
        for view in self.views:
            view.setWordWrap(self.wrap)
            if mode_changed or reset:view.verticalHeader().reset()
            view.verticalHeader().setDefaultSectionSize(round(32*self.scale/100))
            for visible,i in enumerate(self.visible_rows if refit else ()):
                key=tuple(s.rows[i]['key']);height=self.row_heights.get(key)
                if height is None and not self.combined and not mode_changed:continue
                if height is None and key in changed_keys:height=52
                wanted=round((height if height is not None else 32)*self.scale/100)
                if view.rowHeight(visible)!=wanted:view.setRowHeight(visible,wanted)
        self.resizing=False
    def _update_controls(self,s,old):
        """Undo/redo, queue buttons, counters, the search box and the status summary."""
        self.update_status_summary(s)
        self.undo_button.setEnabled(bool(self.undo_stack));self.redo_button.setEnabled(bool(self.redo_stack));ready=bool(s and s.rows and not s.issue)
        self.save_button.setEnabled(ready and not self.busy);self.previous_button.setEnabled(bool(s and (s.flow['queue_index']>0 or s.flow['queue_complete'])));self.skip_button.setEnabled(bool(s));self.next_button.setEnabled(bool(ready and s.flow['queue_index']+1<len(s.flow['comparison_queue'])))

        for button in [self.previous_button,self.queue_label,self.skip_button,self.queue_divider,self.next_button]:button.setVisible(bool(s and len(s.flow['comparison_queue'])>1))
        self.queue_label.setText(f"{s.flow['queue_index']+1} / {len(s.flow['comparison_queue'])}" if s and len(s.flow['comparison_queue'])>1 else '')
        self.save_button.setText('수정 다운로드')
        if s:
            for combo,value in [(self.mode,int(s.row_mode)),(self.copy,int(s.copy_mode=='값만 복사')),(self.order,int(bool(s.sort_columns))),(self.kind,self.kind.findText(s.kind))]:combo.blockSignals(True);combo.setCurrentIndex(value);combo.blockSignals(False)

            if not self.search.hasFocus() and not self.search.composing and self.search.text()!=s.search:
                self.search.blockSignals(True);self.search.setText(s.search);self.search.blockSignals(False)
            for kind,button in self.category_buttons.items():
                changes=[c for c in s.all_changes() if c['kind']==kind];count=sum(c['id'] in s.selected for c in changes);total=len(changes)
                if kind=='수정' and s.row_mode:total=len({tuple(c['key']) for c in changes});count=len({tuple(c['key']) for c in changes if c['id'] in s.selected})
                button.setText(f'{count}/{total}');needed=button.fontMetrics().horizontalAdvance(f'{total}/{total}')+54;button.setFixedWidth(max(getattr(button,'reserved_width',0),needed));button.reserved_width=button.width();button.setIcon(self.native_icon(kind,self.tokens[{'추가':'add','수정':'edit','삭제':'delete'}[kind]+'-text'] if count else '#8792a2'));button.setEnabled(bool(total));color={'추가':'add','수정':'edit','삭제':'delete'}[kind];button.setStyleSheet('border:1px '+('solid' if count else 'dashed')+' '+self.tokens[color+'-text']+';background:'+self.tokens[color]+';color:'+self.tokens[color+'-text'] if count else 'border:1px dashed #8792a2;color:#8792a2;')
        total=self.change_model.rowCount();chosen=sum(all(c['id'] in s.selected for c in changes) for _,changes in self.change_model.entries) if s else 0;self.list_title.setText(f'변경사항  {chosen}/{total}건')
        if s and (old is None or old.headers!=s.headers or old.keys!=s.keys or old.mapping!=s.mapping or old.rows is not s.rows):self.rebuild_keys()
    def _refresh_headers(self):
        for v in self.views:
            if v.model().columnCount():v.model().headerDataChanged.emit(Qt.Orientation.Horizontal,0,v.model().columnCount()-1)
            v.viewport().update();v.external_rail.update()
        self.style_visibility()
    def _fit_columns(self,s,old,new,columns,reset):
        """Auto-fit widths only for a new table or when requested; manual widths are preserved."""
        if new and (self.needs_fit or reset and (old is None or old.rows is not s.rows or columns!=getattr(old,'headers',[]))):
            preserved={c:self.views[0].columnWidth(c) for c in range(self.views[0].model().columnCount()) if (['__row__','__key__'][c] if c<2 else self.columns[c-2]) in self.manual_columns}
            self.needs_fit=False;self.resizing=True
            actual_mode=self.combined
            for v in self.views:
                # Measuring every sampled row of a 10000-row table freezes the window; fewer samples fit as well.
                v.horizontalHeader().setResizeContentsPrecision(1000 if len(self.visible_rows)<=1500 else 250)
                self.combined=True if v.pane==0 else actual_mode;v.model().role_cache.clear()
                v.resizeColumnsToContents()
                for c in range(v.model().columnCount()):v.setColumnWidth(c,min(420,max(40 if c==0 else 52,v.columnWidth(c),v.horizontalHeader().fontMetrics().horizontalAdvance(str(v.model().headerData(c,Qt.Orientation.Horizontal)).split('\n')[-1])+44)))
            self.combined=actual_mode
            for v in self.views:v.model().role_cache.clear()
            self.resizing=False
            for c in range(self.views[0].model().columnCount()):self.sync_column(self.views[0],c,preserved.get(c,max(v.columnWidth(c) for v in self.views)),manual=False)
    def _fit_edited_columns(self,s,old):
        """Widen a column to show a freshly typed value."""
        if old is not None and s and old.edits!=s.edits:
            for edit in s.edits:
                col=edit['column']
                if col in self.columns and col not in self.manual_columns:
                    from html import escape
                    import math
                    c=self.columns.index(col)+2;doc=QTextDocument();doc.setDefaultFont(self.views[0].font());doc.setHtml('<b>'+escape(str(edit['value']))+'</b>');width=min(420,math.ceil(doc.idealWidth())+37)
                    self.sync_column(self.views[0],c,max(width,self.views[0].columnWidth(c)),manual=False)
    def rebuild_keys(self):
        while self.key_layout.count():
            item=self.key_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.key_checks={};self.key_draft=list(self.session.keys)
        for col in self.session.headers:
            if col not in self.session.mapping:continue
            b=QToolButton();b.setText(col);b.setCheckable(True);b.setChecked(col in self.key_draft);b.setToolTip('두 파일에서 같은 항목을 찾을 열입니다. 여러 열을 조합할 수 있습니다.');b.setToolTipDuration(15000)
            b.ensurePolished();b.setMinimumWidth(b.sizeHint().width());b.toggled.connect(lambda on,c=col:self.key_drafted(c,on));self.key_layout.addWidget(b);self.key_checks[col]=b
        self.key_layout.addStretch();self.key_apply.hide()
    def key_drafted(self,col,on):
        if on and col not in self.key_draft:self.key_draft.append(col)
        elif not on and col in self.key_draft:self.key_draft.remove(col)
        self.key_apply.setVisible(self.key_draft!=self.session.keys);self.key_apply.setStyleSheet('padding:0 6px;min-height:0;font-size:11px;background:#2563eb;color:white;border:1px solid #60a5fa')
    def apply_keys(self):
        if self.session:
            s=self.session.clone();keys=list(self.key_draft);self.run(lambda:(s.configure(keys=keys),s)[1])
    def choose(self,ids,on):self.mutate(lambda s:s.choose(ids,on))
    def bulk(self,kind):
        if not self.session:return
        ids=[c['id'] for c in self.session.all_changes() if c['kind']==kind];self.choose(ids,not any(i in self.session.selected for i in ids))
    def change_mode(self,index):
        def change(s):s.row_mode=bool(index);s.selected=effective_selection(s.all_changes(),s.selected,s.row_mode);s.prepare_results()
        self.mutate(change)
    def change_copy(self,index):
        def change(s):s.copy_mode='값만 복사' if index else '일반 복사';s.prepare_results()
        self.mutate(change)
    def filter_change(self,name,value):
        if self.session and getattr(self.session,name)!=value:self.mutate(lambda s:setattr(s,name,value))
    def clear_filters(self):
        def change(s):s.filters={};s.kind='전체 항목';s.search='';s.view_sort=None
        self.mutate(change)
    def fold(self):
        before=self.snapshot();self.collapsed=not self.collapsed;self.record(before);self.refresh(self.session)
    def toggle_edit(self):
        before=self.snapshot();self.edit_enabled=not self.edit_enabled;self.record(before);self.refresh(self.session)
    def toggle_combined(self):
        if not self.combined:self.split_table_sizes=self.tables.sizes()
        first_row=self.views[0].rowAt(0);row_offset=-self.views[0].rowViewportPosition(first_row) if first_row>=0 else 0
        scrolls=[(v.verticalScrollBar().value(),v.horizontalScrollBar().value()) for v in self.views]
        before=self.snapshot();self.combined=not self.combined;self.preferences.setValue('combined',self.combined);self.record(before);self.refresh(self.session)
        self.split.setSizes([max(1,self.split.width()*2//3),max(1,self.split.width()//3)] if self.combined else [self.split.width(),0])
        if not self.combined:self.tables.setSizes(getattr(self,'split_table_sizes',[max(1,self.split.width()//3)]*3))
        def restore():
            QApplication.sendPostedEvents(None,QEvent.Type.LayoutRequest)
            for view,(top,left) in zip(self.views,scrolls):
                target=view.verticalScrollBar().value()+view.rowViewportPosition(first_row)+row_offset if first_row>=0 else top
                view.verticalScrollBar().setValue(target);view.horizontalScrollBar().setValue(left)
        QTimer.singleShot(0,restore)
    def token_color(self,name):
        """Theme colour objects reused while painting thousands of cells."""
        color=self.color_cache.get(name)
        if color is None:color=self.color_cache[name]=QColor(self.tokens[name])
        return color
    def rail_marks(self,height,view):
        """Scroll-rail marks, computed once per review/geometry revision and shared by the three rails."""
        s=self.session;key=(self.review_revision,self.geometry_revision,height,len(self.visible_rows))
        if self.rail_cache and self.rail_cache[0]==key:return self.rail_cache[1]
        heights=[view.rowHeight(j) for j in range(len(self.visible_rows))];total=max(1,sum(heights));scale=height/total
        lanes={kind:[] for kind in ('추가','수정','삭제')};offset=0;selected=s.selected
        for pos,i in enumerate(self.visible_rows):
            top=offset*scale;offset+=heights[pos];bottom=offset*scale
            changes=s.review_changes(i)
            if not changes:continue
            kinds={c['kind'] for c in changes if c['id'] in selected}
            for kind in lanes:
                if kind not in kinds:continue
                runs=lanes[kind]
                # Adjacent marked rows form one run; an unmarked row between them leaves a gap.
                if runs and pos==runs[-1][2]+1:runs[-1][1]=bottom;runs[-1][2]=pos
                else:runs.append([top,bottom,pos])
        marks=[]
        for kind,runs in lanes.items():
            lane=['추가','수정','삭제'].index(kind)*6;merged=[]
            for top,bottom,pos in runs:
                bottom=max(bottom,top+3)
                # Keep a visible 1.5px gap between runs, so one missing row among thousands still shows.
                if merged and top-merged[-1][1]<1.5:
                    shrunk=top-1.5
                    if shrunk-merged[-1][0]>=1:merged[-1][1]=shrunk
                    else:merged[-1][1]=bottom;continue
                merged.append([top,bottom])
            marks.extend((kind,QRectF(lane,top,6,bottom-top)) for top,bottom in merged)
        self.rail_cache=(key,marks);return marks
    def build_hide_menu(self,layout):
        """Hide/show menu next to the review navigation (Excel's Ctrl+0 / Ctrl+9 also work)."""
        self.hide_button=self.button('숨기기',layout,tip='선택한 열·행을 숨기거나 다시 표시합니다. 열 머리글을 누르면 열 전체가 선택됩니다. (Ctrl+0 열 · Ctrl+9 행)')
        menu=QMenu(self);menu.setToolTipsVisible(True)
        self.action(menu,'선택한 열 숨기기 (Ctrl+0)',self.hide_selected_columns,'선택한 셀이 속한 열을 숨깁니다.')
        self.action(menu,'선택한 행 숨기기 (Ctrl+9)',self.hide_selected_rows,'선택한 셀이 속한 행을 숨깁니다.')
        menu.addSeparator()
        self.unlinked_action=menu.addAction('연결 안 한 열 보이기');self.unlinked_action.setCheckable(True);self.unlinked_action.setChecked(self.show_unlinked);self.unlinked_action.setToolTip('열 연결에서 연결하지 않은 원본 열을 비교 화면에 보여 줍니다. 기본은 숨김입니다.');self.unlinked_action.toggled.connect(self.toggle_unlinked)
        menu.addSeparator()
        self.action(menu,'숨긴 열 모두 표시',lambda:self.show_hidden('columns'));self.action(menu,'숨긴 행 모두 표시',lambda:self.show_hidden('rows'))
        self.action(menu,'모두 표시',lambda:self.show_hidden('all'),'숨긴 열과 행을 모두 다시 표시합니다.')
        self.hide_button.setMenu(menu);self.hide_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    def toggle_unlinked(self,on):
        self.show_unlinked=bool(on);self.preferences.setValue('show_unlinked',self.show_unlinked);self.refresh(self.session)
    def selected_axes(self):
        """Rows and columns covered by the selection of the focused (else first selected) table."""
        if not self.session:return None,set(),set()
        view=next((v for v in self.views if v.hasFocus()),None) or next((v for v in self.views if v.selectionModel().hasSelection()),None)
        if view is None:return None,set(),set()
        rows=set();columns=set()
        for block in view.selectionModel().selection():rows.update(range(block.top(),block.bottom()+1));columns.update(range(block.left(),block.right()+1))
        return view,rows,columns
    def hide_selected_columns(self):
        view,rows,columns=self.selected_axes();data=[c for c in columns if c>=2]
        if view is None or not data:return
        if len(data)>=len(self.columns):data=[view.currentIndex().column()] if view.currentIndex().column()>=2 else []
        self.hidden_columns.update(self.columns[c-2] for c in data);self.apply_hidden()
    def hide_selected_rows(self):
        view,rows,columns=self.selected_axes()
        if view is None or not rows:return
        self.hidden_rows.update(tuple(self.session.rows[self.visible_rows[r]]['key']) for r in rows if r<len(self.visible_rows));self.apply_hidden()
    def show_hidden(self,kind):
        if kind in ('columns','all'):self.hidden_columns.clear()
        if kind in ('rows','all'):self.hidden_rows.clear()
        self.apply_hidden()
    def apply_hidden(self):
        """Apply the view-only hidden columns/rows to the three tables; results and saved files are unaffected."""
        s=self.session
        if not s:return
        names=[None,None]+self.columns;hidden_columns=[c for c,name in enumerate(names) if name is not None and name in self.hidden_columns]
        hidden_rows=[r for r,i in enumerate(self.visible_rows) if tuple(s.rows[i]['key']) in self.hidden_rows] if self.hidden_rows else []
        self.resizing=True
        for view in self.views:
            for c in range(2,len(names)):view.setColumnHidden(c,c in hidden_columns)
            if hidden_rows or self.rows_were_hidden:
                shown=set(hidden_rows)
                for r in range(len(self.visible_rows)):view.setRowHidden(r,r in shown)
        self.resizing=False;self.rows_were_hidden=bool(hidden_rows)
        shown=set(hidden_rows);count=len(self.visible_rows)
        visible_columns=[c for c in range(2,len(names)) if c not in hidden_columns];self.last_visible_column=visible_columns[-1] if visible_columns else None
        after={h+1 for h in shown};self.row_gaps_above={r for r in after if r<count and r not in shown}
        last=next((r for r in range(count-1,-1,-1) if r not in shown),None);self.row_gap_last=last if last is not None and last<count-1 and (count-1) in shown else None
        parts=([f'열 {len(hidden_columns)}'] if hidden_columns else [])+([f'행 {len(hidden_rows)}'] if hidden_rows else []);self.hide_button.setText(' · '.join(['숨기기',*parts]))
        self.apply_spans()
        for view in self.views:view.viewport().update();view.horizontalHeader().viewport().update();view.external_rail.update()
        self.geometry_revision+=1
    def place_row(self,position,gap):
        """An added row was dragged from screen row `position` to the gap before screen row `gap`: remember the original row it follows."""
        s=self.session;order=list(self.visible_rows);moved=order.pop(position)
        if gap>position:gap-=1
        order.insert(gap,moved);anchor=None
        for j in reversed(order[:gap]):
            row=s.rows[j]
            if row['beforeRow'] is not None:anchor=row['beforeRow'];break
            placed=s.placements.get(json.dumps(row['key'],ensure_ascii=False))
            if placed is not None:anchor=placed;break
        if anchor is None:
            below=next((s.rows[j]['beforeRow'] for j in order[gap+1:] if s.rows[j]['beforeRow'] is not None),None)
            anchor=(below-1) if below is not None else s.left.start_row-1
        key=s.rows[moved]['key'];keep=order if (s.view_sort or s.filters or s.search.strip()) else None
        self.mutate(lambda n:n.place(key,anchor,keep))
        self.show_toast(f"'{s.rows[moved]['label']}' 행을 원본 {anchor}행 뒤에 넣습니다. 저장할 때 그 자리에 들어갑니다.",4000,'info')
    def apply_spans(self):
        """Draw merged Excel cells merged: rows of one merged range that sit next to each other on screen become one cell.

        Sorting, filters, hidden rows or added rows split a range into separate runs; a row with a change in those columns is never merged."""
        s=self.session;colpos={c:n for n,c in enumerate(self.columns)}
        for view in self.views:
            model=view.model();view.clearSpans();model.span_starts=set()
            if not s or not s.rows:continue
            table=s.right if model.pane==1 and not model.merged() else s.left
            if not table.merged_ranges:continue
            side='incomingRow' if table is s.right else 'beforeRow'
            display=(lambda h:h) if table is s.left else {b:a for a,b in s.mapping.items()}.get
            where={}
            for pos,i in enumerate(self.visible_rows):
                physical=s.rows[i][side]
                if physical is not None and not view.isRowHidden(pos):where[physical]=pos
            for r1,r2,c1,c2 in table.merged_ranges:
                cols=[display(table.headers[c-1]) if c<=len(table.headers) else None for c in range(c1,c2+1)]
                if any(c not in colpos for c in cols):continue
                first=colpos[cols[0]]
                if [colpos[c] for c in cols]!=list(range(first,first+len(cols))) or any(view.isColumnHidden(2+colpos[c]) for c in cols):continue
                run=[]
                def flush():
                    if run and (len(run)>1 or len(cols)>1):view.setSpan(run[0],2+first,len(run),len(cols));model.span_starts.add((run[0],2+first))
                for p in sorted(where[r] for r in range(r1,r2+1) if r in where):
                    if any(c['kind']!='수정' or c['column'] in cols for c in s.review_changes(self.visible_rows[p])):flush();run=[];continue
                    if run and p!=run[-1]+1:flush();run=[]
                    run.append(p)
                flush()
    # ---- Excel-style hide / unhide menus (right click on a column header or on the row number)
    def column_is_hidden(self,column):return 2<=column<len(self.columns)+2 and self.columns[column-2] in self.hidden_columns
    def hidden_run(self,start,step):
        """Hidden data columns in a row starting at `start` and moving by `step` (-1 left, +1 right)."""
        run=[];column=start
        while self.column_is_hidden(column):run.append(column);column+=step
        return run
    def row_is_hidden(self,position):return 0<=position<len(self.visible_rows) and tuple(self.session.rows[self.visible_rows[position]]['key']) in self.hidden_rows
    def hidden_row_run(self,start,step):
        run=[];position=start
        while self.row_is_hidden(position):run.append(position);position+=step
        return run
    def unhide_candidates(self,indexes,run,is_hidden):
        """Hidden items strictly inside the selection plus the hidden runs touching its two ends (as in Excel)."""
        low,high=min(indexes),max(indexes);found=set(run(low-1,-1))|set(run(high+1,1))
        found|={i for i in range(low,high+1) if is_hidden(i)}
        return sorted(found)
    def header_entries(self,view,column,gap=None):
        """(label, action) pairs for the right-click menu of a column header; `gap` = hidden columns under a double line."""
        if gap:return [('숨기기 취소',lambda columns=list(gap):self.unhide_columns(columns))]
        if column<2 or not self.session:return []
        selected=view.selectionModel().selection();columns={c for block in selected for c in range(block.left(),block.right()+1) if c>=2}
        if column not in columns:columns={column}
        entries=[('열 숨기기' if len(columns)==1 else f'열 {len(columns)}개 숨기기',lambda picked=sorted(columns):self.hide_columns_at(picked))]
        restore=self.unhide_candidates(columns,self.hidden_run,self.column_is_hidden)
        if restore:entries.append(('숨기기 취소',lambda columns=restore:self.unhide_columns(columns)))
        return entries
    def row_entries(self,view,row,gap=None):
        if gap:return [('숨기기 취소',lambda rows=list(gap):self.unhide_rows(rows))]
        if not self.session or not 0<=row<len(self.visible_rows):return []
        selected=view.selectionModel().selection();rows={r for block in selected for r in range(block.top(),block.bottom()+1)}
        if row not in rows:rows={row}
        entries=[('행 숨기기' if len(rows)==1 else f'행 {len(rows)}개 숨기기',lambda picked=sorted(rows):self.hide_rows_at(picked))]
        restore=self.unhide_candidates(rows,self.hidden_row_run,self.row_is_hidden)
        if restore:entries.append(('숨기기 취소',lambda rows=restore:self.unhide_rows(rows)))
        return entries
    def hide_columns_at(self,columns):
        self.hidden_columns.update(self.columns[c-2] for c in columns if 2<=c<len(self.columns)+2);self.apply_hidden()
    def unhide_columns(self,columns):
        self.hidden_columns.difference_update(self.columns[c-2] for c in columns if 2<=c<len(self.columns)+2);self.apply_hidden()
    def hide_rows_at(self,rows):
        self.hidden_rows.update(tuple(self.session.rows[self.visible_rows[r]]['key']) for r in rows if 0<=r<len(self.visible_rows));self.apply_hidden()
    def unhide_rows(self,rows):
        self.hidden_rows.difference_update(tuple(self.session.rows[self.visible_rows[r]]['key']) for r in rows if 0<=r<len(self.visible_rows));self.apply_hidden()
    def show_entries(self,entries,global_point):
        if not entries:return None
        menu=QMenu(self);menu.setToolTipsVisible(True)
        for label,callback in entries:menu.addAction(label).triggered.connect(lambda checked=False,callback=callback:self.guard(callback))
        menu.exec(global_point);return menu
    def header_menu(self,view,point):
        """Right click on a column header: hide the selected columns / unhide neighbours. Filters open with the arrow button."""
        header=view.horizontalHeader();column=header.logicalIndexAt(point);gap=header.gap_hit(point)
        if not gap and column>=2:
            columns={c for block in view.selectionModel().selection() for c in range(block.left(),block.right()+1)}
            if column not in columns:view.selectColumn(column)
        self.show_entries(self.header_entries(view,column,gap),header.viewport().mapToGlobal(point))
    def row_menu(self,view,point):
        """Right click on a row number: hide the selected rows / unhide neighbours (the double line only offers unhide)."""
        index=view.indexAt(point)
        if not index.isValid():return
        rect=view.visualRect(index);row=index.row();gap=None
        for r in self.row_gaps_above:
            if abs(point.y()-view.rowViewportPosition(r))<=4:gap=self.hidden_row_run(r-1,-1)
        last=self.row_gap_last
        if last is not None and abs(point.y()-view.rowViewportPosition(last)-view.rowHeight(last))<=4:gap=self.hidden_row_run(last+1,1)
        if not gap:
            rows={r for block in view.selectionModel().selection() for r in range(block.top(),block.bottom()+1)}
            if row not in rows:view.selectRow(row)
        self.show_entries(self.row_entries(view,row,gap),view.viewport().mapToGlobal(point))
    def toggle_pane(self,i):
        if sum(b.isChecked() for b in self.visibility)==0:self.visibility[i].setChecked(True)
        self.style_visibility();self.refresh(self.session)
    def style_visibility(self):
        for button in self.visibility:
            t=self.tokens;bg=t['hover'] if button.isChecked() else t['input']
            button.setStyleSheet('QToolButton,QToolButton:hover,QToolButton:pressed{background:'+bg+';color:'+t['text']+';border:1px '+('solid' if button.isChecked() else 'dashed')+' '+t['border']+';padding:3px 9px;min-height:22px}')
            button.update()
    def sync_column(self,source,column,width,manual=True):
        if self.resizing:return
        if manual and column<len(self.columns)+2:self.manual_columns.add(['__row__','__key__'][column] if column<2 else self.columns[column-2])
        self.resizing=True
        for v in self.views:
            if v.columnWidth(column)!=width:v.setColumnWidth(column,width)
        self.resizing=False
    def sync_row(self,source,row,height):
        if self.resizing:return
        self.geometry_revision+=1
        for view in self.views:
            if hasattr(view,'external_rail'):view.external_rail.update()
        if self.resizing:return
        if self.session and 0<=row<len(self.visible_rows):self.row_heights[tuple(self.session.rows[self.visible_rows[row]]['key'])]=height*100/self.scale
        self.resizing=True
        for view in self.views:
            if view!=source:view.setRowHeight(row,height)
        self.resizing=False
    def sync_scroll(self,source,value,horizontal):
        if self.syncing:return
        self.syncing=True
        for v in self.views:
            if v!=source:(v.horizontalScrollBar() if horizontal else v.verticalScrollBar()).setValue(value)
        self.syncing=False
    def focus_row(self,i,col=None):
        self.focused=i;target=None
        for row,(source,changes) in enumerate(self.change_model.entries):
            if source!=i:continue
            if target is None:target=row
            if col is None or any(c['column']==col for c in changes):target=row;break
        if target is not None:
            index=self.change_model.index(target);selection=self.change_list.selectionModel()
            selection.setCurrentIndex(index,QItemSelectionModel.SelectionFlag.ClearAndSelect);self.change_list.scrollTo(index)
    def list_focus(self,index):
        if index.isValid():
            i,changes=self.change_model.entries[index.row()];self.jump(i,changes[0]['column']);self.change_list.selectionModel().setCurrentIndex(index,QItemSelectionModel.SelectionFlag.ClearAndSelect)
    def list_toggle(self,index):
        if index.isValid():
            i,changes=self.change_model.entries[index.row()];ids=[c['id'] for c in changes];self.choose(ids,not all(c in self.session.selected for c in ids))
    def jump(self,i,col=None):
        if i not in self.visible_rows:return
        self.focused=i;self.focused_column=col;row=self.visible_rows.index(i);column=self.columns.index(col)+2 if col in self.columns else 2
        row_mode=bool(self.session and self.session.row_mode)
        for v in self.views:
            model=v.model();index=model.index(row,column);selection=v.selectionModel()
            # Use the model directly: setCurrentIndex would honour a held Ctrl key and add to the selection.
            if row_mode:
                selection.select(QItemSelection(model.index(row,0),model.index(row,model.columnCount()-1)),QItemSelectionModel.SelectionFlag.ClearAndSelect)
                selection.setCurrentIndex(index,QItemSelectionModel.SelectionFlag.NoUpdate)
            else:selection.setCurrentIndex(index,QItemSelectionModel.SelectionFlag.ClearAndSelect)
            v.scrollTo(index,QAbstractItemView.ScrollHint.EnsureVisible)
        self.focus_row(i,col)
    def navigate(self,direction):
        if not self.session or not self.visible_rows:return
        entries=[]
        for i in self.visible_rows:
            if tuple(self.session.rows[i]['key']) in self.hidden_rows:continue
            changes=[c for c in self.session.review_changes(i) if c['id'] in self.session.selected and c['column'] not in self.hidden_columns]
            if self.session.row_mode:
                if changes:entries.append((i,next((c['column'] for c in changes if c['column']),None)))
            else:
                entries.extend((i,c['column']) for c in changes)
        if not entries:return
        current_col=getattr(self,'focused_column',None);current=(self.focused,current_col)
        if current in entries:index=(entries.index(current)+direction)%len(entries)
        else:
            rowpos=self.visible_rows.index(self.focused) if self.focused in self.visible_rows else (-1 if direction>0 else len(self.visible_rows))
            candidates=[j for j,(i,col) in enumerate(entries) if (self.visible_rows.index(i)-rowpos)*direction>0]
            index=(candidates[0] if direction>0 else candidates[-1]) if candidates else (0 if direction>0 else len(entries)-1)
        i,col=entries[index];self.focused_column=col;self.jump(i,col)
    def zoom(self,direction):
        steps=[60,75,85,100,115,125];index=min(range(len(steps)),key=lambda i:abs(steps[i]-self.scale));self.set_zoom(steps[max(0,min(len(steps)-1,index+direction))])
    def set_zoom(self,scale):
        previous=self.scale;self.scale=scale;self.heights_dirty=True;self.resizing=True;self.geometry_revision+=1;font=QFont(self.font());font.setPixelSize(max(8,round(12*scale/100)))
        self.zoom_combo.blockSignals(True);self.zoom_combo.setCurrentText(str(scale)+'%');self.zoom_combo.blockSignals(False)
        for v in self.views:
            v.setFont(font);v.setStyleSheet('QTableView{font-size:'+str(round(12*scale/100))+'px} QHeaderView::section{font-size:'+str(round(11*scale/100))+'px}')
            v.horizontalHeader().setFixedHeight(round(46*scale/100));v.verticalHeader().setDefaultSectionSize(round(32*scale/100))
        self.resizing=True
        for v in self.views:
            for col in range(v.model().columnCount()):v.setColumnWidth(col,round(v.columnWidth(col)*scale/previous))
        self.resizing=False
        self.refresh(self.session)
    def copy_cells(self):
        view=next((v for v in self.views if v.hasFocus()),None)
        if not view:return
        indexes=view.selectionModel().selectedIndexes()
        if not indexes:return
        rows=sorted({i.row() for i in indexes});columns=sorted({i.column() for i in indexes});picked={(i.row(),i.column()) for i in indexes}
        QApplication.clipboard().setText('\n'.join('\t'.join(str(view.model().data(view.model().index(r,c)) or '') if (r,c) in picked else '' for c in columns) for r in rows))
    def popup_ready(self,key):
        popup=self.active_popover
        if popup and popup.isVisible():
            same=getattr(popup,'request_key',None)==key;popup.reject()
            if same:return False
        closed=getattr(self,'closed_popover',None)
        if closed and closed[0]==key and time.monotonic()-closed[1]<0.12:return False
        self.popup_request=key;return True
    def column_menu(self,view,point,column=None):
        if not self.session:return
        header=view.horizontalHeader();column=header.logicalIndexAt(point) if column is None else column
        if column<0:return
        if not self.popup_ready((header,column)):return
        col=['__row__','__key__'][column] if column<2 else self.columns[column-2];pane=2 if self.combined else view.pane
        self.popup_anchor=header;button=header.button_rect(column);self.popup_trigger_rect=QRect(header.viewport().mapToGlobal(button.topLeft()),button.size());self.popup_position=header.viewport().mapToGlobal(button.bottomLeft())
        self.filter_dialog(pane,col)
    def filter_dialog(self,pane,col):
        dialog=FilterDialog(self,self.session,pane,col)
        if dialog.exec():values=dialog.values();self.mutate(lambda s:s.filters.update({col:values}))
        self.popup_position=None;self.popup_trigger_rect=None
    def rules_dialog(self):
        if not self.popup_ready(self.rules_button):return
        self.popup_trigger_rect=None;self.popup_anchor=self.rules_button;rules=self.session.rules if self.session else __import__('comparison_rules').clean();dialog=RulesDialog(self,rules)
        if dialog.exec() and self.session:
            s=self.session.clone();self.run(lambda:(s.configure(rules=dialog.rules),s)[1])
    def ranges_dialog(self):
        if not self.popup_ready(self.ranges_button):return
        if not self.session:return
        self.popup_trigger_rect=None;self.popup_anchor=self.ranges_button;dialog=RangesDialog(self,self.session)
        if dialog.exec():
            s=self.session.clone();values=dialog.values();self.run(lambda:(s.configure(layout=values),s)[1])
    def mapping_dialog(self):
        if not self.popup_ready(self.mapping_button):return
        if not self.session:return
        self.popup_trigger_rect=None;self.popup_anchor=self.mapping_button;dialog=MappingDialog(self,self.session)
        if dialog.exec():
            keys,mapping=dialog.values();s=self.session.clone();self.run(lambda:(s.configure(keys=keys,mapping=mapping),s)[1])
    def order_dialog(self):
        if not self.popup_ready(self.order.buttons[1]):return
        if not self.session:return
        self.popup_trigger_rect=None;self.popup_anchor=self.order.buttons[1];dialog=Dialog(self,'결과 순서');col=QComboBox();col.addItem('원본 순서 유지','')
        for h in self.session.headers:
            if h!=self.session.sequence:col.addItem(h,h)
        col.setCurrentIndex(col.findData(self.session.sort_columns[0] if self.session.sort_columns else ''));descending=QComboBox();descending.addItems(['오름차순','내림차순']);descending.setCurrentIndex(int(self.session.descending));dialog.body.addWidget(col);dialog.body.addWidget(descending);dialog.buttons()
        if dialog.exec():
            def change(s):s.sort_columns=[col.currentData()] if col.currentData() else [];s.descending=bool(descending.currentIndex())
            self.mutate(change)
    def files_popup(self):
        if not self.popup_ready(self.file_button):return
        from PySide6.QtWidgets import QPushButton
        self.popup_trigger_rect=None;self.popup_anchor=self.file_button;dialog=Dialog(self,'파일');dialog.setMinimumWidth(540)
        for label,name,side in [('원본',self.session.names[0] if self.session else '파일을 선택하세요','original'),('비교',self.session.names[1] if self.session else '파일을 선택하세요','comparison')]:
            row=QHBoxLayout();text=QLabel(label+'  ·  '+name);text.setWordWrap(True);row.addWidget(text,1);button=QPushButton('교체' if self.session else '열기');row.addWidget(button);dialog.body.addLayout(row)
            def choose(checked=False,side=side):
                dialog.reject();QTimer.singleShot(0,lambda:self.open_files(side if self.session else 'all'))
            button.clicked.connect(choose)
            if side=='comparison' and self.session:
                add=QPushButton('추가');add.setToolTip('비교파일을 더 선택해 현재 목록 뒤에 순서대로 취합합니다.');row.addWidget(add)
                add.clicked.connect(lambda checked=False:(dialog.reject(),QTimer.singleShot(0,lambda:self.open_files('append'))))
        dialog.exec()
    def more_popup(self):
        if not self.popup_ready(self.more_button):return
        from PySide6.QtWidgets import QTabWidget,QPushButton,QListWidget
        self.popup_trigger_rect=None;self.popup_anchor=self.more_button;dialog=Dialog(self,'더보기');dialog.resize(650,430);tabs=QTabWidget();dialog.body.addWidget(tabs)
        screen=ScreenDialog(self);screen.setWindowFlags(Qt.WindowType.Widget);tabs.addTab(screen,'화면 설정')
        screen.accepted.connect(lambda:(self.apply_screen(screen),dialog.accept()));screen.rejected.connect(dialog.reject)
        presets=PresetsDialog(self);presets.setWindowFlags(Qt.WindowType.Widget);tabs.addTab(presets,'프리셋');presets.accepted.connect(lambda:(self.load_profile(presets.selected_profile),dialog.accept()));presets.rejected.connect(dialog.reject)
        shortcuts=QLabel('Ctrl+F    검색\n\nCtrl+S    수정 다운로드\n\nCtrl+Enter    반영 후 다음\n\nCtrl+Z / Ctrl+Y    실행 취소 / 다시 실행\n\nCtrl+C    선택한 셀 복사\n\nCtrl+Q / Ctrl+E    이전 / 다음 변경\n\nSpace    선택한 변경 반영 전환\n\n우클릭    해당 변경 반영 전환\n\nCtrl+0 / Ctrl+9    선택한 열 / 행 숨기기\n\nCtrl+휠    표 배율\n\nShift+휠    가로 스크롤');shortcuts.setMargin(20);tabs.addTab(shortcuts,'단축키')
        sample=QWidget();box=QVBoxLayout(sample);items=QListWidget();box.addWidget(items)
        from sample_catalog import CATALOG as SAMPLE_SETS
        for sid,entry in SAMPLE_SETS.items():items.addItem(entry['label']);items.item(items.count()-1).setData(Qt.ItemDataRole.UserRole,sid)
        button=QPushButton('불러오기');box.addWidget(button)
        def load_sample():
            item=items.currentItem()
            if item:dialog.accept();self.open_sample(item.data(Qt.ItemDataRole.UserRole))
        from PySide6.QtWidgets import QPlainTextEdit
        explanation=QPlainTextEdit();explanation.setReadOnly(True);explanation.setMaximumHeight(130);box.addWidget(explanation)
        def explain():
            item=items.currentItem()
            if not item:return
            sid=item.data(Qt.ItemDataRole.UserRole);legacy=SAMPLE_SETS[sid]['legacy']
            if legacy=='16':explanation.setPlainText('같은 설비대장 원본500행을10명에게 배포한 뒤 받은 회신입니다. 서로 다른 수정·동일 셀 충돌·담당자 덮어쓰기·부분 제출을 검토합니다. 현재 순차 취합은 앞사람의 수정을 원복할 수 있으므로 결과를 확인하세요. 공통 원본 기준의 충돌 자동 해결 기능은 아닙니다.')
            else:
                from sample_descriptions import DESCRIPTIONS
                description=DESCRIPTIONS[legacy];explanation.setPlainText(description[1]+'\n\n'+description[5])
        items.currentRowChanged.connect(explain);button.clicked.connect(load_sample);tabs.addTab(sample,'테스트 샘플');info=QPushButton('프로그램 정보·라이선스');info.clicked.connect(self.about);dialog.body.addWidget(info);dialog.exec()
    def apply_screen(self,dialog):
        self.wrap=dialog.wrap.isChecked();self.heights_dirty=True;self.hide_columns=dialog.hide.isChecked();font=dialog.font.currentFont();font.setPixelSize(13);self.setFont(font);self.preferences.setValue('font',self.font().toString());self.preferences.setValue('wrap',self.wrap);self.preferences.setValue('hideColumns',self.hide_columns);self.preferences.setValue('startView',dialog.start.currentText());self.apply_theme(dialog.theme.currentData());self.refresh()
    def screen_dialog(self):
        dialog=ScreenDialog(self)
        if dialog.exec():self.apply_screen(dialog)
    def apply_theme(self,theme):
        self.theme=theme if theme in palettes() else 'light';p=palettes()[self.theme];self.tokens=p['tokens'];self.color_cache={};self.preferences.setValue('theme',self.theme);t=self.tokens
        palette=QPalette()
        for role,key in [(QPalette.ColorRole.Window,'bg'),(QPalette.ColorRole.Base,'input'),(QPalette.ColorRole.AlternateBase,'panel'),(QPalette.ColorRole.Text,'text'),(QPalette.ColorRole.WindowText,'text'),(QPalette.ColorRole.Button,'panel'),(QPalette.ColorRole.ButtonText,'text'),(QPalette.ColorRole.ToolTipBase,'panel'),(QPalette.ColorRole.ToolTipText,'text')]:palette.setColor(role,QColor(t[key]))
        palette.setColor(QPalette.ColorRole.PlaceholderText,QColor(t['muted']));palette.setColor(QPalette.ColorRole.Highlight,QColor('#2563eb'));palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#ffffff'));QApplication.instance().setPalette(palette)
        icons=Path(__file__).with_name('icons');suffix='dark' if p['base']=='dark' else 'light'
        arrow=(icons/f'down-{suffix}.svg').as_posix();arrow_up=(icons/f'up-{suffix}.svg').as_posix()
        self.setStyleSheet(f"""
          QWidget {{font-size:13px}}
          QToolButton,QPushButton {{color:{t['text']};background:{t['input']};padding:6px 10px;border:1px solid {t['control']};border-radius:5px;min-height:20px}}
          QToolButton:hover,QPushButton:hover {{background:{t['hover']}}}
          QWidget#navRow QToolButton {{padding:3px 9px;min-height:22px}}
          QWidget#navRow QToolButton:checked {{background:{t['hover']};color:{t['text']};border-color:{t['control']}}}
          QToolButton#accent {{background:{t['panel']};border:1px solid #2563eb;color:#2563eb;font-weight:600}} QToolButton#accent:hover {{background:{t['hover']}}} QToolButton#accent:disabled {{border:1px solid {t['border']};color:{t['muted']};font-weight:400}} QFrame#divider {{background:{t['border']};border:0}}
          QToolButton:checked,QToolButton#primary {{background:#2563eb;border-color:#2563eb;color:white}}
          QToolButton:disabled,QPushButton:disabled {{color:{t['muted']}}}
          QWidget#menuRow QToolButton {{border:1px solid transparent;background:transparent;padding:4px 10px;min-height:24px}}
          QWidget#welcome {{background:{t['input']};border:1px solid {t['border']};border-radius:14px}}
          QWidget#welcome QLabel {{background:transparent}}
          QLabel#welcomeTitle {{color:{t['text']};font-size:22px;font-weight:700}}
          QLabel#welcomeSub {{color:{t['muted']};font-size:13px}}
          QFrame#welcomeZone {{background:{t['panel']};border:2px dashed {t['control']};border-radius:12px}}
          QLabel#welcomeZoneTitle {{color:{t['text']};font-size:18px;font-weight:700}}
          QStatusBar {{background:{t['panel']};color:{t['muted']};border-top:1px solid {t['border']}}}
          QStatusBar::item {{border:0}}
          QLabel#statusSummary {{color:{t['muted']};font-size:12px;padding:0 8px}}
          QLabel#toast {{background:{t['panel']};color:{t['text']};border:1px solid {t['border']};border-radius:8px;padding:10px 16px;font-size:14px}}
          QLabel#toast[kind="warn"] {{border-left:4px solid #d97706}} QLabel#toast[kind="ok"] {{border-left:4px solid #16a34a}} QLabel#toast[kind="error"] {{border-left:4px solid #dc2626}} QLabel#toast[kind="info"] {{border-left:4px solid #2563eb}}
          QFrame#busyPanel {{background:{t['panel']};border:1px solid {t['border']};border-radius:10px}}
          QFrame#busyPanel QLabel {{color:{t['text']};font-size:14px}}
          QProgressBar {{background:{t['input']};border:0;border-radius:4px}}
          QProgressBar::chunk {{background:#2563eb;border-radius:4px}}
          QWidget#menuRow {{border-bottom:1px solid {t['border']};padding-bottom:6px}}
          QWidget#menuRow QToolButton:pressed {{background:{t['border']}}}
          QWidget#menuRow QToolButton:hover {{background:{t['hover']}}}
          QWidget#menuRow QToolButton#editToggle:checked {{background:#2563eb;color:white;border:1px solid #60a5fa;font-weight:600}}
          QWidget#menuRow QToolButton#editToggle:checked:hover {{background:#1d4ed8;color:white}}
          QToolButton#choice {{padding:4px 8px;font-size:12px;min-height:20px}}
          QFrame#options {{background:{t['panel']};border:1px solid {t['border']};border-radius:9px}}
          QFrame#options QWidget {{background:transparent}}
          QFrame#options QLabel {{color:{t['muted']};font-size:12px}}
          QFrame#options QToolButton {{background:{t['input']}}}
          QFrame#options QToolButton:checked {{background:#2563eb;color:white;border-color:#60a5fa}}
          QLineEdit,QComboBox,QSpinBox {{background:{t['input']};color:{t['text']};padding:6px 8px;border:1px solid {t['control']};border-radius:5px;min-height:20px}}
          QToolButton:focus,QPushButton:focus,QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QWidget#menuRow QToolButton:focus {{border:1px solid {t['ring']}}}
          QTableView:focus,QListView:focus {{border:1px solid {t['ring']}}}
          QSpinBox {{padding-right:26px}}
          QSpinBox::up-button,QSpinBox::down-button {{subcontrol-origin:border;width:22px;border:0;border-left:1px solid {t['border']};background:transparent}}
          QSpinBox::up-button {{subcontrol-position:top right;border-top-right-radius:5px}}
          QSpinBox::down-button {{subcontrol-position:bottom right;border-bottom-right-radius:5px;border-top:1px solid {t['border']}}}
          QSpinBox::up-button:hover,QSpinBox::down-button:hover {{background:{t['hover']}}}
          QSpinBox::up-arrow {{image:url("{arrow_up}");width:10px;height:10px}}
          QSpinBox::down-arrow {{image:url("{arrow}");width:10px;height:10px}}
          QTabWidget::pane {{border:0;background:transparent;top:-1px}}
          QTabBar {{background:transparent}}
          QTabBar::tab {{background:transparent;color:{t['muted']};padding:7px 14px;border:0;border-bottom:2px solid transparent;margin-right:2px}}
          QTabBar::tab:hover {{color:{t['text']}}}
          QTabBar::tab:selected {{color:{t['text']};border-bottom:2px solid #2563eb}}
          QTabWidget QDialog {{border:0;background:transparent}}
          QComboBox::drop-down {{border:0;width:22px}}
          QComboBox::down-arrow {{image:url("{arrow}");width:12px;height:12px}}
          QLabel#supportText {{font-size:11px;color:{t['muted']};font-weight:400}}
          QComboBox QAbstractItemView {{background:{t['input']};color:{t['text']};selection-background-color:#2563eb;selection-color:white;outline:0;border:1px solid {t['border']};border-radius:6px}}
          QComboBox QAbstractItemView::item {{min-height:30px;padding:4px 10px}}
          QComboBox QAbstractItemView::item:selected {{background:#2563eb;color:white}}
          QComboBox QAbstractItemView::item:hover {{background:{t['hover']};color:{t['text']}}}
          QComboBox QAbstractItemView::item:selected:hover {{background:#2563eb;color:white}}
          QFrame#pane {{border:1px solid {t['border']};border-radius:8px;background:{t['input']}}}
          QLabel#paneTitle {{background:{t['panel']};border-bottom:1px solid {t['border']};font-weight:600;border-top-left-radius:7px;border-top-right-radius:7px}}
          QHeaderView::section {{font-size:11px;padding:5px;background:{t['panel']};border:0;border-right:1px solid {t['border']};border-bottom:1px solid {t['border']}}}
          QTableView {{font-size:12px;background:{t['input']};gridline-color:{t['border']};border:1px solid transparent;selection-background-color:{t['hover']};selection-color:{t['text']}}}
          QListView,QListWidget {{background:{t['input']};color:{t['text']};border:1px solid transparent;outline:0}}
          QMenu,QDialog {{background:{t['panel']};color:{t['text']};border:1px solid {t['border']};border-radius:8px}}
          QMenu::item {{padding:8px 14px}} QMenu::item:selected {{background:{t['hover']}}}
          QScrollBar:vertical {{background:transparent;width:18px;margin:0}}
          QScrollBar::handle:vertical {{background:rgba(125,139,160,120);min-height:30px;border-radius:4px;margin:0 5px}}
          QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0}}
          QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent}}
          QSplitter::handle {{background:transparent}}
        """)
        if hasattr(self,'fold_button') and hasattr(self,'edit_button'):self.refresh_menu_icons()
        self.undo_button.setIcon(symbol('undo',t['muted']));self.redo_button.setIcon(symbol('redo',t['muted']));self.refresh(self.session)

    def profile(self,name):
        s=self.session
        return clean_profile(dict(version=1,name=name,mapping=s.mapping,keys=s.keys,mode='행 단위' if s.row_mode else '셀 단위',copy_mode=s.copy_mode,order='직접 정렬' if s.sort_columns else '원본 순서 유지',sort_columns=s.sort_columns,sort_direction='내림차순' if s.descending else '오름차순',sort_type=s.sort_type,comparison_rules=s.rules,old_headers=s.headers,new_headers=s.right.headers,**s.layout))
    def presets_dialog(self):
        dialog=PresetsDialog(self)
        if dialog.exec():self.load_profile(dialog.selected_profile)
    def load_profile(self,p):
        if p and self.session:
            s=self.session.clone()
            def apply():
                s.row_mode=p.get('mode')=='행 단위';s.copy_mode=p.get('copy_mode','일반 복사');s.sort_columns=p.get('sort_columns',[]);s.descending=p.get('sort_direction')=='내림차순';s.sort_type=p.get('sort_type','자동');s.configure(keys=p['keys'],mapping=p['mapping'],layout={k:p.get(k,s.layout[k]) for k in s.layout},rules=p.get('comparison_rules'));return s
            self.run(apply)
    def open_files(self,side):
        filters='Excel (*.xlsx *.xlsm *.xls *.csv)';s=self.session
        if side=='append' and s:
            added,_=QFileDialog.getOpenFileNames(self,'추가할 비교파일 선택 — 선택 순서대로 뒤에 취합','',filters)
            if added:self.load_paths(None,added,append=True)
            return
        if side in ('all','original'):
            path,_=QFileDialog.getOpenFileName(self,'원본 파일','',filters)
            if not path:return
            original=path
        else:original=None
        if side in ('all','comparison'):
            comparisons,_=QFileDialog.getOpenFileNames(self,'비교파일 선택 — 선택 순서대로 취합','',filters)
            if not comparisons:return
        elif s:comparisons=None
        else:comparisons,_=QFileDialog.getOpenFileNames(self,'비교파일 선택','',filters)
        if not s and not comparisons:return
        self.load_paths(original,comparisons)
    def load_paths(self,original,comparisons,append=False):
        """Open an original and/or comparison files; whichever side is None is kept from the current session."""
        s=self.session;self.edit_enabled=False;self.pending_original=self.pending_comparisons=None;self.toast.hide()
        paths={str(Path(p).resolve()) for p in ([original] if original else [])+(comparisons or [])};self.source_paths|=paths
        def load():
            base=Path(original).read_bytes() if original else s.flow['queue_versions'][-1][0] if s.flow['queue_complete'] else s.old
            name=Path(original).name if original else s.names[0]
            kept=list(s.flow['comparison_queue'][s.flow['queue_index']:]) if append and s else []
            incoming=kept+[(Path(p).read_bytes(),Path(p).name) for p in comparisons] if comparisons else s.flow['comparison_queue'][s.flow['queue_index']:]
            return Session(base,incoming,name)
        self.run(load,'파일을 읽고 비교하는 중…')
    SUPPORTED=('.xlsx','.xlsm','.xls','.csv')
    def dragEnterEvent(self,event):
        if self.busy or not event.mimeData().hasUrls() or not self.dropped_files(event.mimeData()):event.ignore();return
        event.acceptProposedAction();self.drop_overlay.show_over(self.tokens)
    def dragMoveEvent(self,event):
        self.drop_overlay.set_zone(self.drop_overlay.zone_at(event.position().x()-self.root.x()));event.acceptProposedAction()
    def dragLeaveEvent(self,event):self.drop_overlay.hide()
    def dropped_files(self,mime):
        return [url.toLocalFile() for url in mime.urls() if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in self.SUPPORTED and Path(url.toLocalFile()).is_file()]
    def dropEvent(self,event):
        zone=self.drop_overlay.zone_at(event.position().x()-self.root.x());self.drop_overlay.hide();files=self.dropped_files(event.mimeData())
        if self.busy or not files:event.ignore();return
        event.acceptProposedAction();self.accept_dropped(zone,files)
    def accept_dropped(self,zone,files):
        """zone 0 = original (one file), zone 1 = comparison files. Without a session the first side waits for the other."""
        if zone==0:
            if self.session:self.load_paths(files[0],None);return
            self.pending_original=files[0]
            if self.pending_comparisons:self.load_paths(self.pending_original,self.pending_comparisons);return
            self.show_toast('원본: '+Path(files[0]).name+(' (첫 파일만 사용)' if len(files)>1 else '')+' — 비교 파일을 오른쪽에 놓으세요.')
        else:
            if self.session:self.load_paths(None,files);return
            self.pending_comparisons=files
            if self.pending_original:self.load_paths(self.pending_original,self.pending_comparisons);return
            self.show_toast('비교 파일 '+str(len(files))+'개 — 원본을 왼쪽에 놓으세요.')
    def show_toast(self,text,milliseconds=0,kind='info'):
        """One notification style for everything non-blocking: kind is info, warn, ok or error (coloured left bar)."""
        self.toast.setProperty('kind',kind);self.toast.style().unpolish(self.toast);self.toast.style().polish(self.toast)
        self.toast.setText(text);self.toast.setWordWrap(True);self.toast.setMaximumWidth(max(300,self.root.width()-80));self.toast.adjustSize();self.toast.move((self.root.width()-self.toast.width())//2,self.root.height()-self.toast.height()-24);self.toast.show();self.toast.raise_()
        if milliseconds:QTimer.singleShot(milliseconds,lambda:self.toast.setVisible(False) if self.toast.text()==text else None)
    def open_sample(self,sid):
        self.edit_enabled=False;self.source_paths=set()
        def load():
            from sample_catalog import load_sample
            old,incoming,name=load_sample(sid);return Session(old,incoming,name)
        self.run(load,'샘플을 불러오는 중…')
    def advance(self,skip=False):
        if not self.session:return
        if not skip and self.session.flow['queue_index']+1>=len(self.session.flow['comparison_queue']):return
        s=self.session.clone();self.run(lambda:(s.next(skip),s)[1],'다음 파일을 준비하는 중…')
    def previous(self):
        if self.session and (self.session.flow['queue_index']>0 or self.session.flow['queue_complete']):
            s=self.session.clone();self.run(lambda:(s.previous(),s)[1],'이전 파일을 불러오는 중…')
    def save_dialog(self):
        if not self.session or not self.session.rows:return
        extension='.xlsm' if self.session.names[0].lower().endswith('.xlsm') else '.xlsx';path,_=QFileDialog.getSaveFileName(self,'수정 파일 저장','수정'+extension,'Excel (*'+extension+')')
        if not path:return
        destination=Path(path)
        if not destination.suffix:destination=destination.with_suffix(extension)
        if destination.suffix.lower()!=extension:raise ValueError('저장 확장자는 '+extension+'로 지정하세요.')
        if str(destination.resolve()) in self.source_paths:raise ValueError('원본·비교파일을 덮어쓸 수 없습니다. 다른 이름으로 저장하세요.')
        s=self.session.clone()
        blank=s.row_blanked_columns() if s.row_mode else []
        if blank and QApplication.platformName()!='offscreen' and QMessageBox.question(self,'행 단위 저장','행 단위로 저장하면 승인한 행에서 연결 안 한 열 '+str(len(blank))+'개가 빈칸이 됩니다: '+', '.join(blank[:8])+(' 외' if len(blank)>8 else '')+'.\n계속 저장할까요? (셀 단위로 바꾸면 연결 안 한 열은 그대로 남습니다.)')!=QMessageBox.StandardButton.Yes:return
        def save():
            result=s.save();temporary=None
            try:
                with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as file:temporary=Path(file.name);file.write(result.data)
                os.replace(temporary,destination)
            finally:
                if temporary and temporary.exists():temporary.unlink()
            if s.flow['queue_index']+1==len(s.flow['comparison_queue']):s.remember();collection_flow.advance(s.flow,s.engine_selected(),result.data,{'old_header':s.left.header_row,'old_start':s.left.start_row})
            s.saved_signature=s.signature()
            return s
        self.run(save,'수정 파일을 저장하는 중…',False,lambda:self.show_toast('저장했습니다: '+destination.name,4000,'ok'))
    def closeEvent(self,event):
        if self.busy:QMessageBox.information(self,'처리 중','파일 처리가 끝난 뒤 종료하세요.');event.ignore();return
        if self.session and self.session.signature()!=self.session.saved_signature and QMessageBox.question(self,'종료','저장하지 않은 변경이 있습니다. 종료할까요?')!=QMessageBox.StandardButton.Yes:event.ignore();return
        self.preferences.sync();event.accept()
