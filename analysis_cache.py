"""Bounded session-owned analysis; never retain live mutable workbooks."""
from collections import OrderedDict
from hashlib import sha256
from compare import table
from ui_helpers import detect_layout


class AnalysisCache:
    def __init__(self, version, table_limit=4, layout_limit=8):
        self.version=version
        self.tables=OrderedDict()
        self.layouts=OrderedDict()
        self.table_limit=table_limit
        self.layout_limit=layout_limit

    @staticmethod
    def digest(data):return sha256(data).digest()

    @staticmethod
    def put(cache,key,value,limit):
        cache[key]=value;cache.move_to_end(key)
        while len(cache)>limit:cache.popitem(last=False)
        return value

    def layout(self,data):
        key=self.digest(data)
        if key in self.layouts:
            self.layouts.move_to_end(key)
            return self.layouts[key]
        return self.put(self.layouts,key,detect_layout(data),self.layout_limit)

    def read(self,data,sheet,header=1,start=2):
        key=(self.digest(data),sheet,header,start)
        if key in self.tables:
            self.tables.move_to_end(key)
            return self.tables[key]
        return self.put(self.tables,key,table(data,sheet,header,start),self.table_limit)

    def seed(self,data,dataset):
        """Reuse export metadata only for its exact bytes, sheet and range."""
        digest=self.digest(data)
        self.put(self.tables,(digest,dataset.sheet,dataset.header_row,dataset.start_row),dataset,self.table_limit)
        self.put(self.layouts,digest,{'sheet':dataset.sheet,'header':dataset.header_row,'start':dataset.start_row},self.layout_limit)
