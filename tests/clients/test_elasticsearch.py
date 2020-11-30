import uuid
from typing import Callable

import pytest

from stac_api.clients.postgres.core import CoreCrudClient
from stac_api.clients.postgres.transactions import TransactionsClient
from stac_api.errors import ConflictError, NotFoundError
from stac_api.models.schemas import Collection, Item
from tests.conftest import MockStarletteRequest


def test_create_item(
    postgres_core: CoreCrudClient,
    postgres_transactions: TransactionsClient,
    load_test_data: Callable,
):
    coll = Collection.parse_obj(load_test_data("test_collection.json"))
    postgres_transactions.create_collection(coll, request=MockStarletteRequest)
    item = Item.parse_obj(load_test_data("test_item.json"))
    postgres_transactions.create_item(item, request=MockStarletteRequest)
    resp = postgres_core.get_item(item.id, request=MockStarletteRequest)
    assert item.dict(
        exclude={"links": ..., "properties": {"created", "updated"}}
    ) == resp.dict(exclude={"links": ..., "properties": {"created", "updated"}})


def test_create_item_already_exists(
    postgres_core: CoreCrudClient,
    postgres_transactions: TransactionsClient,
    load_test_data: Callable,
):
    coll = Collection.parse_obj(load_test_data("test_collection.json"))
    postgres_transactions.create_collection(coll, request=MockStarletteRequest)

    item = Item.parse_obj(load_test_data("test_item.json"))
    postgres_transactions.create_item(item, request=MockStarletteRequest)

    with pytest.raises(ConflictError):
        postgres_transactions.create_item(item, request=MockStarletteRequest)


def test_update_item(
    postgres_core: CoreCrudClient,
    postgres_transactions: TransactionsClient,
    load_test_data: Callable,
):
    coll = Collection.parse_obj(load_test_data("test_collection.json"))
    postgres_transactions.create_collection(coll, request=MockStarletteRequest)

    item = Item.parse_obj(load_test_data("test_item.json"))
    postgres_transactions.create_item(item, request=MockStarletteRequest)

    item.properties.foo = "bar"
    postgres_transactions.update_item(item, request=MockStarletteRequest)

    updated_item = postgres_core.get_item(item.id, request=MockStarletteRequest)
    assert updated_item.properties.foo == "bar"


def test_delete_item(
    postgres_core: CoreCrudClient,
    postgres_transactions: TransactionsClient,
    load_test_data: Callable,
):
    coll = Collection.parse_obj(load_test_data("test_collection.json"))
    postgres_transactions.create_collection(coll, request=MockStarletteRequest)

    item = Item.parse_obj(load_test_data("test_item.json"))
    postgres_transactions.create_item(item, request=MockStarletteRequest)

    postgres_transactions.delete_item(item.id, request=MockStarletteRequest)

    with pytest.raises(NotFoundError):
        postgres_core.get_item(item.id, request=MockStarletteRequest)
