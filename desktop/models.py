"""Virtual Qt table/list models: no widget or item is allocated for each data cell."""
from collections import OrderedDict
import json
from html import escape
from PySide6.QtCore import Qt,QPoint,QAbstractTableModel,QAbstractListModel,QModelIndex,QSize,Signal,QRect,QPointF,QRectF
from PySide6.QtGui import QColor,QTextDocument,QPalette,QFont,QPen,QBrush,QPainter
from PySide6.QtWidgets import QStyledItemDelegate,QStyle,QStyleOptionViewItem,QTableView,QListView,QAbstractItemView,QHeaderView,QScrollBar,QStyleOptionButton
from openpyxl.utils import get_column_letter
from .motion import SmoothScroll,ChangeRail,MARK_COLORS

# PySide enum attribute lookups and flag combinations are slow in per-cell code; resolve them once.
R_DISPLAY=Qt.ItemDataRole.DisplayRole;R_EDIT=Qt.ItemDataRole.EditRole;R_CHECK=Qt.ItemDataRole.CheckStateRole
R_BACKGROUND=Qt.ItemDataRole.BackgroundRole;R_FOREGROUND=Qt.ItemDataRole.ForegroundRole;R_TOOLTIP=Qt.ItemDataRole.ToolTipRole;R_ALIGN=Qt.ItemDataRole.TextAlignmentRole
GRID_ROLES=frozenset((R_DISPLAY,R_EDIT,R_CHECK,R_BACKGROUND,R_FOREGROUND,R_TOOLTIP,R_ALIGN))
SELECTION_FILL=QColor(37,99,235,46)
CELL_TEXT_FLAGS=Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextSingleLine
CELL_TEXT_FLAGS_RIGHT=Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight|Qt.TextFlag.TextSingleLine
ELIDE_RIGHT=Qt.TextElideMode.ElideRight;STATE_SELECTED=QStyle.StateFlag.State_Selected


def blend(front,back,amount):
    """Mix two colours; used to dim text without the unreadable pure grey."""
    a,b=QColor(front),QColor(back)
    return QColor(round(a.red()*amount+b.red()*(1-amount)),round(a.green()*amount+b.green()*(1-amount)),round(a.blue()*amount+b.blue()*(1-amount)))


