import typing

import pydantic
import pytest

from socketsundso.handler import Handler


@pytest.fixture
def simple_async_handler():
    async def return_foo():
        return "foo"

    return Handler("return_foo", return_foo)


@pytest.fixture
def return_arg_async_handler():
    async def return_arg(arg: typing.Any):
        return arg

    return Handler("return_arg", return_arg)


def test_handler_init_attrs(simple_async_handler):
    assert simple_async_handler.event == "return_foo"
    assert simple_async_handler.bound_method == None

    assert isinstance(simple_async_handler.model, pydantic.main.ModelMetaclass)
    assert isinstance(simple_async_handler.response_model, pydantic.main.ModelMetaclass)
    assert isinstance(simple_async_handler.response_field, pydantic.fields.ModelField)


async def test_handler_async_call(simple_async_handler):
    assert await simple_async_handler() == "foo"


@pytest.mark.skip(reason="not implemented yet")
def test_handler_call(simple_handler):
    assert simple_handler() == "foo"


async def test_handler_async_call_with_arg(return_arg_async_handler):
    assert await return_arg_async_handler("foo") == "foo"
    assert await return_arg_async_handler(None) == None
    assert await return_arg_async_handler(42) == 42


@pytest.mark.skip(reason="test not implemented yet")
async def test_handler_handle(simple_handler):
    pass


@pytest.mark.skip(reason="test not implemented yet")
async def test_handler_handle_invalid_data(simple_handler):
    pass
