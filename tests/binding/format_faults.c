/* Deterministic errors at the formatter boundary; real native error state. */
#include <cvc5/c/cvc5.h>

const char *format_utf8(Cvc5Term term)
{
  (void)term;
  static const char invalid[] = {'o', 'k', (char)0xff, 0};
  return invalid;
}

const char *format_native(Cvc5Term term)
{
  (void)cvc5_term_get_boolean_value(term); /* The fixture supplies an integer. */
  return "error must be checked before conversion";
}