class GridModel(QAbstractTableModel):
    def __init__(self,window,pane):super().__init__(window);self.window=window;self.pane=pane;self.role_cache={};self.cache_revision=-1
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.window.visible_rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() or not self.window.session else len(self.window.columns)+2
    def source_index(self,index):return self.window.visible_rows[index.row()]
    def merged(self):return self.window.combined and self.pane==0
    def change(self,row,col,i=None):
        changes=self.window.session.review_changes(i if i is not None else self.window.session.tokens[json.dumps(row['key'],ensure_ascii=False)])
        return next((c for c in changes if c['column']==col and c['kind']=='수정'),None) or next((c for c in changes if c['kind']!='수정'),None)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if role not in GRID_ROLES:return None
        if not index.isValid() or index.row()>=len(self.window.visible_rows):return None
        revision=self.window.review_revision
        if self.cache_revision!=revision:self.role_cache.clear();self.cache_revision=revision
        key=(index.row(),index.column(),role)
        if key not in self.role_cache:
            if len(self.role_cache)>24000:self.role_cache.clear()
            self.role_cache[key]=self.cell_data(index,role)
        return self.role_cache[key]
    def cell_data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not self.window.session:return None
        s=self.window.session;i=self.source_index(index);row=s.rows[i];column=index.column()
        if role==Qt.ItemDataRole.TextAlignmentRole:
            if column==0:return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter) if column>=2 and self.window.columns[column-2] in self.window.numeric_columns() else None
        if column<2 and role==Qt.ItemDataRole.BackgroundRole:return self.row_tint(i,True) or QColor(self.window.tokens['panel'])
        if column==0:
            if role==Qt.ItemDataRole.DisplayRole:return f"{row['beforeRow'] or '—'} ↔ {row['incomingRow'] or '—'}" if self.merged() or self.pane==2 else str((row['beforeRow'] if self.pane==0 else row['incomingRow']) or '—')
            return None
        if column==1:
            if role==Qt.ItemDataRole.DisplayRole:return row['label']
            if role==Qt.ItemDataRole.CheckStateRole and self.cell_changes(i,1):
                changes=self.cell_changes(i,1);n=sum(c['id'] in s.selected for c in changes)
                return Qt.CheckState.Checked if n==len(changes) else Qt.CheckState.PartiallyChecked if n else Qt.CheckState.Unchecked
            return None
        col=self.window.columns[column-2];pane=self.pane;merged=self.merged();change=self.change(row,col,i)
        value=s.results[i] if pane==2 else s.source(i,pane)
        if merged:value=s.source(i,0) or s.source(i,1)
        if role==Qt.ItemDataRole.CheckStateRole:
            if s.row_mode:return None
            if not self.merged() and (s.results[i] if self.pane==2 else s.source(i,self.pane)) is None:return None
            changes=[c for c in self.cell_changes(i,column) if c['kind']=='수정']
            if changes:return Qt.CheckState.Checked if all(c['id'] in s.selected for c in changes) else Qt.CheckState.Unchecked
            return None
        if role==Qt.ItemDataRole.EditRole:return str(s.raw_result(i,col))
        if role==Qt.ItemDataRole.DisplayRole:
            if merged and s.results[i] is not None and col in s.overrides.get(tuple(row['key']),{}):return s.value(i,2,col)
            return '' if value is None else s.value(i,pane,col) if not merged else str(value.get(col,'') or '')
        if role==Qt.ItemDataRole.ToolTipRole:
            original=self.headerData(column,Qt.Orientation.Horizontal,Qt.ItemDataRole.DisplayRole).replace('\n',' ')
            return original+'\n'+str((value or {}).get(col,'') or '')+(' → '+s.value(i,2,col) if merged and change else '')
        if role in (Qt.ItemDataRole.BackgroundRole,Qt.ItemDataRole.ForegroundRole):
            kind=None
            if col in s.overrides.get(tuple(row['key']),{}) and s.results[i] is not None and (merged or pane==2):kind='edit'
            elif change and value is not None:
                if change['kind']=='추가' and (merged or pane==1 or pane==2 and change['id'] in s.selected):kind='add'
                elif change['kind']=='삭제' and (merged or pane==0):kind='delete'
                elif change['kind']=='수정' and (merged or pane!=2 or change['id'] in s.selected):kind='edit'
            if kind:
                if role==Qt.ItemDataRole.ForegroundRole:
                    color=QColor(self.window.tokens[kind+'-text'])
                    # Merged view: added text is bright when applied, deleted text is bright while it is kept.
                    if merged and change and (change['kind']=='추가' and change['id'] not in s.selected or change['kind']=='삭제' and change['id'] in s.selected) and not (col in s.overrides.get(tuple(row['key']),{})):color=blend(color,self.window.tokens[kind],.42)
                    return color
                return QColor(self.window.tokens[kind])
            if row.get('structure'):return QColor(self.window.tokens['panel']) if role==Qt.ItemDataRole.BackgroundRole else None
            # Values copied down/across from a merged cell are shown dimmer than the cell that really holds them.
            if role==Qt.ItemDataRole.ForegroundRole and col in row.get('incomingFilled' if pane==1 and not merged else 'beforeFilled',()) and (index.row(),index.column()) not in getattr(self,'span_starts',()):return QColor(self.window.tokens['muted'])
            if role==Qt.ItemDataRole.BackgroundRole:return self.row_tint(i,False)
        return None
    def row_tint(self,i,strong):
        """Row mode: show that the whole row is part of a change, not only the changed cells."""
        s=self.window.session
        if not s.row_mode:return None
        kinds={c['kind'] for c in s.review_changes(i)}
        kind=next((k for k in ('수정','추가','삭제') if k in kinds),None)
        if kind is None or self.pane==2 and not any(c['id'] in s.selected for c in s.review_changes(i)):return None
        token={'수정':'edit','추가':'add','삭제':'delete'}[kind];color=QColor(self.window.tokens[token])
        if not strong:color.setAlpha(90)
        return color
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        s=self.window.session
        if orientation==Qt.Orientation.Vertical:return '' if role==Qt.ItemDataRole.DisplayRole else None
        if not s:return None
        col=['__row__','__key__'][section] if section<2 else self.window.columns[section-2]
        active=bool(s.view_sort and s.view_sort[:2]==(2 if self.merged() else self.pane,col))
        if role==Qt.ItemDataRole.FontRole:
            font=QFont(self.window.font());font.setPixelSize(round(11*self.window.scale/100));font.setBold(active);return font
        if role==Qt.ItemDataRole.TextAlignmentRole:return int((Qt.AlignmentFlag.AlignHCenter if section==0 else Qt.AlignmentFlag.AlignLeft)|Qt.AlignmentFlag.AlignVCenter)
        if role!=Qt.ItemDataRole.DisplayRole:return None
        arrow=(' ↓' if s.view_sort[2] else ' ↑') if active else ''
        if section<2:return ['행','기준값'][section]+arrow
        old=get_column_letter(s.headers.index(col)+1);incoming=s.mapping.get(col);new=get_column_letter(s.right.headers.index(incoming)+1) if incoming in s.right.headers else '—'
        return (old+' ↔ '+new if self.merged() or self.pane==2 else new if self.pane==1 else old)+'\n'+col+arrow
    def cell_changes(self,i,column):
        s=self.window.session;changes=s.review_changes(i)
        if s.row_mode:return changes if column>=1 else []
        if column==1:return [c for c in changes if c['kind']!='수정']
        if column<2:return []
        col=self.window.columns[column-2];return [c for c in changes if c['kind']!='수정' or c['column']==col]
    def flags(self,index):
        flags=Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable
        if not index.isValid():return flags
        s=self.window.session;row=s.rows[self.source_index(index)]
        if self.data(index,Qt.ItemDataRole.CheckStateRole) is not None:flags|=Qt.ItemFlag.ItemIsUserCheckable
        if index.column()>1 and self.window.edit_enabled and not row.get('structure') and (self.pane==2 or self.merged()) and s.results[self.source_index(index)] is not None and self.window.columns[index.column()-2]!=s.sequence:flags|=Qt.ItemFlag.ItemIsEditable
        return flags
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if not index.isValid():return False
        i=self.source_index(index);s=self.window.session
        if role==Qt.ItemDataRole.CheckStateRole:
            ids=[c['id'] for c in self.cell_changes(i,index.column())];self.window.choose(ids,value==Qt.CheckState.Checked or value==2);return True
        if role==Qt.ItemDataRole.EditRole and self.flags(index)&Qt.ItemFlag.ItemIsEditable:
            col=self.window.columns[index.column()-2]
            if str(value)==str(s.raw_result(i,col)):return False
            self.window.mutate(lambda new:new.edit(i,col,str(value)));return True
        return False
    def merged_html(self,index):
        if not self.merged() or index.column()<2:return None
        # Painting and sizing ask for the same cell repeatedly while scrolling; reuse until the next review revision.
        if self.cache_revision!=self.window.review_revision:self.role_cache.clear();self.cache_revision=self.window.review_revision
        key=(index.row(),index.column(),'html')
        if key not in self.role_cache:self.role_cache[key]=self.build_merged_html(index)
        return self.role_cache[key]
    def build_merged_html(self,index):
        w=self.window;s=w.session;i=self.source_index(index);row=s.rows[i];col=w.columns[index.column()-2];change=self.change(row,col,i);manual=col in s.overrides.get(tuple(row['key']),{}) and s.results[i] is not None
        old=str((s.source(i,0) or {}).get(col,'') or '')
        if not change and not manual:
            # Row mode copies whole rows: show cells that end up different even though they are not listed as changes.
            if s.results[i] is not None and s.row_copied(i) and col not in s.keys and col!=s.sequence:
                new=s.value(i,2,col)
                if new!=old:
                    bright=w.tokens['edit-text'];dim=blend(bright,w.tokens['edit'],.42).name()
                    return '<div><span style="color:'+dim+'"><s>'+escape(old or '(빈 값)')+'</s></span><br><b style="color:'+bright+'">'+escape(new or '(빈 값)')+'</b></div>'
            return None
        if change and change['kind']=='삭제' and not manual:
            # Applied deletion is struck through and dimmed; a kept row is plain and bright.
            if change['id'] not in s.selected:return None
            # The rich-text document ignores the painter pen, so the dimmed colour must be written into the markup.
            return '<span style="color:'+blend(w.tokens['delete-text'],w.tokens['delete'],.42).name()+'"><s>'+escape(old)+'</s></span>'
        if manual or change and change['kind']=='수정':
            new=s.value(i,2,col) if manual else s.candidate(i,col)
            if manual:return '<div><s>'+escape(old or '(빈 값)')+'</s><br><b>'+escape(new or '(빈 값)')+'</b></div>'
            on=change['id'] in s.selected;bright=w.tokens['edit-text'];dim=blend(bright,w.tokens['edit'],.42).name()
            # Applied: the comparison value is bright and the original is struck; reverted: the reverse.
            first=('<span style="color:'+dim+'"><s>'+escape(old or '(빈 값)')+'</s></span>') if on else ('<b style="color:'+bright+'">'+escape(old or '(빈 값)')+'</b>')
            second=('<b style="color:'+bright+'">'+escape(new or '(빈 값)')+'</b>') if on else ('<span style="color:'+dim+'"><s>'+escape(new or '(빈 값)')+'</s></span>')
            return '<div>'+first+'<br>'+second+'</div>'
        return None


