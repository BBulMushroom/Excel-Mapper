"""Insert and delete rows of one worksheet while keeping merged cells, formulas and row formats consistent.

openpyxl's insert_rows/delete_rows move cell values only: merged ranges, formula references, row heights,
validations and conditional formats stay where they were. `RowLayout` moves all of them together.

Rules (T103):
- A new row is placed right after an "anchor" row of the original sheet (0 = above the first row).
- A formula range that contains the anchor row grows to include the new row (so a subtotal `=SUM(E5:E12)`
  includes a row added after row 12); a deleted row shrinks it. A single reference to a deleted row is refused.
- A vertical merge grows over a new row placed inside it when the new row's value in that column is empty
  or equal; a different value splits the merge. Right after the last row (or before the first row) it grows
  only when the value is equal.
"""
from bisect import bisect_left, bisect_right
from copy import copy
import re

from openpyxl.utils import get_column_letter, column_index_from_string
from openpyxl.worksheet.cell_range import CellRange

# Optional sheet prefix, then A1 or A1:B2 (with $). Not preceded by letters/digits so function names stay intact.
REF = re.compile(r"(?<![A-Za-z0-9_.\"])((?:'(?:[^']|'')+'|[A-Za-z0-9_.ㄱ-힝]+)!)?(\$?)([A-Z]{1,3})(\$?)(\d+)(?::(\$?)([A-Z]{1,3})(\$?)(\d+))?(?![\d(A-Za-z_])")


def _same(a, b):
    return ('' if a is None else str(a).strip()) == ('' if b is None else str(b).strip())


