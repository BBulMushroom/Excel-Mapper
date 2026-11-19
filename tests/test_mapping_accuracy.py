"""Automatic column links must be right or absent: a wrong link is worse than a missing one."""
from io import BytesIO
import openpyxl
from compare import table
from ui_helpers import suggested_mapping,header_key


def load(headers,rows):
    wb=openpyxl.Workbook();ws=wb.active;ws.title='자료';ws.append(headers)
    for row in rows:ws.append(row)
    out=BytesIO();wb.save(out);return table(out.getvalue(),'자료')


def test_titles_equal_after_width_case_and_space_normalisation_are_linked():
    left=load(['코드','품목 이름','Ｑｔｙ'],[['A1','x',1],['A2','y',2]])
    right=load(['코드 ','품목이름','qty'],[['A1','x',1],['A2','y',2]])
    assert suggested_mapping(left,right)=={'코드':'코드','품목 이름':'품목이름','Ｑｔｙ':'qty'}
    assert header_key('  Ｑｔｙ:')==header_key('QTY')=='qty'


def test_ambiguous_titles_are_not_linked_by_name():
    left=load(['코드','메모'],[['A1','a'],['A2','b']])
    right=load(['코드','메 모','메모 '],[['A1','a','b'],['A2','b','a']])
    mapping=suggested_mapping(left,right)
    assert mapping=={'코드':'코드'}                 # two right columns look like "메모": leave it to the user


def test_unmistakable_value_match_is_linked_even_with_different_titles():
    ids=[f'ID{n:03d}' for n in range(40)]
    left=load(['자산번호','이름'],[[i,f'n{n}'] for n,i in enumerate(ids)])
    right=load(['관리코드','품명'],[[i,f'm{n}'] for n,i in enumerate(ids)])
    assert suggested_mapping(left,right)=={'자산번호':'관리코드'}   # the names columns share no values: not linked


def test_weak_or_competing_matches_are_left_unlinked():
    base=[f'V{n:03d}' for n in range(40)]
    left=load(['값'],[[v] for v in base])
    partial=load(['다른열'],[[v] for v in base[:20]]+[[f'X{n}'] for n in range(20)])        # only half shared
    assert suggested_mapping(left,partial)=={}
    twins=load(['가','나'],[[v,v] for v in base])                                            # two equally good targets
    assert suggested_mapping(left,twins)=={}


def test_sequence_columns_are_never_linked():
    left=load(['순번','코드'],[[1,'A'],[2,'B']]);right=load(['순번','코드'],[[1,'A'],[2,'B']])
    assert suggested_mapping(left,right)=={'코드':'코드'}


def test_boolean_like_columns_are_not_linked_by_values_alone():
    left=load(['사용'],[['Y'],['N']]*20);right=load(['여부'],[['Y'],['N']]*20)
    assert suggested_mapping(left,right)=={}