class MergeDelegate(QStyledItemDelegate):
    def __init__(self,parent):super().__init__(parent);self.cache=OrderedDict()
    def editorEvent(self,event,model,option,index):
        if index.model().flags(index)&Qt.ItemFlag.ItemIsUserCheckable:
            return super().editorEvent(event,model,option,index)
        return super().editorEvent(event,model,option,index)
    def paint(self,painter,option,index):
        model=index.model();w=model.window;s=w.session;i=model.source_index(index);html=model.merged_html(index)
        selected=bool(option.state&STATE_SELECTED)
        self._paint_background(painter,option,index,model,w,html)
        self._paint_missing_hatch(painter,option,index,model,w,s,i)
        if html is not None:self._paint_merged_text(painter,option,index,model,w,html)
        if index.column()==1:self._paint_key_column(painter,option,index,model,w,s,i)
        if selected:self._paint_selection(painter,option)
    def _paint_background(self,painter,option,index,model,w,html):
        """Plain cells use the fast text path; everything else goes through the style."""
        fast=html is None and index.column()>=2 and not w.wrap and model.data(index,R_CHECK) is None
        if fast:
            background=model.data(index,R_BACKGROUND) or w.token_color('hover' if index.row()==w.hover_row else 'input');foreground=model.data(index,R_FOREGROUND) or w.token_color('text');painter.save();painter.fillRect(option.rect,background);painter.setFont(option.font);painter.setPen(foreground);text=str(model.data(index,R_DISPLAY) or '');painter.drawText(option.rect.adjusted(6,0,-6,0),CELL_TEXT_FLAGS_RIGHT if index.column()-2 in w.numeric_positions() else CELL_TEXT_FLAGS,painter.fontMetrics().elidedText(text,ELIDE_RIGHT,max(1,option.rect.width()-12)));painter.restore()
        else:
            opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);opt.state&=~STATE_SELECTED
            if html is not None or index.column()==1:opt.text=''
            style=opt.widget.style();style.drawControl(QStyle.ControlElement.CE_ItemViewItem,opt,painter,opt.widget)
    def _paint_missing_hatch(self,painter,option,index,model,w,s,i):
        """Hatch cells whose row does not exist in this pane."""
        if index.column()>=2 and not model.merged() and (s.results[i] if model.pane==2 else s.source(i,model.pane)) is None:
            painter.save();painter.setClipRect(option.rect);color=QColor(w.tokens['border']);color.setAlpha(100);painter.fillRect(option.rect,QBrush(color,Qt.BrushStyle.BDiagPattern));painter.restore()
    def _paint_merged_text(self,painter,option,index,model,w,html):
        """Draw the cached rich text of a merged/edited cell, vertically centred."""
        if html is not None:
            color=model.data(index,Qt.ItemDataRole.ForegroundRole) or option.palette.color(QPalette.ColorRole.Text)
            right=index.column()-2 in w.numeric_positions();checkbox=model.data(index,Qt.ItemDataRole.CheckStateRole) is not None
            key=(html,option.font.toString(),option.rect.width(),color.name(),w.wrap,right,checkbox);doc=self.cache.get(key)
            if doc is None:
                doc=QTextDocument();doc.setDefaultFont(option.font);doc.setDefaultStyleSheet('body{color:'+key[3]+'}');doc.setDocumentMargin(0);doc.setHtml(html);options=self.text_options(w.wrap)
                if right:options.setAlignment(Qt.AlignmentFlag.AlignRight)   # numbers keep their right edge when struck through
                doc.setDefaultTextOption(options);doc.setTextWidth(max(1,option.rect.width()-(30 if checkbox else 12)) if right else max(1,option.rect.width()-28));self.cache[key]=doc
                if len(self.cache)>512:self.cache.popitem(last=False)
            painter.save();painter.setClipRect(option.rect);painter.translate(option.rect.left()+(24 if model.data(index,Qt.ItemDataRole.CheckStateRole) is not None else 6),option.rect.top()+max(0,(option.rect.height()-doc.size().height())/2));doc.drawContents(painter);painter.restore()
    def _paint_key_column(self,painter,option,index,model,w,s,i):
        if index.column()==1:
            painter.save();painter.setFont(option.font);painter.setPen(QColor(w.tokens['text']));text=str(model.data(index,Qt.ItemDataRole.DisplayRole) or '');painter.drawText(option.rect.adjusted(24,0,-6,0),Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextSingleLine,painter.fontMetrics().elidedText(text,Qt.TextElideMode.ElideRight,max(1,option.rect.width()-30)));painter.restore()
            kinds={c['kind'] for c in s.review_changes(i)}
            kind=next((kind for kind in ['수정','추가','삭제'] if kind in kinds),None)
            if kind:painter.fillRect(option.rect.left(),option.rect.top(),4,option.rect.height(),QColor(MARK_COLORS[kind]))
    def _paint_selection(self,painter,option):
        painter.save();painter.fillRect(option.rect,SELECTION_FILL);painter.setPen(QPen(QColor('#60a5fa'),2));painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRect(option.rect.adjusted(1,1,-1,-1));painter.restore()
    @staticmethod
    def text_options(wrap):
        from PySide6.QtGui import QTextOption
        value=QTextOption();value.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere if wrap else QTextOption.WrapMode.NoWrap);return value
    def createEditor(self,parent,option,index):
        editor=super().createEditor(parent,option,index)
        if editor:
            editor.setFont(option.font);editor.setStyleSheet('QLineEdit{font-size:'+str(round(12*index.model().window.scale/100))+'px;padding:0 5px;min-height:0;border:1px solid #60a5fa;border-radius:0}')
        return editor
    def setEditorData(self,editor,index):
        super().setEditorData(editor,index)
        from PySide6.QtCore import QTimer
        view=index.model().window.views[index.model().pane];position=getattr(view,'slow_edit_position',None);view.slow_edit_position=None
        def cursor():
            try:
                if position is None:editor.selectAll()
                else:editor.setCursorPosition(editor.cursorPositionAt(editor.mapFrom(view.viewport(),position)))
            except RuntimeError:pass
        QTimer.singleShot(0,cursor)
    def sizeHint(self,option,index):
        if not index.isValid() or index.model() is None:return QSize(40,32)
        model=index.model();html=model.merged_html(index);metrics=option.fontMetrics;column=index.column()
        if html is None and column>=2 and model.data(index,Qt.ItemDataRole.CheckStateRole) is None:
            # Plain cell: measure the text directly with the same 6px side padding used when painting.
            return QSize(metrics.horizontalAdvance(str(model.data(index,Qt.ItemDataRole.DisplayRole) or ''))+16,max(metrics.height()+8,22))
        size=super().sizeHint(option,index)
        text=str(index.data() or '')
        if column==0:size.setWidth(max(size.width(),metrics.horizontalAdvance(text)+16))
        elif column==1:size.setWidth(max(size.width(),metrics.horizontalAdvance(text)+36))
        elif html is None:size.setWidth(max(size.width(),metrics.horizontalAdvance(text)+34))
        if html:
            doc=QTextDocument();doc.setDefaultFont(option.font);doc.setHtml(html);doc.setDefaultTextOption(self.text_options(model.window.wrap));size.setWidth(max(size.width(),int(doc.idealWidth())+(36 if model.data(index,Qt.ItemDataRole.CheckStateRole) is not None else 18)));doc.setTextWidth(max(1,option.rect.width()-28));size.setHeight(max(size.height(),int(doc.size().height())+8))
        return size


