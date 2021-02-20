from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterable
from inspect import iscoroutinefunction
from typing import Any, TypeVar

from async_injector.errors import CircularDependency, ProviderMissing, SyncAsyncMismatch
from async_injector.provider import (
    AsyncProvider,
    CallableProvider,
    ConstProvider,
    Module,
    Provider,
)
from async_injector.util import ProvidedValue, extract_dependencies


R = TypeVar("R")


class Injector:
    def __init__(self, *providers_and_modules: [Any]):
        self.providers: ProviderDict = _make_provider_dict(providers_and_modules)
        self.resolver = Resolver()

    def call(self, f: Callable[..., R], **kwargs) -> R:
        injected = {
            name: self.get(iface)
            for name, iface in extract_dependencies(f)
            if name not in kwargs
        }
        return f(**kwargs, **injected)

    async def acall(self, f: Callable[..., Coroutine[None, None, R]], **kwargs) -> R:
        names, interfaces = list(
            zip(*[
                (name, iface)
                for name, iface in extract_dependencies(f)
                if name not in kwargs
            ])
        )
        for iface in interfaces:
            await self._awalk_dependencies(iface)
        raw_values = (self.resolver.get_provided(iface) for iface in interfaces)
        injected = dict(zip(names, await ProvidedValue.aget_multiple(raw_values)))
        return await f(**kwargs, **injected)

    def get(self, interface: type):
        self._walk_dependencies(interface)
        return self.resolver.get_provided(interface).get_value()

    async def aget(self, interface: type):
        await self._awalk_dependencies(interface)
        return await self.resolver.get_provided(interface).aget_value()

    def _walk_dependencies(self, interface: type):
        if self.resolver.is_resolved(interface):
            return
        stack = ResolutionStack([interface])
        while stack:
            provider = self.providers[stack.top]
            if self.resolver.has_unresolved_deps(provider):
                next_dep = self.resolver.first_unresolved_dep(provider)
                stack.append(next_dep)
            else:
                self.resolver.provide(provider)
                stack.pop()

    async def _awalk_dependencies(self, interface: type):
        if self.resolver.is_resolved(interface):
            return
        stack = ResolutionStack([interface])
        while stack:
            provider = self.providers[stack.top]
            if self.resolver.has_unresolved_deps(provider):
                next_dep = self.resolver.first_unresolved_dep(provider)
                stack.append(next_dep)
            else:
                await self.resolver.aprovide(provider)
                stack.pop()


class ResolutionStack(list[type]):
    def append(self, interface: type) -> None:
        if interface in self:
            raise CircularDependency(interface)

        super().append(interface)

    @property
    def top(self) -> type:
        return self[-1]


class ProviderDict(dict[type, Provider]):
    def __getitem__(self, iface: type):
        provider = super().get(iface)
        if provider is None:
            raise ProviderMissing(iface)
        return provider


class Resolver:
    def __init__(self):
        self.resolved: dict[type, ProvidedValue] = {}

    def has_unresolved_deps(self, provider: Provider) -> bool:
        return any(dep not in self.resolved for _, dep in provider.dependencies)

    def provide(self, provider: Provider) -> None:
        values = {name: self.resolved[dep] for name, dep in provider.dependencies}
        if provider.is_async:
            raise SyncAsyncMismatch(provider.interface)
        self.resolved[provider.interface] = provider.provide(**values)

    async def aprovide(self, provider: Provider) -> None:
        values = {name: self.resolved[dep] for name, dep in provider.dependencies}
        if not provider.is_async:
            values = dict(
                zip(values.keys(), await ProvidedValue.aget_multiple(values.values()))
            )
        self.resolved[provider.interface] = provider.provide(**values)

    def first_unresolved_dep(self, provider: Provider) -> type:
        return next(dep for _, dep in provider.dependencies if dep not in self.resolved)

    def get_provided(self, interface: type) -> ProvidedValue:
        return self.resolved[interface]

    def is_resolved(self, interface: type) -> bool:
        return interface in self.resolved


def _make_provider(obj: Any) -> Provider:
    if isinstance(obj, Provider):
        return obj
    if callable(obj):
        if iscoroutinefunction(obj):
            return AsyncProvider(obj)
        return CallableProvider(obj)
    return ConstProvider(obj)


def _make_providers(obj: Any) -> Iterable[Provider]:
    if isinstance(obj, type) and issubclass(obj, Module):
        for member in dir(obj):
            if not member.startswith("_"):
                yield from _make_providers(getattr(obj, member))
    else:
        yield _make_provider(obj)


def _make_provider_dict(providers_and_modules: Iterable) -> ProviderDict:
    return ProviderDict(
        (provider.interface, provider)
        for obj in providers_and_modules
        for provider in _make_providers(obj)
    )
