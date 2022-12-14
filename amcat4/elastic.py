import hashlib
import json
import logging
from typing import Mapping, List, Optional, Iterable, Tuple, Union, Sequence, Dict, Literal

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from amcat4.config import settings

_ES: Optional[Elasticsearch] = None
SYS_INDEX = "amcat4system"
SYS_MAPPING = "sys"
REQUIRED_FIELDS = ["title", "date", "text"]
HASH_FIELDS = REQUIRED_FIELDS + ["url"]
DEFAULT_QUERY_FIELDS = HASH_FIELDS

ES_MAPPINGS = {
   'long': {"type": "long"},
   'date': {"type": "date", "format": "strict_date_optional_time"},
   'double': {"type": "double"},
   'keyword': {"type": "keyword"},
   'url': {"type": "keyword", "meta": {"amcat4_type": "url"}},
   'tag': {"type": "keyword", "meta": {"amcat4_type": "tag"}},
   'id': {"type": "keyword", "meta": {"amcat4_type": "id"}},
   'text': {"type": "text"},
   'object': {"type": "object"},
   'geo_point': {"type": "geo_point"}
   }


def es() -> Elasticsearch:
    if _ES is None:
        raise Exception("Elasticsearch not setup yet")
    return _ES


def setup_elastic(*hosts):
    """
    Check whether we can connect with elastic
    """
    if not hosts:
        hosts = settings.amcat4_elastic_host
    global _ES
    if _ES is None:
        logging.debug("Connecting with elasticsearch at {}".format(hosts or "(default: localhost:9200)"))
        _ES = Elasticsearch(hosts or None)
    else:
        logging.debug("Elasticsearch already configured")
    if not _ES.ping():
        raise Exception(f"Cannot connect to elasticsearch server {hosts}")
    if not _ES.indices.exists(index=SYS_INDEX):
        logging.info(f"Creating amcat4 system index: {SYS_INDEX}")
        _ES.indices.create(index=SYS_INDEX)


def _list_indices(exclude_system_index=True) -> List[str]:
    """
    List all indices on the connected elastic cluster.
    You should probably use the methods in amcat4.index rather than this.
    """
    result = es().indices.get(index="*")
    return [x for x in result.keys() if not (exclude_system_index and x == SYS_INDEX)]


def _create_index(name: str) -> None:
    """
    Create a new index
    You should probably use the methods in amcat4.index rather than this.
    """
    fields = {'text': ES_MAPPINGS['text'],
              'title': ES_MAPPINGS['text'],
              'date': ES_MAPPINGS['date'],
              'url': ES_MAPPINGS['url']}
    es().indices.create(index=name, mappings={'properties': fields})


def _delete_index(name: str, ignore_missing=False) -> None:
    """
    Delete an index
    You should probably use the methods in amcat4.index rather than this.
    :param name: The name of the new index (without prefix)
    :param ignore_missing: If True, do not throw exception if index does not exist
    """
    es().indices.delete(index=name, ignore=([404] if ignore_missing else []))


def _get_hash(document):
    """
    Get the hash for a document
    """
    hash_dict = {key: document.get(key) for key in HASH_FIELDS}
    hash_str = json.dumps(hash_dict, sort_keys=True, ensure_ascii=True).encode('ascii')
    m = hashlib.sha224()
    m.update(hash_str)
    return m.hexdigest()


def check_elastic_type(value, ftype):
    """
    coerces values into the respective type in elastic
    based on ES_MAPPINGS and elastic field types
    """
    if ftype in ["keyword",
                 "constant_keyword",
                 "wildcard",
                 "url",
                 "tag",
                 "text"]:
        value = str(value)
    elif ftype in ["long",
                   "short",
                   "byte",
                   "double",
                   "float",
                   "half_float",
                   "half_float",
                   "unsigned_long"]:
        value = float(value)
    elif ftype in ["integer"]:
        value = int(value)
    elif ftype == "boolean":
        value = bool(value)
    return value


def _get_es_actions(index, documents):
    """
    Create the Elasticsearch bulk actions from article dicts.
    It also tries to coerce types using the first entry of the index as reference
    If you provide a list to ID_SEQ_LIST, the hashes are copied there
    """
    field_types = get_index_fields(index)
    for document in documents:
        for key in document.keys():
            if key in field_types:
                document[key] = check_elastic_type(document[key], field_types[key].get("type"))
        for f in REQUIRED_FIELDS:
            if f not in document:
                raise ValueError("Field {f!r} not present in document {document}".format(**locals()))
        if '_id' not in document:
            document['_id'] = _get_hash(document)
        yield {
            "_index": index,
            **document
        }


def upload_documents(index: str, documents, columns: Mapping[str, str] = None) -> List[str]:
    """
    Upload documents to this index

    :param index: The name of the index (without prefix)
    :param documents: A sequence of article dictionaries
    :param columns: A mapping of field:type for column types
    :return: the list of document ids
    """
    if columns:
        set_columns(index, columns)

    actions = list(_get_es_actions(index, documents))
    bulk(es(), actions)
    invalidate_field_cache(index)
    return [action['_id'] for action in actions]


