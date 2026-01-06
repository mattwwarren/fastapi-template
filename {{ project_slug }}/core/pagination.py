"""Pagination configuration and dependency helpers."""

import importlib
from typing import Annotated

from fastapi import Depends
from fastapi_pagination import Page, Params, set_page
from pydantic import Field

from {{ project_slug }}.core.config import settings


class DefaultParams(Params):
    page: int = Field(default=1, ge=1)
    size: int = Field(
        default=settings.pagination_page_size,
        ge=1,
        le=settings.pagination_page_size_max,
    )


ParamsDep = Annotated[DefaultParams, Depends()]


def configure_pagination() -> None:
    if not settings.pagination_page_class:
        return
    module_path, _, attr = settings.pagination_page_class.rpartition(".")
    if not module_path:
        raise ValueError("pagination_page_class must be an importable path")
    module = importlib.import_module(module_path)
    page_cls = getattr(module, attr)
    if not isinstance(page_cls, type) or not issubclass(page_cls, Page):
        raise TypeError("pagination_page_class must be a fastapi-pagination Page")
    set_page(page_cls)