def _gap_pen(w):
    return QPen(w.token_color('control'),1)


def _paint_pill(painter,rect,w):
    painter.setPen(_gap_pen(w));painter.setBrush(QColor(w.tokens['input']));painter.drawRoundedRect(rect,min(rect.width(),rect.height())/2-.5,min(rect.width(),rect.height())/2-.5)
    painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(w.token_color('muted'))
    for step in (-1,0,1):
        if rect.height()>=rect.width():painter.drawEllipse(QPointF(rect.center().x(),rect.center().y()+step*4),1.1,1.1)
        else:painter.drawEllipse(QPointF(rect.center().x()+step*4,rect.center().y()),1.1,1.1)


def paint_gap_vertical(painter,rect,x,w):
    """Hidden-column marker (design B): hairlines at x-3 and x+3 and a 10x22 pill handle centred on x, kept inside `rect`."""
    painter.save();painter.setClipRect(rect);painter.setRenderHint(QPainter.RenderHint.Antialiasing,False);painter.setPen(_gap_pen(w))
    for dx in (-3,3):painter.drawLine(x+dx,rect.top()+3,x+dx,rect.bottom()-3)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
    _paint_pill(painter,QRectF(x-5,rect.center().y()-11+.5,10,22),w);painter.restore()


def paint_gap_horizontal(painter,rect,y,w):
    """Hidden-row marker (design B): hairlines at y-2 and y+2 and a 22x8 pill handle centred on y, kept inside `rect`."""
    painter.save();painter.setClipRect(rect);painter.setRenderHint(QPainter.RenderHint.Antialiasing,False);painter.setPen(_gap_pen(w))
    for dy in (-2,2):painter.drawLine(rect.left()+3,y+dy,rect.right()-3,y+dy)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
    _paint_pill(painter,QRectF(rect.center().x()-11+.5,y-4,22,8),w);painter.restore()



