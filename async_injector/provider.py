from abc import ABC
from asyncio import create_task
from collections.abc import Callable, Coroutine
from typing import Any

from async_injector.util import ProvidedValue, extract_dependencies, extract_interface


class Module:
    """Marker type which can be used to group providers"""


class Provider(ABC):
    dependencies: [(str, type)]
    interface: type

    @property
    def is_async(self) -> bool:
        return False

    def provide(self, **kwargs) -> ProvidedValue:
        raise NotImplementedError()


class ConstProvider(Provider):
    dependencies = []

    def __init__(self, value: Any, interface: type = ...):
        self.interface = type(value) if interface is ... else interface
        self.value = value

    def provide(self) -> ProvidedValue:
        return ProvidedValue.from_bare(self.value)


class CallableProvider(Provider):
    def __init__(self, callee: Callable, interface: type = ...):
        self.dependencies = extract_dependencies(callee)
        self.interface = extract_interface(callee) if interface is ... else interface
        self.callee = callee

    def provide(self, **kwargs) -> ProvidedValue:
        for key in kwargs:
            if isinstance(kwargs[key], ProvidedValue):
                kwargs[key] = kwargs[key].get_value()
        return ProvidedValue.from_bare(self.callee(**kwargs))


class AsyncProvider(CallableProvider):
    def __init__(
        self, callee: Callable[..., Coroutine[None, None, Any]], interface: type = ...
    ):
        super().__init__(callee, interface)

    def provide(self, **kwargs) -> ProvidedValue:
        async def run_provider():
            values = dict(
                zip(kwargs.keys(), await ProvidedValue.aget_multiple(kwargs.values()))
            )
            return await self.callee(**values)

        return ProvidedValue.from_task(create_task(run_provider()))

    @property
    def is_async(self) -> bool:
        return True
