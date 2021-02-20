from asyncio import sleep

from pytest import raises, mark

from async_injector import Injector, Module, CircularDependency, ProviderMissing


def test_call():
    class A:
        pass

    def func(a: A):
        return a

    instance = Injector(A).call(func)
    assert isinstance(instance, A)


def test_only_one_dependency_instance_across_graph():
    class A:
        pass

    class B:
        def __init__(self, a: A):
            self.a = a

    class C:
        def __init__(self, b: B, a: A):
            self.a = a
            self.b = b

    def func(a: A, c: C, b: B):
        return a, b, c

    a, b, c = Injector(A, B, C).call(func)
    assert a is b.a
    assert a is c.a
    assert b is c.b


def test_only_one_dependency_instance_across_calls():
    class A:
        pass

    class B:
        def __init__(self, a: A):
            self.a = a

    def func(b: B) -> A:
        return b.a

    injector = Injector(A, B)
    a1 = injector.call(func)
    a2 = injector.call(func)
    a3 = injector.call(func)
    assert a1 is a2
    assert a2 is a3


def test_modules_work():
    class Answer:
        def __init__(self, value: int):
            self.value = value

    class Question:
        def __init__(self, question: str):
            self.question = question

    class M(Module):
        @staticmethod
        def the_obvious_answer() -> int:
            return 42

        question = Question

    def func(a: Answer, q: Question):
        return a, q

    a, q = Injector(Answer, M, 'What was the question?').call(func)
    assert a.value == 42
    assert q.question == 'What was the question?'


def test_circular_dependency():
    class A:
        def __init__(self):
            pass

    class B:
        def __init__(self, a: A):
            pass

    def provide_a(b: B) -> A:
        return A()

    injector = Injector(provide_a, B)
    with raises(CircularDependency):
        injector.get(A)


def test_provider_missing():
    def provide_str(a: int) -> str:
        return f'{a}'

    injector = Injector(provide_str)
    with raises(ProviderMissing):
        injector.get(str)


@mark.asyncio
async def test_async_call():
    class A:
        pass

    async def func(a: A):
        return a

    instance = await Injector(A).acall(func)
    assert isinstance(instance, A)


@mark.asyncio
async def test_async_providers():
    class A:
        pass

    class B:
        pass

    async def provide_a(b: B) -> A:
        await sleep(1e-6)
        return A()

    class M(Module):
        @staticmethod
        async def some_text() -> str:
            return 'some text'

        b = B

    async def func(a: A, text: str):
        return a

    instance = await Injector(provide_a, M).acall(func)
    assert isinstance(instance, A)


@mark.asyncio
async def test_only_one_async_dependency_instance_across_graph():
    class A:
        pass

    class B:
        def __init__(self, a: A):
            self.a = a

    class C:
        def __init__(self, b: B, a: A):
            self.a = a
            self.b = b

    async def provide_a() -> A:
        await sleep(1e-6)
        return A()

    async def provide_b(a: A) -> B:
        await sleep(1e-6)
        return B(a)

    async def provide_c(a: A, b: B) -> C:
        await sleep(1e-6)
        return C(b, a)

    async def func(a: A, c: C, b: B):
        return a, b, c

    a, b, c = await Injector(provide_a, provide_b, provide_c).acall(func)
    assert a is b.a
    assert a is c.a
    assert b is c.b


@mark.asyncio
async def test_only_one_async_dependency_instance_across_calls():
    class A:
        pass

    class B:
        def __init__(self, a: A):
            self.a = a

    async def provide_a() -> A:
        await sleep(1e-6)
        return A()

    async def func(b: B) -> A:
        return b.a

    injector = Injector(provide_a, B)
    a1 = await injector.acall(func)
    a2 = await injector.acall(func)
    a3 = await injector.acall(func)
    assert a1 is a2
    assert a2 is a3
