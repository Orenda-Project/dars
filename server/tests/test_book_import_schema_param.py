"""core-book-import: source-schema parameter validation (ID + schema feature).

Pure-function tests for the schema-name guard used to interpolate `search_path`
safely (identifiers can't be parameterised). No DB.
"""
import pytest
from fastapi import HTTPException

from dars.v2_api import book_import_service as svc
from dars.v2_api.router_book_import import DEFAULT_CORE_SCHEMA, _validate_schema


def test_validate_schema_accepts_valid_identifiers():
    assert _validate_schema("fde_staging") == "fde_staging"
    assert _validate_schema("public") == "public"
    assert _validate_schema("My_Schema2") == "My_Schema2"
    # blank / None falls back to the default
    assert _validate_schema(None) == DEFAULT_CORE_SCHEMA
    assert _validate_schema("  fde_staging  ") == "fde_staging"


@pytest.mark.parametrize("bad", [
    "fde_staging; DROP TABLE books",  # injection attempt
    "fde-staging",                    # hyphen
    "1schema",                        # leading digit
    "fde staging",                    # space
    "schema,public",                  # comma
])
def test_validate_schema_rejects_injection_and_bad_names(bad):
    with pytest.raises(HTTPException) as ei:
        _validate_schema(bad)
    assert ei.value.status_code == 422


def test_service_schema_guard_matches_router():
    # The service's defensive guard must reject what the router rejects.
    assert svc._SCHEMA_RE.match("fde_staging")
    assert not svc._SCHEMA_RE.match("fde_staging; DROP TABLE books")
    assert not svc._SCHEMA_RE.match("1bad")