class RowLayout:
    def __init__(self, ws, deleted, insertions):
        """`deleted`: original row numbers to remove. `insertions`: list of (anchor row, payload) in display order."""
        self.ws = ws
        self.deleted = sorted(set(deleted))
        self.anchors = sorted(a for a, _ in insertions)
        self.insertions = insertions
        rank = {}
        self.positions = []
        for anchor, _ in insertions:
            n = rank.get(anchor, 0); rank[anchor] = n + 1
            self.positions.append(anchor - bisect_right(self.deleted, anchor) + bisect_left(self.anchors, anchor) + 1 + n)

    # --- row arithmetic ------------------------------------------------------------------------------
    def shift(self, row):
        """New number of an original row, or None when it is deleted."""
        i = bisect_left(self.deleted, row)
        if i < len(self.deleted) and self.deleted[i] == row:
            return None
        return row - i + bisect_left(self.anchors, row)

    def span(self, first, last):
        """New (first, last) of an original row range, grown by rows inserted after a row inside it; None if all deleted."""
        rows = [self.shift(r) for r in (first, last)]
        survivors = [r for r in range(first, last + 1) if self.shift(r) is not None] if None in rows else [first, last]
        inside = [p for (a, _), p in zip(self.insertions, self.positions) if first <= a <= last]
        if not survivors and not inside:
            return None
        values = [self.shift(survivors[0]), self.shift(survivors[-1])] if survivors else []
        return min(values + inside), max(values + inside)

    # --- formulas ------------------------------------------------------------------------------------
    def rewrite(self, text, own_sheet, where):
        title = self.ws.title

        def replace(m):
            sheet = m.group(1)
            if sheet is None and not own_sheet:
                return m.group(0)
            if sheet is not None and sheet[:-1].strip("'").replace("''", "'") != title:
                return m.group(0)
            prefix = sheet or ''
            if m.group(7) is None:
                row = self.shift(int(m.group(5)))
                if row is None:
                    raise ValueError(f'{where}의 수식이 지워지는 {m.group(5)}행({m.group(3)}{m.group(5)})을 직접 가리킵니다. 그 행의 삭제 승인을 해제하거나 엑셀에서 수식을 고친 뒤 다시 저장하세요.')
                return f'{prefix}{m.group(2)}{m.group(3)}{m.group(4)}{row}'
            first, last = sorted((int(m.group(5)), int(m.group(9))))
            span = self.span(first, last)
            if span is None:
                raise ValueError(f'{where}의 수식 범위({m.group(0)})의 행이 모두 지워집니다. 삭제 승인을 해제하거나 엑셀에서 수식을 고친 뒤 다시 저장하세요.')
            return f'{prefix}{m.group(2)}{m.group(3)}{m.group(4)}{span[0]}:{m.group(6)}{m.group(7)}{m.group(8)}{span[1]}'

        return REF.sub(replace, text)

    def remap_range(self, text):
        """`A5:D12` style (space separated) ranges for validations, conditional formats and filters."""
        out = []
        for part in str(text).split():
            r = CellRange(part)
            span = self.span(r.min_row, r.max_row)
            if span:
                out.append(f'{get_column_letter(r.min_col)}{span[0]}:{get_column_letter(r.max_col)}{span[1]}')
        return ' '.join(out)

    # --- the move ------------------------------------------------------------------------------------
    def apply(self, value_of):
        """Move everything to the new layout. `value_of(payload, column)` gives a new row's value for merge decisions.

        Returns a function that re-creates the merged ranges; call it after the new rows are written."""
        ws = self.ws
        wb = ws.parent
        # Formulas everywhere that point at this sheet (other sheets only through a sheet-qualified reference).
        for sheet in wb.worksheets:
            for cell in list(sheet._cells.values()):
                if isinstance(cell.value, str) and cell.value.startswith('=') and (sheet is not ws or self.shift(cell.row) is not None):
                    cell.value = self.rewrite(cell.value, sheet is ws, f'{sheet.title}!{cell.coordinate}')
        merges = []
        for r in list(ws.merged_cells.ranges):
            top = ws.cell(r.min_row, r.min_col)
            merges.append((r.min_row, r.max_row, r.min_col, r.max_col, top.value, copy(top._style)))
            ws.unmerge_cells(str(r))
        cells = {}
        for (row, col), cell in ws._cells.items():
            new = self.shift(row)
            if new is None:
                continue
            cell.row = new
            if cell.hyperlink is not None:
                cell.hyperlink.ref = cell.coordinate
            cells[(new, col)] = cell
        ws._cells = cells
        dims = {r: (d.height, d.hidden, d.outlineLevel) for r, d in ws.row_dimensions.items()}
        ws.row_dimensions.clear()
        for row, (height, hidden, level) in dims.items():
            new = self.shift(row)
            if new is not None:
                dim = ws.row_dimensions[new]; dim.height = height; dim.hidden = hidden; dim.outlineLevel = level
        for dv in ws.data_validations.dataValidation:
            dv.sqref = self.remap_range(dv.sqref) or dv.sqref
        from openpyxl.formatting.formatting import ConditionalFormattingList
        old = ws.conditional_formatting
        ws.conditional_formatting = ConditionalFormattingList()
        for cf in old:
            target = self.remap_range(cf.sqref)
            if target:
                for rule in cf.rules:
                    ws.conditional_formatting.add(target, rule)
        if ws.auto_filter.ref:
            ws.auto_filter.ref = self.remap_range(ws.auto_filter.ref) or ws.auto_filter.ref
        for image in getattr(ws, '_images', []):
            anchor = getattr(image, 'anchor', None)
            for point in (getattr(anchor, '_from', None), getattr(anchor, 'to', None)):
                if point is not None and hasattr(point, 'row'):
                    new = self.shift(point.row + 1)
                    if new is not None:
                        point.row = new - 1

        def finish():
            for first, last, c1, c2, top_value, top_style in merges:
                survivors = [self.shift(r) for r in range(first, last + 1) if self.shift(r) is not None]
                rows = set(survivors)
                for (anchor, payload), pos in zip(self.insertions, self.positions):
                    value = value_of(payload, c1)
                    inside = first <= anchor < last
                    edge = anchor == last or anchor == first - 1
                    if inside and (value in (None, '') or _same(value, top_value)) or edge and value not in (None, '') and _same(value, top_value):
                        rows.add(pos)
                if not rows:
                    continue
                ordered = sorted(rows)
                runs, run = [], [ordered[0]]
                for row in ordered[1:]:
                    if row == run[-1] + 1:
                        run.append(row)
                    else:
                        runs.append(run); run = [row]
                runs.append(run)
                for run in runs:
                    head = ws.cell(run[0], c1)
                    if head.value in (None, '') and top_value not in (None, ''):
                        head.value = top_value; head._style = copy(top_style)
                    if len(run) > 1 or c2 > c1:
                        ws.merge_cells(start_row=run[0], start_column=c1, end_row=run[-1], end_column=c2)
        return finish
