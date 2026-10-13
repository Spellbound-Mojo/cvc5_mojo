"""Hand-written methods of `Solver`, and the `OptionInfo` they return.

`bindgen.gen_api` splices the methods of `struct Solver` below into the
generated class, adding cvc5's docstrings, and appends the definitions after
it to the generated module, `src/cvc5_mojo/solver.mojo`. This file is not
compiled on its own.

Python returns an option's information as a dict whose keys depend on the
option's value type. Mojo cannot type such a dict, so an `OptionInfo` has
every key as a field. cvc5 fills a `Cvc5OptionInfo` struct, which the raw
layer reads at the offsets the C compiler measured.
"""

from std.utils import Variant
from ._c.ffi import Ptr


struct Solver:
    def addPlugin[P: Plugin](self, plugin: ArcPointer[P]) raises:
        var registration = _CallbackRegistration(_PluginState(plugin, self._o[].api, self._o[].tm, self._o[].callbacks))
        var state = registration.state.unsafe_bitcast[_PluginState[P]]()
        _wire_plugin[P](state[].table, registration.state)
        var table = Pointer(to=state[].table).unsafe_origin_cast[MutUntrackedOrigin]()
        # The native API may retain the table before reporting a registration error.
        self._o[].callbacks[].registrations.append(registration^)
        self._o[].api[].cvc5_add_plugin(self._handle(), table)

    def declareOracleFun[O: Oracle](self, symbol: String, sorts: List[Sort], sort: Sort, oracle: ArcPointer[O]) raises -> Term:
        if sort.isNull() or sort._tm.ptr != self._o[].tm.ptr:
            raise Error("cvc5_mojo: oracle result sort must belong to this term manager")
        var handles = List[Cvc5Sort](capacity=len(sorts))
        for domain in sorts:
            if domain.isNull() or domain._tm.ptr != self._o[].tm.ptr:
                raise Error("cvc5_mojo: oracle domain sort must belong to this term manager")
            handles.append(domain._h)
        var symbol_c = c_bytes(symbol)
        var tm = TermManager(_borrowed=self._o[].tm, _from_solver=self._o)
        # A deliberately different sort makes cvc5's checked oracle evaluator
        # unwind to the public call boundary. No fabricated result escapes.
        var sentinel = tm.mkInteger(0) if sort.isBoolean() else tm.mkTrue()
        var registration = _CallbackRegistration(_OracleState(oracle, self._o[].api, self._o[].tm, self._o[].callbacks, sort, sentinel))
        var state = registration.state
        self._o[].callbacks[].registrations.append(registration^)
        var handle = self._o[].api[].cvc5_declare_oracle_fun(self._handle(), symbol_c.unsafe_ptr(), UInt(len(handles)), handles.unsafe_ptr(), sort._h, state, _oracle_evaluate[O])
        return Term._received(self._o[].api, self._o[].tm, handle)

    def getOptionInfo(self, option: String) raises -> OptionInfo:
        var option_c = c_bytes(option)
        var info = Cvc5OptionInfo()
        self._o[].api[].cvc5_get_option_info(self._handle(), option_c.unsafe_ptr(), Pointer(to=info))
        return OptionInfo(_info=info)


trait Oracle(Movable, Deinitable):
    """A deterministic implementation of an SMT oracle function.

    Retained by `Solver.declareOracleFun`. Arguments are owned terms and may
    be copied; return a non-null term of the declared sort and term manager.
    Do not call back into the registering solver or its parser. An error
    invalidates that solver and is raised after native evaluation unwinds.
    """

    def evaluate(mut self, arguments: List[Term]) raises -> Term:
        ...


struct _OracleState[O: Oracle](Movable):
    var oracle: ArcPointer[Self.O]
    var api: CApiPtr
    var tm: Cvc5TermManager
    var registry: Pointer[_CallbackRegistry, MutUntrackedOrigin]
    var sort: Sort
    var sentinel: Term
    var result: Term

    def __init__(out self, oracle: ArcPointer[Self.O], api: CApiPtr, tm: Cvc5TermManager, registry: ArcPointer[_CallbackRegistry], sort: Sort, sentinel: Term):
        self.oracle = oracle
        self.api = api
        self.tm = tm
        self.registry = Pointer(to=registry[]).unsafe_origin_cast[MutUntrackedOrigin]()
        self.sort = sort
        self.sentinel = sentinel
        self.result = sentinel


def _oracle_evaluate[O: Oracle](size: UInt, handles: Pointer[Cvc5Term, MutUntrackedOrigin], data: Ptr) abi("C") -> Ptr:
    var state = data.unsafe_bitcast[_OracleState[O]]()
    # Receive every exported argument even if another callback has failed.
    var arguments = List[Term](capacity=Int(size))
    for i in range(Int(size)):
        arguments.append(Term._received(state[].api, state[].tm, handles[unsafe_offset=i]))
    if not state[].registry[].error.byte_length():
        try:
            var result = state[].oracle[].evaluate(arguments)
            if result.isNull():
                raise Error("evaluate() must return a non-null term")
            if result._tm.ptr != state[].tm.ptr:
                raise Error("result belongs to a different term manager")
            if result.getSort() != state[].sort:
                raise Error("result does not have the declared oracle sort")
            state[].result = result^
            return state[].result._h.ptr
        except e:
            state[].registry[]._fail(String(e), "oracle")
    return state[].sentinel._h.ptr