def get_mapping(type_: Union[str, dict]):
    if isinstance(type_, str):
        return ES_MAPPINGS[type_]
    else:
        mapping = ES_MAPPINGS[type_['type']]
        meta = mapping.get('meta', {})
        if m := type_.get('meta'):
            meta.update(m)
        mapping['meta'] = meta
        return mapping


def set_columns(index: str, columns: Mapping[str, str]):
    """
    Update the column types for this index

    :param index: The name of the index (without prefix)
    :param columns: A mapping of field:type for column types
    """
    mapping = {field: get_mapping(type_) for (field, type_) in columns.items()}
    es().indices.put_mapping(index=index, body=dict(properties=mapping))
    invalidate_field_cache(index)


def get_document(index: str, doc_id: str, **kargs) -> dict:
    """
    Get a single document from this index.

    :param index: The name of the index
    :param doc_id: The document id (hash)
    :return: the source dict of the document
    """
    return es().get(index=index, id=doc_id, **kargs)['_source']


def update_document(index: str, doc_id: str, fields: dict):
    """
    Update a single document.

    :param index: The name of the index
    :param doc_id: The document id (hash)
    :param fields: a {field: value} mapping of fields to update
    """
    # Mypy doesn't understand that body= has been deprecated already...
    es().update(index=index, id=doc_id, doc=fields)  # type: ignore
    invalidate_field_cache(index)


def delete_document(index: str, doc_id: str):
    """
    Delete a single document

    :param index: The name of the index
    :param doc_id: The document id (hash)
    """
    es().delete(index=index, id=doc_id)


def _get_type_from_property(properties: dict) -> str:
    """
    Convert an elastic 'property' into an amcat4 field type
    """
    result = properties.get("meta", {}).get("amcat4_type")
    if result:
        return result
    return properties['type']


def _get_fields(index: str) -> Iterable[Tuple[str, dict]]:
    r = es().indices.get_mapping(index=index)
    for k, v in r[index]['mappings']['properties'].items():
        t = dict(name=k, type=_get_type_from_property(v))
        if meta := v.get('meta'):
            t['meta'] = meta
        yield k, t


FIELD_CACHE: Dict[str, Mapping[str, dict]] = {}


def invalidate_field_cache(index):
    if index in FIELD_CACHE:
        del FIELD_CACHE[index]


def get_index_fields(index: str) -> Mapping[str, dict]:
    """
    Get the field types in use in this index
    :param index:
    :param invalidate_cache: Force re-getting the field types from elastic
    :return: a dict of fieldname: field objects {fieldname: {name, type, meta, ...}]
    """
    # TODO Is this thread safe? I think worst case is two threads overwrite the cache, but should be the same data?
    if result := FIELD_CACHE.get(index):
        return result
    else:
        result = dict(_get_fields(index))
        FIELD_CACHE[index] = result
        return result


def get_fields(index: Union[str, Sequence[str]]):
    """
    Get the field types in use in this index or indices
    :param index: name(s) of index(es) to query
    :param invalidate_cache: Force re-getting the field types from elastic
    :return: a dict of fieldname: field objects {fieldname: {name, type, ...}]
    """
    if isinstance(index, str):
        return get_index_fields(index)
    result = {}
    for ix in index:
        for f, ftype in get_index_fields(ix).items():
            if f in result:
                if result[f] != ftype:
                    result[f] = {"name": f, "type": "keyword", "meta": {"merged": True}}
            else:
                result[f] = ftype
    return result


def field_type(index: Union[str, Sequence[str]], field_name: str) -> str:
    """
    Get the field type for the given field.
    :return: a type name ('text', 'date', ..)
    """
    return get_fields(index)[field_name]["type"]


def get_values(index: str, field: str) -> List[str]:
    """
    Get the values for a given field (e.g. to populate list of filter values on keyword field)
    :param index: The index
    :param field: The field name
    :return: A list of values
    """
    aggs = {"values": {"terms": {"field": field}}}
    r = es().search(index=index, size=0, aggs=aggs)
    return [x["key"] for x in r["aggregations"]["values"]["buckets"]]


def refresh(index: str):
    es().indices.refresh(index=index)


def index_exists(name: str) -> bool:
    """
    Check if an index with this name exists
    """
    return es().indices.exists(index=name)


def update_by_query(index: str, script: str, query: dict, params: dict = None):
    body = dict(
        **query,
        script=dict(
            source=script,
            lang="painless",
            params=params or {}
        )
    )
    es().update_by_query(index=index, body=body)


TAG_SCRIPTS = dict(
    add="""
    if (ctx._source[params.field] == null) {
      ctx._source[params.field] = [params.tag]
    } else if (!ctx._source[params.field].contains(params.tag)) {
      ctx._source[params.field].add(params.tag)
    }
    """,
    remove="""
    if (ctx._source[params.field] != null && ctx._source[params.field].contains(params.tag)) {
      ctx._source[params.field].removeAll([params.tag])
    }""")


def update_tag_by_query(index: str, action: Literal["add", "remove"], query: dict, field: str, tag: str):
    script = TAG_SCRIPTS[action]
    params = dict(field=field, tag=tag)
    update_by_query(index, script, query, params)
