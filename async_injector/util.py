from __future__ import annotations

from asyncio import gather
from collections.abc import Awaitable, Callable, Iterable
from inspect import Parameter, Signature, signature
from typing import Any, Generic, Literal, TypeVar, Union

from async_injector.errors import AnnotationMissing, SyncAsyncMismatch


_injectable_parameter_kinds = (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)


def extract_dependencies(callable_: Callable[..., Any]) -> [(str, type)]:
    return [
        (name, parameter.annotation)
        for name, parameter in signature(callable_).parameters.items()
        if parameter.kind in _injectable_parameter_kinds
        and parameter.annotation is not Signature.empty
    ]


def extract_interface(callable_: Callable[..., Any]) -> type:
    if isinstance(callable_, type):
        return callable_
    sig = signature(callable_)
    if sig.return_annotation is Signature.empty:
        raise AnnotationMissing(
            f"Callable {callable_} is missing return type annotation"
        )
    return sig.return_annotation


T = TypeVar("T")


class ProvidedValue(Generic[T]):
    __slots__ = ("type_", "value")

    def __init__(
        self,
        type_: Union[Literal["bare"], Literal["task"]],
        value: Union[T, Awaitable[T]],
    ) -> None:
        self.type_ = type_
        self.value = value

    @classmethod
    def from_bare(cls, value: T) -> ProvidedValue:
        return ProvidedValue("bare", value)

    @classmethod
    def from_task(cls, value: Awaitable[T]) -> ProvidedValue:
        return ProvidedValue("task", value)

    def get_value(self) -> T:
        if self.type_ == "bare":
            return self.value
        if self.value.done():
            return self.value.result()
        raise SyncAsyncMismatch()

    async def aget_value(self) -> T:
        if self.type_ == "bare":
            return self.value
        return await self.value

    @staticmethod
    async def aget_multiple(values: Iterable[ProvidedValue]) -> [Any]:
        tasks: [(int, Awaitable[Any])] = []
        ready: [(int, Any)] = []
        for position, value in enumerate(values):
            if value.type_ == "task":
                tasks.append((position, value.value))
            else:
                ready.append((position, value.value))
        if tasks:
            positions, awaitables = list(zip(*tasks))
            ready.extend(zip(positions, await gather(*awaitables)))
        return [value for _, value in sorted(ready)]