class FilterHeader(QHeaderView):
    def __init__(self,window,view):super().__init__(Qt.Orientation.Horizontal,view);self.window=window;self.view=view;self.setSectionsClickable(True)
    def paintEvent(self,event):
        super().paintEvent(event)
        w=self.window
        if not w.hidden_columns:return
        painter=QPainter(self.viewport())
        for column in range(2,self.count()):
            if self.isSectionHidden(column):continue
            left=self.sectionViewportPosition(column);height=self.viewport().height()
            if w.hidden_run(column-1,-1):paint_gap_vertical(painter,QRect(left-8,0,16,height),left,w)
            if column==w.last_visible_column and w.hidden_run(column+1,1):
                right=left+self.sectionSize(column);paint_gap_vertical(painter,QRect(right-8,0,16,height),right,w)
        painter.end()
    def gap_hit(self,point):
        """Hidden columns whose double line is under `point` (within 4px), else []."""
        if not self.window.hidden_columns:return []
        for column in range(2,self.count()):
            if self.isSectionHidden(column):continue
            left=self.sectionViewportPosition(column)
            before=self.window.hidden_run(column-1,-1)
            if before and abs(point.x()-left)<=6:return before
            if column==self.window.last_visible_column:
                after=self.window.hidden_run(column+1,1)
                if after and abs(point.x()-(left+self.sectionSize(column)))<=6:return after
        return []
    def button_rect(self,column):return QRect(self.sectionViewportPosition(column)+self.sectionSize(column)-23,self.height()-27,20,22)
    def paintSection(self,painter,rect,column):
        painter.save();super().paintSection(painter,rect,column);painter.restore()
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        button=self.button_rect(column);active=bool(self.window.active_popover and getattr(self.window.active_popover,'request_key',None)==(self,column))
        painter.save();painter.setBrush(QColor(self.window.tokens['input']));painter.setPen(QColor(self.window.tokens['border']));painter.drawRoundedRect(button.adjusted(1,1,-1,-1),2,2);center=button.center();painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(self.window.tokens['text']));painter.drawPolygon(QPolygon([center+QPoint(-4,2 if active else -2),center+QPoint(4,2 if active else -2),center+QPoint(0,-3 if active else 3)]));painter.restore()
    def mousePressEvent(self,event):
        col=self.logicalIndexAt(event.position().toPoint())
        if col>=0 and self.button_rect(col).contains(event.position().toPoint()):
            self.window.column_menu(self.view,event.position().toPoint(),col);self.viewport().update();event.accept();return
        super().mousePressEvent(event)


