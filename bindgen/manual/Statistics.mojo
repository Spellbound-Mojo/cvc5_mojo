"""Hand-written methods of `Statistics`, and the `Stat` values they return.

`bindgen.gen_api` splices the methods of `struct Statistics` below into the
generated class, adding cvc5's docstrings, and appends the definitions after
it to the generated module, `src/cvc5_mojo/statistics.mojo`. This file is
not compiled on its own.

Python returns each statistic as a dict, `{'default': ..., 'internal': ...,
'value': ...}`, whose value is an int, a float, a string or a histogram (a
dict from names to counts). Mojo cannot type such a dict, so a `Stat` has
its three keys as fields.
"""

from std.utils import Variant


struct Statistics:
    def __getitem__(self, name: String) raises -> Stat:
        var name_c = c_bytes(name)
        return _StatReference(self._api, self._api[].cvc5_stats_get(self._h, name_c.unsafe_ptr())).stat()

    def __iter__(self) raises -> OwnedIterator[Tuple[String, Stat]]:
        return OwnedIterator(self._read(True, True))

    def get(self, internal: Bool = False, defaulted: Bool = False) raises -> Dict[String, Stat]:
        var snapshot = self._read(internal, defaulted)
        var out = Dict[String, Stat](capacity=len(snapshot))
        for entry in snapshot:
            out[entry[0]] = entry[1].copy()
        return out^

    def _read(self, internal: Bool, defaulted: Bool) raises -> List[Tuple[String, Stat]]:
        """Read the statistics with cvc5's iterator, which this object holds.

        Args:
            internal: Whether to include internal statistics.
            defaulted: Whether to include statistics that still have their
                default value.

        Returns:
            The name and value of each statistic, in cvc5's order.
        """
        self._api[].cvc5_stats_iter_init(self._h, internal, defaulted)
        var out = List[Tuple[String, Stat]]()
        while self._api[].cvc5_stats_iter_has_next(self._h):
            var name = null[Int8]()
            var stat = _StatReference(self._api, self._api[].cvc5_stats_iter_next(self._h, Pointer(to=name)))
            var key = to_string(name)  # valid until the next C API call
            out.append((key, stat.stat()))
        return out^


struct Stat(Copyable, Movable, Writable):
    """A cvc5 statistic, as `Statistics` returns it.

    Python returns a dict with the keys `default`, `internal` and `value`; a
    `Stat` has them as fields, so Python's `stats["name"]["value"]` is
    `stats["name"].value`. It prints as Python prints that dict.
    """

    comptime Value = Variant[Int, Float64, String, Dict[String, UInt64]]
    """A value: an integer, a float, a string, or a histogram from names to counts."""

    var default: Bool
    """Whether the statistic still has its default value."""
    var internal: Bool
    """Whether the statistic is internal to cvc5."""
    var value: Self.Value
    """The value; `value.isa[Int]()` tests its type and `value[Int]` reads it."""

    def __init__(out self, default: Bool, internal: Bool, var value: Self.Value):
        """Create a statistic.

        Args:
            default: Whether it still has its default value.
            internal: Whether it is internal to cvc5.
            value: The value.
        """
        self.default = default
        self.internal = internal
        self.value = value^

    def write_to(self, mut writer: Some[Writer]):
        """Write the statistic as Python prints its dict.

        For example `{'default': False, 'internal': True, 'value': 0.0}`.

        Args:
            writer: The writer.
        """
        writer.write("{'default': ", self.default, ", 'internal': ", self.internal, ", 'value': ")
        if self.value.isa[Int]():
            writer.write(self.value[Int])
        elif self.value.isa[Float64]():
            writer.write(self.value[Float64])  # Mojo's shortest form is Python's repr
        elif self.value.isa[String]():
            write_python_repr(writer, self.value[String])
        else:
            writer.write("{")
            var first = True
            for entry in self.value[Dict[String, UInt64]].items():
                if not first:
                    writer.write(", ")
                first = False
                write_python_repr(writer, entry.key)
                writer.write(": ", entry.value)
            writer.write("}")
        writer.write("}")



struct _StatReference(Movable):
    """One cvc5 reference to a statistic, released on destruction.

    Python has no `Stat` class, so the reference lives only while the
    statistic is read into a `Stat`.
    """

    var api: CApiPtr
    var h: Cvc5Stat

    def __init__(out self, api: CApiPtr, h: Cvc5Stat):
        """Take ownership of a statistic cvc5 returned.

        Args:
            api: The C API.
            h: The statistic.
        """
        self.api = api
        self.h = h

    def stat(self) raises -> Stat:
        """Read the statistic.

        Returns:
            Its flags and its value.
        """
        return Stat(self.api[].cvc5_stat_is_default(self.h), self.api[].cvc5_stat_is_internal(self.h), self.value())

    def value(self) raises -> Stat.Value:
        """Read the value, whichever of the four kinds it is.

        Returns:
            The value.
        """
        if self.api[].cvc5_stat_is_int(self.h):
            return Stat.Value(Int(self.api[].cvc5_stat_get_int(self.h)))
        if self.api[].cvc5_stat_is_double(self.h):
            return Stat.Value(self.api[].cvc5_stat_get_double(self.h))
        if self.api[].cvc5_stat_is_string(self.h):
            return Stat.Value(to_string(self.api[].cvc5_stat_get_string(self.h)))
        if self.api[].cvc5_stat_is_histogram(self.h):
            var names = null[CChars]()
            var counts = null[UInt64]()
            var size = UInt(0)
            self.api[].cvc5_stat_get_histogram(self.h, Pointer(to=names), Pointer(to=counts), Pointer(to=size))
            var histogram = Dict[String, UInt64](capacity=Int(size))
            for i in range(Int(size)):
                histogram[to_string(names[unsafe_offset=i])] = counts[unsafe_offset=i]
            return Stat.Value(histogram^)
        raise Error("cvc5_mojo: the statistic has no value")

    def __deinit__(deinit self):
        """Release the reference."""
        try:
            self.api[].cvc5_stat_release(self.h)
        except e:
            abort(String(e))

