"""Type de colonne géométrie.

PostgreSQL avec PostGIS (NV_USE_POSTGIS=true, défaut) : colonne PostGIS (SRID 4326, index GiST).
Autres cas (SQLite des tests, PostgreSQL sans PostGIS avec NV_USE_POSTGIS=false) : GeoJSON stocké en texte.
La valeur Python est toujours un dict GeoJSON.
"""
import json

from geoalchemy2 import Geometry
from shapely import wkb
from shapely.geometry import mapping, shape
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import get_settings


def _postgis(dialect) -> bool:
    return dialect is not None and dialect.name == "postgresql" and get_settings().use_postgis


class GeoJSONGeometry(TypeDecorator):
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if _postgis(dialect):
            return dialect.type_descriptor(Geometry("GEOMETRY", srid=4326, spatial_index=True))
        return Text() if dialect is None else dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if _postgis(dialect):
            return "SRID=4326;" + shape(value).wkt
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if _postgis(dialect):
            data = value.data if hasattr(value, "data") else value
            return mapping(wkb.loads(bytes(data)))
        return json.loads(value)
