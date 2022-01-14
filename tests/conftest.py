import os
from typing import Iterable

import pytest
from elasticsearch.exceptions import NotFoundError

# Set db to in-memory database *before* importing amcat4. Maybe not the most elegant solution...
os.environ['AMCAT4_DB_NAME'] = ":memory:"

from amcat4 import elastic, api  # noqa: E402
from amcat4.db import initialize_if_needed  # noqa: E402
from amcat4.auth import create_user, Role, User  # noqa: E402
from amcat4.index import create_index, Index  # noqa: E402

initialize_if_needed()

UNITS = [{"unit": {"text": "unit1"}},
         {"unit": {"text": "unit2"}, "gold": {"element": "au"}}]
CODEBOOK = {"foo": "bar"}
PROVENANCE = {"bar": "foo"}
RULES = {"ruleset": "crowdcoding"}


@pytest.fixture()
def user():
    u = create_user(email="testuser@example.org", password="test")
    u.plaintext_password = "test"
    yield u
    u.delete_instance()


@pytest.fixture()
def writer():
    u = create_user(email="writer@example.org", password="test", global_role=Role.WRITER)
    u.plaintext_password = "test"
    yield u
    u.delete_instance()


@pytest.fixture()
def admin():
    u = create_user(email="admin@example.org", password="secret", global_role=Role.ADMIN)
    u.plaintext_password = "secret"
    yield u
    u.delete_instance()


@pytest.fixture()
def index():
    i = create_index("amcat4_unittest_index")
    yield i
    try:
        i.delete_index()
    except NotFoundError:
        pass


@pytest.fixture()
def guest_index():
    i = create_index("amcat4_unittest_guestindex", guest_role=Role.READER)
    yield i
    try:
        i.delete_index()
    except NotFoundError:
        pass


def upload(index: Index, docs: Iterable[dict], **kwargs):
    """
    Upload these docs to the index, giving them an incremental id, and flush
    """
    for i, doc in enumerate(docs):
        defaults = {'title': "title", 'date': "2018-01-01", 'text': "text", '_id': str(i)}
        for k, v in defaults.items():
            if k not in doc:
                doc[k] = v
    ids = elastic.upload_documents(index.name, docs, **kwargs)
    elastic.refresh(index.name)
    return ids


TEST_DOCUMENTS = [
    {'cat': 'a', 'subcat': 'x', 'i': 1, 'date': '2018-01-01', 'text': 'this is a text', },
    {'cat': 'a', 'subcat': 'x', 'i': 2, 'date': '2018-02-01', 'text': 'a test text', },
    {'cat': 'a', 'subcat': 'y', 'i': 11, 'date': '2020-01-01', 'text': 'and this is another test toto', 'title': 'bla'},
    {'cat': 'b', 'subcat': 'y', 'i': 31, 'date': '2018-01-01', 'text': 'Toto je testovací článek', 'title': 'more bla'},
]


def populate_index(index):
    upload(index, TEST_DOCUMENTS, columns={'cat': 'keyword', 'subcat': 'keyword', 'i': 'int'})
    return TEST_DOCUMENTS


@pytest.fixture()
def index_docs():
    i = create_index("amcat4_unittest_indexdocs")
    populate_index(i)
    yield i
    try:
        i.delete_index()
    except NotFoundError:
        pass


def _delete_index(name):
    ix = Index.get_or_none(Index.name == name)
    if ix:
        ix.delete_index(delete_from_elastic=False)
    elastic._delete_index(name, ignore_missing=True)


@pytest.fixture()
def index_many():
    ix = create_index("amcat4_unittest_indexmany")
    upload(ix, [dict(id=i, pagenr=abs(10-i), text=text) for (i, text) in enumerate(["odd", "even"]*10)])
    yield ix
    _delete_index(ix.name)


@pytest.fixture()
def index_name():
    """A name to create an index which will be deleted afterwards if needed"""
    name = "amcat4_unittest_index_name"
    _delete_index(name)
    yield name
    _delete_index(name)


@pytest.fixture()
def username():
    """A name to create a user which will be deleted afterwards if needed"""
    name = "test_user@example.com"
    yield name
    u = User.get_or_none(User.email == name)
    if u:
        u.delete_instance()


@pytest.fixture()
def app():
    return api.app
