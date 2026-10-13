"""Exact native numeric access and lossless string-value conversion."""

from ._c.ffi import unescape_smt_string


struct Term:
    def getIntegerValue(self) raises -> Integer:
        var api = self._api
        if api[].cvc5_term_is_int64_value(self._h):
            return Integer(api[].cvc5_term_get_int64_value(self._h))
        if api[].cvc5_term_is_uint64_value(self._h):
            return Integer(api[].cvc5_term_get_uint64_value(self._h))
        return Integer(to_string(api[].cvc5_term_get_integer_value(self._h)))

    def getRealValue(self) raises -> Rational:
        var api = self._api
        if api[].cvc5_term_is_real64_value(self._h):
            var num = Int64(0)
            var den = UInt64(0)
            api[].cvc5_term_get_real64_value(self._h, Pointer(to=num), Pointer(to=den))
            return Rational(Integer(num), Integer(den))
        return Rational(to_string(api[].cvc5_term_get_real_value(self._h)))

    def getStringValue(self) raises -> String:
        # Retain the C getter's type validation. Its zero-terminated result
        # cannot describe embedded NUL, whereas the quoted representation can.
        _ = self._api[].cvc5_term_get_u32string_value(self._h)
        return unescape_smt_string(to_string(self._api[].cvc5_term_to_string(self._h)))