class GridView(QTableView):
    def __init__(self,window,pane):
        super().__init__();self.window=window;self.pane=pane;self.setModel(GridModel(window,pane));self.setItemDelegate(MergeDelegate(self));self.setToolTipDuration(15000)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.smooth=SmoothScroll(self);self.setMouseTracking(True);self.resize_drag=None;self.key_press=None;self.setHorizontalHeader(FilterHeader(window,self));self.horizontalHeader().setFixedHeight(46);self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter);self.setAlternatingRowColors(False);self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.SelectedClicked);self.setWordWrap(False)
        self.verticalHeader().hide();self.verticalHeader().setDefaultSectionSize(32);self.horizontalHeader().setMinimumSectionSize(40);self.horizontalHeader().setResizeContentsPrecision(1000)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.horizontalHeader().customContextMenuRequested.connect(lambda point:window.header_menu(self,point))
        self.horizontalHeader().sectionResized.connect(lambda column,old,new:window.sync_column(self,column,new))
        self.verticalScrollBar().valueChanged.connect(lambda value:window.sync_scroll(self,value,False));self.horizontalScrollBar().valueChanged.connect(lambda value:window.sync_scroll(self,value,True))
        self.verticalHeader().sectionResized.connect(lambda row,old,new:window.sync_row(self,row,new));self.verticalHeader().sectionDoubleClicked.connect(self.resizeRowToContents)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel);self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.clicked.connect(lambda index:self.focus_cell(index))
    def focus_cell(self,index):
        self.window.focused_column=self.window.columns[index.column()-2] if index.column()>=2 else None;self.window.focus_row(self.model().source_index(index))
    def wheelEvent(self,event):self.smooth.wheel(event)
    def resize_edge(self,point):
        if self.columnAt(int(point.x()))!=0:return -1
        row=self.rowAt(int(point.y()))
        if row>=0 and abs(point.y()-(self.rowViewportPosition(row)+self.rowHeight(row)))<=5:return row
        previous=self.rowAt(int(point.y())-5)
        if previous>=0 and abs(point.y()-(self.rowViewportPosition(previous)+self.rowHeight(previous)))<=5:return previous
        return -1
    def movable_row(self,row):
        """Only rows that will be added can be dragged to another place."""
        s=self.window.session
        return s is not None and 0<=row<len(self.window.visible_rows) and any(c['kind']=='추가' for c in s.review_changes(self.window.visible_rows[row]))
    def drop_gap(self,y):
        row=self.rowAt(int(y))
        if row<0:return len(self.window.visible_rows) if y>0 else 0
        return row+1 if y>self.rowViewportPosition(row)+self.rowHeight(row)/2 else row
    def mousePressEvent(self,event):
        self.smooth.stop();edge=self.resize_edge(event.position())
        if edge>=0 and event.button()==Qt.MouseButton.LeftButton:
            self.resize_drag=(edge,event.position().y(),self.rowHeight(edge));event.accept();return
        index=self.indexAt(event.position().toPoint())
        if event.button()==Qt.MouseButton.LeftButton and index.isValid() and index.column()==0 and self.movable_row(index.row()):
            self.row_drag={'row':index.row(),'y':event.position().y(),'active':False,'gap':None};event.accept();return
        index=self.indexAt(event.position().toPoint());self.slow_edit_position=event.position().toPoint() if event.button()==Qt.MouseButton.LeftButton and index==self.currentIndex() else None;self.key_press=(index,event.position().toPoint()) if index.isValid() and index.column()==1 else None
        super().mousePressEvent(event)
    def paintEvent(self,event):
        super().paintEvent(event)
        w=self.window
        drag=getattr(self,'row_drag',None)
        if drag and drag['active'] and drag['gap'] is not None:
            # Where the dragged row will go: an accent line between rows.
            gap=drag['gap'];count=len(w.visible_rows)
            y=self.rowViewportPosition(gap) if gap<count else (self.rowViewportPosition(count-1)+self.rowHeight(count-1) if count else 0)
            painter=QPainter(self.viewport());painter.fillRect(QRect(0,y-1,self.viewport().width(),3),QColor(w.tokens['ring']));painter.end()
        if not w.hidden_rows:return
        painter=QPainter(self.viewport());x=self.columnViewportPosition(0);width=self.columnWidth(0)
        ys=[self.rowViewportPosition(r) for r in w.row_gaps_above]
        if w.row_gap_last is not None:ys.append(self.rowViewportPosition(w.row_gap_last)+self.rowHeight(w.row_gap_last))
        for y in ys:paint_gap_horizontal(painter,QRect(x,y-6,width,12),y,w)
        painter.end()
    def mouseMoveEvent(self,event):
        drag=getattr(self,'row_drag',None)
        if drag:
            if not drag['active'] and abs(event.position().y()-drag['y'])>6:drag['active']=True;self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            if drag['active']:drag['gap']=self.drop_gap(event.position().y());self.viewport().update()
            event.accept();return
        if self.resize_drag:
            row,y,height=self.resize_drag;self.setRowHeight(row,max(24,round(height+event.position().y()-y)));event.accept();return
        index=self.indexAt(event.position().toPoint())
        self.viewport().setCursor(Qt.CursorShape.SplitVCursor if self.resize_edge(event.position())>=0 else Qt.CursorShape.OpenHandCursor if index.isValid() and index.column()==0 and self.movable_row(index.row()) else Qt.CursorShape.ArrowCursor)
        self.window.set_hover_row(self.rowAt(int(event.position().y())))
        super().mouseMoveEvent(event)
    def leaveEvent(self,event):
        self.window.set_hover_row(-1);super().leaveEvent(event)
    def mouseReleaseEvent(self,event):
        drag=getattr(self,'row_drag',None)
        if drag:
            self.row_drag=None;self.viewport().setCursor(Qt.CursorShape.ArrowCursor);self.viewport().update()
            if drag['active'] and drag['gap'] is not None:self.window.place_row(drag['row'],drag['gap'])
            else:self.selectRow(drag['row'])
            event.accept();return
        if self.resize_drag:self.resize_drag=None;event.accept();return
        self.key_press=None;super().mouseReleaseEvent(event)
        if event.button()==Qt.MouseButton.RightButton:
            index=self.indexAt(event.position().toPoint())
            if index.isValid() and index.column()==0:self.window.row_menu(self,event.position().toPoint())
            else:self.toggle_index(index)
    def toggle_index(self,index):
        if not index.isValid():return
        changes=self.model().cell_changes(self.model().source_index(index),index.column())
        if changes:self.window.choose([c['id'] for c in changes],not all(c['id'] in self.window.session.selected for c in changes))
    def contextMenuEvent(self,event):
        event.accept()
    def resizeRowToContents(self,row):
        super().resizeRowToContents(row);self.setRowHeight(row,max(round(32*self.window.scale/100),self.rowHeight(row)))
    def mouseDoubleClickEvent(self,event):
        edge=self.resize_edge(event.position())
        if edge>=0:self.resize_drag=None;self.resizeRowToContents(edge);event.accept();return
        if self.columnAt(int(event.position().x()))==1:self.key_press=None;event.accept();return
        self.slow_edit_position=None;super().mouseDoubleClickEvent(event)