struct OptionInfo(Copyable, Movable, Writable):
    """Information about an option, as `Solver.getOptionInfo` returns it.

    Python returns a dict whose keys depend on the option's value type; an
    `OptionInfo` has every key as a field, and a key Python leaves out for
    that type is `None`, or an empty `modes`. It prints as Python prints the
    dict.
    """

    comptime Value = Variant[Bool, String, Int, UInt64, Float64]
    """A value: `Bool`, `String` (also a mode), `Int` for int64 options,
    `UInt64` for uint64 options, or `Float64`. Python has `int` for both."""

    var name: String
    """The option's name."""
    var aliases: List[String]
    """Its other names."""
    var setByUser: Bool
    """Whether the user set it."""
    var category: OptionCategory
    """Its category."""
    var type: Optional[String]
    """Its value type as Python names it: "bool", "str", "int", "float" or
    "mode"; `None` for an option without a value."""
    var current: Optional[Self.Value]
    """The current value."""
    var default: Optional[Self.Value]
    """The default value."""
    var minimum: Optional[Self.Value]
    """The smallest value allowed, for a number with a lower bound."""
    var maximum: Optional[Self.Value]
    """The largest value allowed, for a number with an upper bound."""
    var modes: List[String]
    """The modes a mode option allows."""

    def __init__(out self, *, _info: Cvc5OptionInfo) raises:
        """Copy what cvc5 filled in, which is valid only until its next call.

        Args:
            _info: The struct cvc5 filled.
        """
        self.name = to_string(_info.name())
        self.aliases = to_strings(_info.aliases(), _info.num_aliases())
        self.setByUser = _info.is_set_by_user()
        self.category = _info.category()
        self.type = None
        self.current = None
        self.default = None
        self.minimum = None
        self.maximum = None
        self.modes = List[String]()
        var kind = _info.kind()
        if kind == Cvc5OptionInfoKind.BOOL:
            self.type = String("bool")
            self.current = Self.Value(_info.info_bool_cur())
            self.default = Self.Value(_info.info_bool_dflt())
        elif kind == Cvc5OptionInfoKind.STR:
            self.type = String("str")
            self.current = Self.Value(to_string(_info.info_str_cur()))
            self.default = Self.Value(to_string(_info.info_str_dflt()))
        elif kind == Cvc5OptionInfoKind.INT64:
            self.type = String("int")
            self.current = Self.Value(Int(_info.info_int_cur()))
            self.default = Self.Value(Int(_info.info_int_dflt()))
            if _info.info_int_has_min():
                self.minimum = Self.Value(Int(_info.info_int_min()))
            if _info.info_int_has_max():
                self.maximum = Self.Value(Int(_info.info_int_max()))
        elif kind == Cvc5OptionInfoKind.UINT64:
            self.type = String("int")
            self.current = Self.Value(_info.info_uint_cur())
            self.default = Self.Value(_info.info_uint_dflt())
            if _info.info_uint_has_min():
                self.minimum = Self.Value(_info.info_uint_min())
            if _info.info_uint_has_max():
                self.maximum = Self.Value(_info.info_uint_max())
        elif kind == Cvc5OptionInfoKind.DOUBLE:
            self.type = String("float")
            self.current = Self.Value(_info.info_double_cur())
            self.default = Self.Value(_info.info_double_dflt())
            if _info.info_double_has_min():
                self.minimum = Self.Value(_info.info_double_min())
            if _info.info_double_has_max():
                self.maximum = Self.Value(_info.info_double_max())
        elif kind == Cvc5OptionInfoKind.MODES:
            self.type = String("mode")
            self.current = Self.Value(to_string(_info.info_mode_cur()))
            self.default = Self.Value(to_string(_info.info_mode_dflt()))
            self.modes = to_strings(_info.info_mode_modes(), _info.info_mode_num_modes())

    def write_to(self, mut writer: Some[Writer]):
        """Write the information as Python prints its dict.

        For example `{'name': 'verbosity', 'aliases': [], 'setByUser': False,
        'category': <OptionCategory.COMMON: 2>, 'type': <class 'int'>,
        'current': 0, 'default': 0, 'minimum': None, 'maximum': None}`.

        Args:
            writer: The writer.
        """
        writer.write("{'name': ")
        write_python_repr(writer, self.name)
        writer.write(", 'aliases': ")
        _write_list(writer, self.aliases)
        writer.write(", 'setByUser': ", self.setByUser, ", 'category': ")
        self.category.write_repr_to(writer)
        writer.write(", 'type': ")
        if not self.type:
            writer.write("None}")
            return
        var type = self.type.value()
        if type == "mode":
            writer.write("'mode'")
        else:
            writer.write("<class '", type, "'>")
        writer.write(", 'current': ")
        _write_value(writer, self.current)
        writer.write(", 'default': ")
        _write_value(writer, self.default)
        if type == "int" or type == "float":
            writer.write(", 'minimum': ")
            _write_value(writer, self.minimum)
            writer.write(", 'maximum': ")
            _write_value(writer, self.maximum)
        if type == "mode":
            writer.write(", 'modes': ")
            _write_list(writer, self.modes)
        writer.write("}")


def _write_list(mut writer: Some[Writer], items: List[String]):
    """Write a list of strings as Python prints it.

    Args:
        writer: The writer.
        items: The strings.
    """
    writer.write("[")
    for i in range(len(items)):
        if i:
            writer.write(", ")
        write_python_repr(writer, items[i])
    writer.write("]")


def _write_value(mut writer: Some[Writer], value: Optional[OptionInfo.Value]):
    """Write an option value as Python prints it.

    Args:
        writer: The writer.
        value: The value, if any.
    """
    if not value:
        writer.write("None")
        return
    ref v = value.value()
    if v.isa[Bool]():
        writer.write(v[Bool])
    elif v.isa[String]():
        write_python_repr(writer, v[String])
    elif v.isa[Int]():
        writer.write(v[Int])
    elif v.isa[UInt64]():
        writer.write(v[UInt64])
    else:
        writer.write(v[Float64])  # Mojo's shortest form is Python's repr
