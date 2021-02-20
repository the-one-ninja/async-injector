class InjectionError(Exception):
    """Base for injection exceptions"""


class AnnotationMissing(InjectionError):
    """Cannot infer interface for provider, type annotation missing"""


class CircularDependency(InjectionError):
    """There is a cycle in providers' dependency graph"""


class ProviderMissing(InjectionError):
    """No provider found for an interface"""


class SyncAsyncMismatch(InjectionError):
    """Async provider called during sync injection"""