class ChangeModel(QAbstractListModel):
    def __init__(self,window):super().__init__(window);self.window=window;self.entries=[]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.entries)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not self.window.session:return None
        i,changes=self.entries[index.row()];s=self.window.session;row=s.rows[i];c=changes[0];kind=c['kind'];col=c['column'] or s.headers[0]
        if role==Qt.ItemDataRole.DisplayRole:
            name=kind+' · '+row['label']+(' · '+col if c['column'] else '')
            old=str((s.source(i,0) or {}).get(col,'') or '');new=s.candidate(i,col)
            if col in s.overrides.get(tuple(row['key']),{}):new=s.value(i,2,col)
            return name+'\n'+get_column_letter(s.headers.index(col)+1)+str(row['beforeRow'] or '—')+' ↔ '+str(row['incomingRow'] or '—')+'\n'+old+' → '+new
        if role==Qt.ItemDataRole.CheckStateRole:
            n=sum(c['id'] in s.selected for c in changes)
            return Qt.CheckState.Checked if n==len(changes) else Qt.CheckState.PartiallyChecked if n else Qt.CheckState.Unchecked
        if role==Qt.ItemDataRole.BackgroundRole:return QColor(self.window.tokens[{'추가':'add','수정':'edit','삭제':'delete'}[kind]])
        if role==Qt.ItemDataRole.ForegroundRole:return QColor(self.window.tokens[{'추가':'add','수정':'edit','삭제':'delete'}[kind]+'-text'])
        if role==Qt.ItemDataRole.SizeHintRole:return QSize(250,max(104,82+26*len(changes)) if s.row_mode and kind=='수정' else 104)
        if role==Qt.ItemDataRole.ToolTipRole:return self.data(index,Qt.ItemDataRole.DisplayRole)
        return None
    def flags(self,index):return Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsUserCheckable
    def setData(self,index,value,role):
        if role!=Qt.ItemDataRole.CheckStateRole or not index.isValid():return False
        self.window.choose([c['id'] for c in self.entries[index.row()][1]],value==Qt.CheckState.Checked or value==2);return True
    def rebuild(self):
        entries=[];s=self.window.session;view=self.window.change_list
        if s:
            for kind in ['추가','수정','삭제']:
                for i in self.window.visible_rows:
                    changes=[c for c in s.review_changes(i) if c['kind']==kind]
                    if s.row_mode and kind=='수정':
                        if changes:entries.append((i,changes))
                    else:entries.extend((i,[c]) for c in changes)
        signature=lambda items:[(i,tuple(c['id'] for c in changes)) for i,changes in items]
        if signature(entries)==signature(self.entries):
            self.entries=entries
            if entries:self.dataChanged.emit(self.index(0),self.index(len(entries)-1))
            return
        scroll=view.verticalScrollBar().value();current=view.currentIndex();identity=signature(self.entries)[current.row()] if current.isValid() else None
        self.beginResetModel();self.entries=entries;self.endResetModel()
        identities=signature(entries)
        if identity in identities:view.setCurrentIndex(self.index(identities.index(identity)))
        view.verticalScrollBar().setValue(scroll)


class ChangeDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        model=index.model();w=model.window;s=w.session;i,changes=model.entries[index.row()];row=s.rows[i];c=changes[0]
        kind=c['kind'];token={'추가':'add','수정':'edit','삭제':'delete'}[kind];on=any(change['id'] in s.selected for change in changes);rect=option.rect
        painter.save();painter.fillRect(rect,QColor(w.tokens[token] if on else w.tokens['panel']))
        if option.state&QStyle.StateFlag.State_Selected:
            painter.setPen(QPen(QColor('#60a5fa'),2));painter.drawRect(rect.adjusted(1,1,-1,-1))
        painter.setPen(QColor(w.tokens['border']));painter.drawLine(rect.bottomLeft(),rect.bottomRight())
        check=QStyleOptionButton();check.rect=rect.adjusted(12,12,0,0);check.rect.setSize(QSize(16,16));check.state=QStyle.StateFlag.State_Enabled
        check.state|=QStyle.StateFlag.State_On if all(change['id'] in s.selected for change in changes) else QStyle.StateFlag.State_NoChange if on else QStyle.StateFlag.State_Off
        option.widget.style().drawControl(QStyle.ControlElement.CE_CheckBox,check,painter,option.widget)
        col=c['column'];heading=kind+' · '+row['label']+(' · '+col if col else '')
        font=QFont(option.font);font.setPixelSize(13);font.setBold(True);painter.setFont(font);painter.setPen(QColor(w.tokens[token+'-text'] if on else w.tokens['muted']))
        painter.drawText(rect.adjusted(36,10,-10,0),Qt.AlignmentFlag.AlignTop,painter.fontMetrics().elidedText(heading,Qt.TextElideMode.ElideRight,max(1,rect.width()-50)))
        if s.row_mode and kind=='수정':self._paint_row_table(painter,rect,w,s,i,row,changes,token,font)
        else:self._paint_change_detail(painter,rect,w,s,i,row,changes,kind,token,on,font)
        painter.restore()
    def _paint_row_table(self,painter,rect,w,s,i,row,changes,token,font):
        """Row mode: one line per changed column with its original and comparison value."""
        painter.setPen(QColor(w.tokens['muted']));font.setBold(False);font.setPixelSize(11);painter.setFont(font)
        painter.drawText(rect.adjusted(12,35,-12,0),Qt.AlignmentFlag.AlignTop,f"{row['beforeRow'] or '—'}행 ↔ {row['incomingRow'] or '—'}행 · 수정 {len(changes)}개")
        width=max(20,(rect.width()-24)//3);y=rect.top()+58
        for j,title in enumerate(['항목','원본','비교']):painter.drawText(rect.left()+12+j*width,y,title)
        for change in changes:
            y+=26;name=change['column'];values=[name,str((s.source(i,0) or {}).get(name,'') or '(빈 값)'),s.candidate(i,name) or '(빈 값)']
            painter.setPen(QColor(w.tokens['border']));painter.drawLine(rect.left()+12,y+7,rect.right()-12,y+7);painter.setPen(QColor(w.tokens[token+'-text']))
            for j,value in enumerate(values):painter.drawText(rect.left()+12+j*width,y,painter.fontMetrics().elidedText(value,Qt.TextElideMode.ElideRight,width-10))
    def _paint_change_detail(self,painter,rect,w,s,i,row,changes,kind,token,on,font):
        """Cell mode: cell address and the original/new text of one change."""
        c=changes[0]
        columns=[change['column'] for change in changes if change['column']] or s.headers[:1];address=[]
        for pane,label,r in [(0,'원본',row['beforeRow']),(1,'비교',row['incomingRow'])]:
            name=columns[0] if pane==0 else s.mapping.get(columns[0])
            headers=s.headers if pane==0 else s.right.headers
            if r and name in headers:address.append(get_column_letter(headers.index(name)+1)+str(r))
        font.setBold(False);font.setPixelSize(11);painter.setFont(font);painter.setPen(QColor('#6479b5'));painter.drawText(rect.adjusted(12,35,-10,0),Qt.AlignmentFlag.AlignTop,' ↔ '.join(address))
        font.setPixelSize(12);painter.setFont(font);painter.setPen(QColor(w.tokens[token+'-text'] if on else w.tokens['muted']))
        if kind=='수정':
            old=' · '.join(str((s.source(i,0) or {}).get(name,'') or '(빈 값)') for name in columns)
            new=' · '.join(s.value(i,2,name) if name in s.overrides.get(tuple(row['key']),{}) else (s.candidate(i,name) or '(빈 값)') for name in columns)
            font.setStrikeOut(True);painter.setFont(font);painter.drawText(rect.adjusted(12,53,-12,0),Qt.AlignmentFlag.AlignTop,painter.fontMetrics().elidedText(old,Qt.TextElideMode.ElideRight,rect.width()-24))
            font.setStrikeOut(False);painter.setFont(font);painter.drawText(rect.adjusted(12,72,-12,0),Qt.AlignmentFlag.AlignTop,painter.fontMetrics().elidedText(new,Qt.TextElideMode.ElideRight,rect.width()-24))
        else:
            values=(s.results[i] or s.source(i,1)) if kind=='추가' else s.source(i,0);values=values or {};text=' · '.join(name+': '+str(values.get(name,'') or '') for name in s.headers)
            font.setStrikeOut(kind=='삭제');painter.setFont(font);painter.drawText(rect.adjusted(12,55,-12,0),Qt.AlignmentFlag.AlignTop,painter.fontMetrics().elidedText(text,Qt.TextElideMode.ElideRight,rect.width()-24))
    def editorEvent(self,event,model,option,index):
        from PySide6.QtCore import QEvent
        if event.type()==QEvent.Type.MouseButtonRelease and event.button()==Qt.MouseButton.LeftButton and event.position().x()<32:
            value=model.data(index,Qt.ItemDataRole.CheckStateRole)
            return model.setData(index,Qt.CheckState.Unchecked if value==Qt.CheckState.Checked else Qt.CheckState.Checked,Qt.ItemDataRole.CheckStateRole)
        return False


class ChangeView(QListView):
    toggleRequested=Signal(object)
    def __init__(self):
        super().__init__();self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel);self.smooth=SmoothScroll(self)
    def wheelEvent(self,event):self.smooth.wheel(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if event.button()==Qt.MouseButton.RightButton:
            index=self.indexAt(event.position().toPoint())
            if index.isValid():self.setCurrentIndex(index);self.toggleRequested.emit(index)
    def contextMenuEvent(self,event):event.accept()
    def mouseDoubleClickEvent(self,event):event.accept()
