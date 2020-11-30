from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from pystac.validation import STACValidationError

from ..models import User, StacRequest,  ValidateItem, BatchAddItem
from ..auth import decode_jwt, get_key_dict
from ..core.stac import (
    get_item,
    add_item_to_search,
    get_document_from_search,
    validate_stac_item
)


router = APIRouter()


@router.post("/stac")
async def add_stac_item(
        body: StacRequest,
        authorization: str = Header(None),
        current_user: User = Depends(get_current_active_user)
):
    """
    Add STAC item to Elasticsearch index
    Given a url to a STAC item, read the item and add to Elasticsearch index.
    """
    if not body.item:
        url = body.url

        item = get_item(url)
    else:
        item = body.item
    try:
        validate_stac_item(body.dict())
        result = add_item_to_search(item)
    except STACValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="STAC Item Failed Validation",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return result


@router.get("/item/{id}")
async def get_stac_item(
    id: str
):
    """
    Get STAC item from Elasticsearch index
    Given an Elasticsearch ID, get the STAC item document from Elasticsearch.
    For an example, try: `LDZMkHMB4H42utSA7GSG`
    """
    result = get_document_from_search(id)

    return result


@router.post("/validate")
async def validate_item(
    body: ValidateItem
):
    """
    Validate Stac json using pystac item valdiation
    """
    result = validate_stac_item(body.dict())
    return result


@router.post("bulk_add")
async def add_batch_items(
        body: BatchAddItem,
):
    """
    Add Batch of STAC item to Elasticsearch index
    Given a url to a STAC item, read the item and add to Elasticsearch index.
    """
    for item in body.items:
        await add_stac_item(item)
