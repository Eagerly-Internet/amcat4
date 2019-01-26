"""
All things query
"""
from math import ceil
from typing import Mapping

from .elastic import DOCTYPE, es


class QueryResult:
    def __init__(self, data, n=None, per_page=None, page=None, page_count=None, scroll_id=None):
        if n and page_count is None:
            page_count = ceil(n / per_page)
        self.data = data
        self.total_count = n
        self.page = page
        self.page_count = page_count
        self.per_page = per_page
        self.scroll_id = scroll_id

    def as_dict(self):
        if self.scroll_id:
            meta = dict(scroll_id=self.scroll_id)
        else:
            meta = dict(total_count=self.total_count, per_page=self.per_page, page_count=self.page_count,
                        page=self.page)
        return dict(meta=meta, results=self.data)


def query_documents(index: str, query_string: str=None, page:int=0, per_page:int=10,
                    scroll=None, scroll_id:str=None,
                    filters: Mapping[str, Mapping]=None, **kwargs) -> QueryResult:
    """
    Conduct a query_string query, returning the found documents

    It will return at most per_page results.
    In normal (paginated) mode, the next batch can be  requested by incrementing the page parameter.
    If the scroll parameter is given, the result will contain a scroll_id which can be used to get the next batch.
    In case there are no more documents to scroll, it will return None

    :param index: The name of the index
    :param query_string: The elasticsearch query_string
    :param page: The number of the page to request (starting from zero)
    :param per_page: The number of hits per page
    :param scroll: if not None, will create a scroll request rather than a paginated request. Parmeter should
                   specify the time the context should be kept alive, or True to get the default of 2m.
    :param scroll_id: if not None, should be a previously returned context_id to retrieve a new page of results
    :param filters: if not None, a dict of filters: {field: {'value': value}} or
                    {field: {'range': {'gte/gt/lte/lt': value, 'gte/gt/..': value, ..}}
    :param kwargs: Additional elements passed to Elasticsearch.search(), for example:
           sort=col1:desc,col2

    :return: an iterator of article dicts
    """
    if scroll or scroll_id:
        # set scroll to default also if scroll_id is given but no scroll time is known
        kwargs['scroll'] = '2m' if (not scroll or scroll is True) else scroll

    if scroll_id:
        result = es.scroll(scroll_id, **kwargs)
        if not result['hits']['hits']:
            return None
    else:
        if query_string:
            body = dict(query_string=dict(query=query_string))
        else:
            body = dict(match_all={})
        if filters:
            def parse_filter(field, filter):
                if 'value' in filter:
                    return {"term": {field: filter['value']}}
                elif 'range' in filter:
                    return {"range": {field: filter['range']}}

            fterms = [parse_filter(*item) for item in filters.items()]
            body = {"bool": {"must": body,
                             "filter": fterms}}

        if not scroll:
            kwargs['from_'] = page * per_page
        result = es.search(index, DOCTYPE, {'query': body}, size=per_page, **kwargs)

    data = [dict(_id=hit['_id'], **hit['_source']) for hit in result['hits']['hits']]
    if scroll_id:
        return QueryResult(data, scroll_id=scroll_id)
    elif scroll:
        return QueryResult(data, n=result['hits']['total'], per_page=per_page, scroll_id=result['_scroll_id'])
    else:
        return QueryResult(data, n=result['hits']['total'], per_page=per_page,  page=page)
