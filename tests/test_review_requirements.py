from compare import Table
from ui_helpers import key_metrics


def test_key_percentages_distinguish_uniqueness_from_overlap():
    a=Table('a',1,2,['code'],[{'code':'a'},{'code':'b'}],[2,3])
    b=Table('b',1,2,['code'],[{'code':'c'},{'code':'d'}],[2,3])
    assert key_metrics(a,b,{'code':'code'})['code']=={'unique':100,'match':0}
    b.rows=[{'code':'a'},{'code':'a'}]
    assert key_metrics(a,b,{'code':'code'})['code']=={'unique':50,'match':100}
