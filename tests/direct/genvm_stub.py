"""A small stand-in for the GenVM runtime, enough to run Remit's built
contracts in-process.

It is not GenVM: no consensus, no gas, no sandbox. It exists so tests can run
the exact files that are deployed - including the minified ones, whose local
names are rewritten - and check they behave like the readable builds they were
made from. Storage is plain dicts and lists, a contract call is a method call,
and the jury is a scripted model whose answer the test chooses.
"""

import json
import sys
import types


class TreeMap(dict):
    """Storage map stand-in. Subscripting it in an annotation returns the class
    itself (dict's own __class_getitem__ would return a generic alias)."""

    def __class_getitem__(cls, item):
        return cls


class DynArray(list):
    def __class_getitem__(cls, item):
        return cls


def u256(value=0):
    return int(value)


def Address(value):
    return str(value)


class _Write:
    def __new__(cls, fn):
        return fn

    @staticmethod
    def payable(fn):
        return fn


class _Public:
    write = _Write

    @staticmethod
    def view(fn):
        return fn


class _Evm:
    """``gl.evm``: an EVM contract interface whose only use here is sending
    value. A transfer moves value out of the contract executing the call."""

    runtime = None

    @classmethod
    def contract_interface(cls, klass):
        rt = cls.runtime

        class _Iface:
            def __init__(self, address):
                self.address = str(address).lower()

            def emit_transfer(self, value=0):
                rt.transfer(rt.current, self.address, int(value))

        _Iface.__name__ = klass.__name__
        return _Iface


class _Response:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status


class Runtime:
    """One simulated network: contracts by address, the current sender, the
    clock, the web, and the model."""

    def __init__(self):
        self.contracts = {}
        self.sender = "0x0000000000000000000000000000000000000000"
        self.now = 1_700_000_000
        self.web = {}
        self.model = lambda prompt: {"verdict": "undetermined", "reason": "", "confidence": 0}
        self.prompts_seen = []
        self.value = 0
        self.current = None
        self.balances = {}
        self.transfers = []
        self.outbox = []  # messages emitted by the transaction running now
        self.messages = []  # (from, to, method, args, outcome) of every delivered message

    def transfer(self, source, to, value):
        if self.balances.get(source, 0) < value:
            raise Exception("insufficient balance in %s" % source)
        self.balances[source] = self.balances.get(source, 0) - value
        self.balances[to] = self.balances.get(to, 0) + value
        self.transfers.append((source, to, value))

    def call(self, address, method, *args, sender=None, value=0):
        """A transaction: ``sender`` calls ``method`` on the contract at
        ``address``, sending ``value``. State is rolled back on an exception,
        as a reverted transaction's would be."""
        import copy

        address = str(address).lower()
        if sender:
            self.sender = sender
        snapshot = (copy.deepcopy(self.contracts_state()), dict(self.balances), list(self.transfers))
        self.value, self.current = int(value), address
        self.balances[address] = self.balances.get(address, 0) + int(value)
        outbox = self.outbox = []
        try:
            result = getattr(self.contracts[address], method)(*args)
        except Exception:
            state, self.balances, self.transfers = snapshot
            for addr, data in state.items():
                self.contracts[addr].__dict__.clear()
                self.contracts[addr].__dict__.update(data)
            raise
        finally:
            self.value, self.current = 0, None
        # Messages a contract emitted run as their own transactions once this
        # one is accepted, sent by that contract; one that fails is recorded
        # and does not undo the call that sent it.
        for target, name, margs, origin in outbox:
            try:
                self.call(target, name, *margs, sender=origin)
                self.messages.append((origin, target, name, margs, "ok"))
            except Exception as exc:
                self.messages.append((origin, target, name, margs, "failed: %s" % exc))
        return result

    def contracts_state(self):
        return {addr: obj.__dict__ for addr, obj in self.contracts.items()}

    # --- what `gl` exposes ------------------------------------------------
    def make_gl(self):
        rt = self

        class Contract:
            def __init_subclass__(cls, **kw):
                super().__init_subclass__(**kw)

            @property
            def balance(self):
                return rt.balances.get(self.__dict__.get("_stub_address"), 0)

            @property
            def address(self):
                return self.__dict__.get("_stub_address")

            def __getattr__(self, name):
                # Storage fields are annotated on the class and start empty.
                ann = {}
                for klass in type(self).__mro__:
                    ann.update(getattr(klass, "__annotations__", {}))
                if name in ann:
                    kind = ann[name]
                    value = kind() if kind in (TreeMap, DynArray) else (0 if kind is u256 else "")
                    object.__setattr__(self, name, value)
                    return value
                raise AttributeError(name)

        class _Proxy:
            def __init__(self, address):
                self.address = str(address).lower()

            def view(self):
                return rt.contracts[self.address]

            def emit(self, on="accepted"):
                address, origin = self.address, rt.current

                class _Emit:
                    def __getattr__(self, name):
                        return lambda *a: rt.outbox.append((address, name, a, origin))

                return _Emit()

        class _Message:
            @property
            def sender_address(self):
                return rt.sender

            @property
            def value(self):
                return rt.value

        class _Web:
            @staticmethod
            def get(uri):
                # Measured on Studio: a 404 is a response with its status; an
                # unreachable host raises. rt.web maps a URI to bytes (200), to
                # an int status, or is missing (unreachable).
                if uri not in rt.web:
                    raise Exception("NondetException: unreachable %s" % uri)
                found = rt.web[uri]
                if isinstance(found, int):
                    return _Response(b"Not Found", found)
                return _Response(found)

        class _Nondet:
            web = _Web

            @staticmethod
            def exec_prompt(prompt, response_format=None):
                rt.prompts_seen.append(prompt)
                answer = rt.model(prompt)
                return answer if response_format == "json" else json.dumps(answer)

        class _Vm:
            @staticmethod
            def run_nondet(leader, validator, compare_user_errors=True):
                result = leader()
                if not validator(result):
                    raise Exception("validators disagreed")
                return result

        gl = types.SimpleNamespace(
            Contract=Contract,
            public=_Public,
            message=_Message(),
            nondet=_Nondet,
            vm=_Vm,
            evm=_Evm,
            get_contract_at=lambda addr: _Proxy(addr),
        )
        _Evm.runtime = rt
        return gl

    def clock(self):
        rt = self

        class _DT:
            @staticmethod
            def now():
                return types.SimpleNamespace(timestamp=lambda: float(rt.now))

        return types.SimpleNamespace(datetime=_DT)


def load(path, runtime):
    """Execute a built contract file against ``runtime``; returns its namespace."""
    gl = runtime.make_gl()
    fake = types.ModuleType("genlayer")
    for name, value in {"gl": gl, "Address": Address, "u256": u256, "TreeMap": TreeMap, "DynArray": DynArray}.items():
        setattr(fake, name, value)
    fake.__all__ = ["gl", "Address", "u256", "TreeMap", "DynArray"]
    sys.modules["genlayer"] = fake
    with open(path) as handle:
        source = handle.read()
    namespace = {"__name__": "remit_contract_under_test"}
    exec(compile(source, path, "exec"), namespace)
    namespace["datetime"] = runtime.clock()
    return namespace


def deploy(runtime, namespace, cls, address, *args, sender=None):
    if sender:
        runtime.sender = sender
    address = str(address).lower()
    obj = namespace[cls].__new__(namespace[cls])
    obj.__dict__["_stub_address"] = address
    runtime.current = address
    try:
        namespace[cls].__init__(obj, *args)
    finally:
        runtime.current = None
    runtime.contracts[address] = obj
    return obj
