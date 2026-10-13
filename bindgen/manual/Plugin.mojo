"""Plugin trait defaults and the retained, type-erased callback bridge.

The generator supplies upstream docs, C field wiring and ABI-checked setters.
Only the bridge owns the leaked allocation, which its registration frees.
"""

from std.memory import OwnedPointer
from ._c.ffi import Ptr


struct Plugin:
    def check(mut self) raises -> List[Term]:
        return List[Term]()

    def notifySatClause(mut self, clause: Term) raises:
        pass

    def notifyTheoryLemma(mut self, lemma: Term) raises:
        pass

    @staticmethod
    def getName() -> StaticString:
        return "MojoPlugin"


struct _CallbackRegistry(Movable):
    var registrations: List[_CallbackRegistration]
    var busy: Bool
    var error: String

    def __init__(out self):
        self.registrations = List[_CallbackRegistration]()
        self.busy = False
        self.error = String()

    def _check(self) raises:
        if self.error.byte_length():
            raise Error(self.error)

    def _fail(mut self, error: String, source: StaticString = "plugin"):
        if not self.error.byte_length():
            self.error = "cvc5_mojo " + String(source) + " callback: " + error

    def _available(self) raises:
        self._check()
        if self.busy:
            raise Error("cvc5_mojo: cannot reenter a solver from its callback")


struct _CallbackCall(Movable):
    var registry: ArcPointer[_CallbackRegistry]

    def __init__(out self, registry: ArcPointer[_CallbackRegistry]):
        self.registry = registry

    def __enter__(self) raises:
        self.registry[]._available()
        self.registry[].busy = True

    def __exit__(self) raises:
        self.registry[].busy = False
        self.registry[]._check()


struct _CallbackRegistration(Movable):
    var state: Ptr
    var destroy: def(Ptr) thin -> NoneType

    def __init__[T: Movable & Deinitable](out self, var value: T):
        var owned = OwnedPointer(value^)
        self.state = rebind[Ptr](owned^.unsafe_take_allocation().unsafe_leak())
        self.destroy = _destroy_callback[T]

    def __deinit__(deinit self):
        self.destroy(self.state)


struct _PluginState[P: Plugin](Movable):
    var plugin: ArcPointer[Self.P]
    var api: CApiPtr
    var tm: Cvc5TermManager
    # Registry owns this state; a borrowed back pointer avoids an Arc cycle.
    var registry: Pointer[_CallbackRegistry, MutUntrackedOrigin]
    var table: Cvc5Plugin
    var lemmas: List[Term]
    var handles: List[Cvc5Term]

    def __init__(out self, plugin: ArcPointer[Self.P], api: CApiPtr, tm: Cvc5TermManager, registry: ArcPointer[_CallbackRegistry]):
        self.plugin = plugin
        self.api = api
        self.tm = tm
        self.registry = Pointer(to=registry[]).unsafe_origin_cast[MutUntrackedOrigin]()
        self.table = Cvc5Plugin()
        self.lemmas = List[Term]()
        self.handles = List[Cvc5Term]()


def _destroy_callback[T: Movable & Deinitable](state: Ptr):
    _ = OwnedPointer[T](unsafe_from_opaque_pointer=state)


def _plugin_check[P: Plugin](size: Pointer[UInt, MutUntrackedOrigin], data: Ptr) abi("C") -> Pointer[Cvc5Term, MutUntrackedOrigin]:
    var state = data.unsafe_bitcast[_PluginState[P]]()
    size[] = 0
    if state[].registry[].error.byte_length():
        return null[Cvc5Term]()
    try:
        state[].lemmas = state[].plugin[].check()
        state[].handles.clear()
        for lemma in state[].lemmas:
            if lemma.isNull():
                raise Error("check() must return non-null Boolean terms")
            if lemma._tm.ptr != state[].tm.ptr:
                raise Error("lemma belongs to a different term manager")
            if not lemma.getSort().isBoolean():
                raise Error("check() must return Boolean terms")
            state[].handles.append(lemma._h)
        size[] = UInt(len(state[].handles))
        return state[].handles.unsafe_ptr().unsafe_origin_cast[MutUntrackedOrigin]()
    except e:
        state[].registry[]._fail(String(e))
        return null[Cvc5Term]()


def _plugin_notifySatClause[P: Plugin](handle: Ptr, data: Ptr) abi("C"):
    var state = data.unsafe_bitcast[_PluginState[P]]()
    # Native notification exports transfer a reference, even after an earlier error.
    var term = Term._received(state[].api, state[].tm, Cvc5Term(handle))
    if not state[].registry[].error.byte_length():
        try:
            state[].plugin[].notifySatClause(term)
        except e:
            state[].registry[]._fail(String(e))


def _plugin_notifyTheoryLemma[P: Plugin](handle: Ptr, data: Ptr) abi("C"):
    var state = data.unsafe_bitcast[_PluginState[P]]()
    var term = Term._received(state[].api, state[].tm, Cvc5Term(handle))
    if not state[].registry[].error.byte_length():
        try:
            state[].plugin[].notifyTheoryLemma(term)
        except e:
            state[].registry[]._fail(String(e))


def _plugin_getName[P: Plugin]() abi("C") -> CChars:
    comptime name = P.getName()
    # The raw layer spells C string results with a mutable pointer type;
    # cvc5 receives const char* and must never write the embedded literal.
    return name.as_c_string_span().ptr().unsafe_mut_cast[True]().unsafe_origin_cast[MutUntrackedOrigin]()
