"""API pydantic models"""

import operator
from dataclasses import dataclass
from datetime import datetime
from enum import auto
from types import DynamicClassAttribute
from typing import Any, Callable, Dict, List, Optional, Set, Union

import sqlalchemy as sa
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import shape

from geojson_pydantic.geometries import Polygon
from pydantic import Field, ValidationError, root_validator
from pydantic.error_wrappers import ErrorWrapper
from stac_api import config
from stac_api.models.decompose import CollectionGetter, ItemGetter
from stac_pydantic import Collection as CollectionBase
from stac_pydantic import Item as ItemBase
from stac_pydantic.api import Search
from stac_pydantic.api.extensions.fields import FieldsExtension as FieldsBase
from stac_pydantic.api.search import DATETIME_RFC339
from stac_pydantic.shared import Link
from stac_pydantic.utils import AutoValueEnum

# Be careful: https://github.com/samuelcolvin/pydantic/issues/1423#issuecomment-642797287
NumType = Union[float, int]


class Operator(str, AutoValueEnum):
    """
    Define our own operators because all operators defined in stac-pydantic are not currently supported.
    """

    eq = auto()
    ne = auto()
    lt = auto()
    le = auto()
    gt = auto()
    ge = auto()
    # TODO: These are defined in the spec but aren't currently implemented by the api
    # startsWith = auto()
    # endsWith = auto()
    # contains = auto()
    # in = auto()

    @DynamicClassAttribute
    def operator(self) -> Callable[[Any, Any], bool]:
        """Return python operator"""
        return getattr(operator, self._value_)


class Queryables(str, AutoValueEnum):
    """
    Define an enum of queryable fields and their data type.  Queryable fields are explicitly defined for two reasons:
        1. So the caller knows which fields they can query by
        2. Because JSONB queries with sqlalchemy ORM require casting the type of the field at runtime
            (see ``QueryableTypes``)

    # TODO: Let the user define these in a config file
    """

    gsd = auto()
    epsg = "proj:epsg"


@dataclass
class QueryableTypes:
    """
    Define an enum of the field type of each queryable field

    # TODO: Let the user define these in a config file
    # TODO: There is a much better way of defining this field <> type mapping than two enums with same keys
    """

    gsd = sa.Float
    epsg = sa.Integer


class FieldsExtension(FieldsBase):
    """Fields extension"""

    include: Optional[Set[str]] = set()
    exclude: Optional[Set[str]] = set()

    def _get_field_dict(self, fields: Set[str]) -> Dict:
        """
        Internal method to reate a dictionary for advanced include or exclude of pydantic fields on model export

        Ref: https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
        """
        field_dict = {}
        for field in fields:
            if "." in field:
                parent, key = field.split(".")
                if parent not in field_dict:
                    field_dict[parent] = {key}
                else:
                    field_dict[parent].add(key)
            else:
                field_dict[field] = ...  # type:ignore
        return field_dict

    @property
    def filter_fields(self) -> Dict:
        """
        Create dictionary of fields to include/exclude on model export based on the included and excluded fields passed
        to the API

        Ref: https://pydantic-docs.helpmanual.io/usage/exporting_models/#advanced-include-and-exclude
        """
        # Include default set of fields
        include = config.settings.default_includes
        # If only include is specified, add fields to default set
        if self.include and not self.exclude:
            include = include.union(self.include)
        # If both include + exclude specified, find the difference between sets but don't remove any default fields
        # If we remove default fields we will get a validation error
        elif self.include and self.exclude:
            include = include.union(self.include) - (
                self.exclude - config.settings.default_includes
            )
        return {
            "include": self._get_field_dict(include),
            "exclude": self._get_field_dict(self.exclude),
        }


class Collection(CollectionBase):
    """Collection model"""

    stac_extensions: Optional[List[str]]
    links: Optional[List[Link]]

    class Config:
        """model config"""

        orm_mode = True
        use_enum_values = True
        getter_dict = CollectionGetter


class Item(ItemBase):
    """Item model"""

    geometry: Polygon
    links: Optional[List[Link]]

    class Config:
        """model config"""

        json_encoders = {datetime: lambda v: v.strftime(DATETIME_RFC339)}
        use_enum_values = True
        orm_mode = True
        getter_dict = ItemGetter


class STACSearch(Search):
    """Search model"""

    # Make collections optional, default to searching all collections if none are provided
    collections: Optional[List[str]] = None
    # Override default field extension to include default fields and pydantic includes/excludes factory
    field: FieldsExtension = Field(FieldsExtension(), alias="fields")
    # Override query extension with supported operators
    query: Optional[Dict[Queryables, Dict[Operator, Any]]]
    token: Optional[str] = None

    @root_validator(pre=True)
    def validate_query_fields(cls, values: Dict) -> Dict:
        """validate query fields"""
        if "query" in values and values["query"]:
            queryable_fields = Queryables.__members__.values()
            for field_name in values["query"]:
                if field_name not in queryable_fields:
                    raise ValidationError(
                        [
                            ErrorWrapper(
                                ValueError(f"Cannot search on field: {field_name}"),
                                "STACSearch",
                            )
                        ],
                        STACSearch,
                    )
        return values

    @root_validator
    def include_query_fields(cls, values: Dict) -> Dict:
        """
        Root validator to ensure query fields are included in the API response
        """
        if "query" in values and values["query"]:
            query_include = set(
                [
                    k.value
                    if k in config.settings.indexed_fields
                    else f"properties.{k.value}"
                    for k in values["query"]
                ]
            )
            if not values["field"].include:
                values["field"].include = query_include
            else:
                values["field"].include.union(query_include)
        return values

    def polygon(self) -> Optional[ShapelyPolygon]:
        """
        Convenience method to create a shapely polygon for the spatial query (either `intersects` or `bbox`)
        """
        if self.intersects:
            return shape(self.intersects)
        elif self.bbox:
            return ShapelyPolygon.from_bounds(*self.bbox)
        else:
            return None
