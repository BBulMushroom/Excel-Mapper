"""Copy actual Excel formulas and basic cell formatting between workbooks."""
from copy import copy
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re
import openpyxl
from openpyxl.formula import Tokenizer
from openpyxl.formula.translate import Translator
from openpyxl.utils import quote_sheetname

# Excel A1 references, including whole-row/whole-column ranges.
A1 = re.compile(r'^(?:\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?|\$?[A-Z]{1,3}:\$?[A-Z]{1,3}|\$?\d+:\$?\d+)$', re.I)


def copy_format(source, target):
    # Style IDs belong to a workbook, so copying _style across workbooks is invalid.
    for attr in ('font', 'fill', 'border', 'alignment', 'protection'):
        setattr(target, attr, copy(getattr(source, attr)))
    target.number_format = source.number_format
    target.comment = copy(source.comment)
    if source.hyperlink:
        target.hyperlink = copy(source.hyperlink)
        target.hyperlink.ref = target.coordinate
    else:
        target.hyperlink = None


class ExcelCopy:
    def __init__(self, destination, comparison_data, sheet, mode='일반 복사'):
        if mode not in ('일반 복사', '값만 복사'):
            raise ValueError('복사 방식을 확인하세요.')
        self.destination, self.data, self.sheet, self.mode = destination, comparison_data, sheet, mode
        self.source = self.cached = None
        self.empty_cache = None
        self.references = {}
        self.imported = set()
        self.styles = {}

    def copy_format(self,source,target):
        # Source style IDs are workbook-local. Resolve them in this destination
        # once, then clone only that destination-owned StyleArray for each cell.
        key=source.style_id
        if key not in self.styles:
            copy_format(source,target)
            self.styles[key]=copy(target._style)
        else:
            target._style=copy(self.styles[key])
            target.comment=copy(source.comment)
            target.hyperlink=copy(source.hyperlink) if source.hyperlink else None
            if target.hyperlink:target.hyperlink.ref=target.coordinate

    def close(self):
        for wb in (self.source, self.cached):
            if wb is not None:
                wb.close()

    def source_cell(self, row, column):
        if self.data is None:
            return None
        if self.source is None:
            self.source = openpyxl.load_workbook(BytesIO(self.data))
        return self.source[self.sheet].cell(row, column)

    def has_empty_string_cache(self, coordinate):
        if self.empty_cache is None:
            self.empty_cache = set()
            # An explicit string result may legitimately be empty; numeric <v/>
            # written by openpyxl means no cached result and must still fail.
            with ZipFile(BytesIO(self.data)) as archive:
                workbook = ET.fromstring(archive.read('xl/workbook.xml'))
                sheets = workbook.find('{*}sheets')
                sheet = next(s for s in sheets if s.attrib['name'] == self.sheet)
                rel_id = next(v for k, v in sheet.attrib.items() if k.endswith('}id'))
                rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
                target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rel_id)
                path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
                root = ET.fromstring(archive.read(path))
                for cell in root.findall('.//{*}c'):
                    value = cell.find('{*}v')
                    if cell.attrib.get('t') == 'str' and cell.find('{*}f') is not None and value is not None and not value.text:
                        self.empty_cache.add(cell.attrib['r'])
        return coordinate in self.empty_cache

    def rewrite_references(self, formula):
        try:
            tokens = Tokenizer(formula).items
        except Exception as exc:
            raise ValueError('수식을 해석할 수 없습니다. 해당 변경을 제외하거나 값만 복사를 사용하세요.') from exc
        for token in tokens:
            if token.type != 'OPERAND' or token.subtype != 'RANGE':
                continue
            value = token.value
            if '!' in value:
                name, ref = value.rsplit('!', 1)
                name = name[1:-1].replace("''", "'") if name.startswith("'") and name.endswith("'") else name
                if '[' in name or ':' in name or not A1.fullmatch(ref):
                    raise ValueError('외부 파일·3차원 참조·이름 정의 수식은 일반 복사를 지원하지 않습니다. 값만 복사를 사용하세요.')
                target = self.import_sheet(name)
                token.value = quote_sheetname(target) + '!' + ref
            elif not A1.fullmatch(value):
                raise ValueError(f'이름 정의·표 참조 수식({value})은 일반 복사를 지원하지 않습니다. 값만 복사를 사용하세요.')
        return '=' + ''.join(t.value for t in tokens)

    def import_sheet(self, name):
        if name in self.references:
            return self.references[name]
        if name not in self.source.sheetnames:
            raise ValueError(f'비교파일에 참조 시트 “{name}”이 없습니다.')
        # Always use a separate comparison snapshot, even if names match.
        base = (name[:26] + ' (비교)')[:31]
        title, number = base, 2
        while title in self.destination.sheetnames:
            suffix = f' ({number})'
            title = base[:31-len(suffix)] + suffix
            number += 1
        target = self.destination.create_sheet(title)
        self.references[name] = target.title  # Register before resolving cyclic dependencies.
        source = self.source[name]
        for cell in source._cells.values():
            dest = target.cell(cell.row, cell.column)
            if cell.data_type == 'f':
                if not isinstance(cell.value, str):
                    raise ValueError('배열 수식은 일반 복사를 지원하지 않습니다. 값만 복사를 사용하세요.')
                dest.value = self.rewrite_references(cell.value)
            else:
                dest.value, dest.data_type = cell.value, cell.data_type
            if cell.has_style or cell.comment or cell.hyperlink:
                self.copy_format(cell, dest)
        for key, dim in source.row_dimensions.items():
            target.row_dimensions[key].height = dim.height
            target.row_dimensions[key].hidden = dim.hidden
        for key, dim in source.column_dimensions.items():
            target.column_dimensions[key].width = dim.width
            target.column_dimensions[key].hidden = dim.hidden
        for merged in source.merged_cells.ranges:
            target.merge_cells(str(merged))
        target.freeze_panes = source.freeze_panes
        target.sheet_view.showGridLines = source.sheet_view.showGridLines
        self.imported.add(target.title)
        return target.title

    def calculated_value(self, row, column):
        if self.cached is None:
            self.cached = openpyxl.load_workbook(BytesIO(self.data), data_only=True)
        cell = self.cached[self.sheet].cell(row, column)
        if cell.value is None and self.has_empty_string_cache(cell.coordinate):
            return True, '', 's'
        return cell.value is not None, cell.value, cell.data_type

    def write(self, target, row, column, fallback):
        source = self.source_cell(row, column)
        # Without provenance, a string beginning '=' remains literal text.
        if source is None:
            target.value = fallback
            if isinstance(fallback, str):
                target.data_type = 's'
            return
        if source.data_type == 'f':
            if self.mode == '값만 복사':
                exists, value, data_type = self.calculated_value(row, column)
                if not exists:
                    raise ValueError(f'비교 {self.sheet}!{source.coordinate}: 저장된 수식 계산값이 없습니다. Excel에서 계산 후 저장하거나 일반 복사를 선택하세요.')
                target.value, target.data_type = value, data_type
            else:
                if not isinstance(source.value, str):
                    raise ValueError(f'비교 {source.coordinate}: 배열 수식은 일반 복사를 지원하지 않습니다.')
                try:
                    formula = Translator(source.value, origin=source.coordinate).translate_formula(target.coordinate)
                    target.value = self.rewrite_references(formula)
                except ValueError:
                    raise
                except Exception as exc:
                    raise ValueError(f'비교 {source.coordinate}: 이동 위치에 맞춰 수식을 조정할 수 없습니다. 해당 변경을 제외하세요.') from exc
        else:
            target.value, target.data_type = source.value, source.data_type
        if self.mode == '일반 복사':
            self.copy_format(source, target)
