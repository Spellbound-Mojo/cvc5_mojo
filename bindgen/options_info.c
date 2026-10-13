/* Query the pinned binary through its own headers; no option names are listed here. */
#include <cvc5/c/cvc5.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

static void string(const char* value)
{
  if (!value) { fputs("null", stdout); return; }
  putchar('"');
  for (const unsigned char* p = (const unsigned char*) value; *p; ++p)
  {
    if (*p == '"' || *p == '\\') { putchar('\\'); putchar(*p); }
    else if (*p < 32) { printf("\\u%04x", *p); }
    else { putchar(*p); }
  }
  putchar('"');
}

static void strings(size_t size, const char* const* values)
{
  putchar('[');
  for (size_t i = 0; i < size; ++i) { if (i) putchar(','); string(values[i]); }
  putchar(']');
}

static void check(void)
{
  if (cvc5_has_error()) { fprintf(stderr, "%s\n", cvc5_get_error_message()); exit(1); }
}

int main(void)
{
  Cvc5TermManager* tm = cvc5_term_manager_new();
  Cvc5* solver = cvc5_new(tm);
  check();
  size_t size;
  const char** names = cvc5_get_option_names(solver, &size);
  check();
  putchar('[');
  for (size_t i = 0; i < size; ++i)
  {
    Cvc5OptionInfo info;
    cvc5_get_option_info(solver, names[i], &info);
    check();
    if (i) putchar(',');
    fputs("{\"name\":", stdout); string(info.name);
    fputs(",\"aliases\":", stdout); strings(info.num_aliases, info.aliases);
    fputs(",\"no_support\":", stdout); strings(info.num_no_supports, info.no_supports);
    fputs(",\"value_kind\":", stdout);
    switch (info.kind)
    {
      case CVC5_OPTION_INFO_VOID:
        string("void"); fputs(",\"default\":null", stdout); break;
      case CVC5_OPTION_INFO_BOOL:
        string("bool"); fputs(",\"default\":", stdout); string(info.info_bool.dflt ? "true" : "false"); break;
      case CVC5_OPTION_INFO_STR:
        string("string"); fputs(",\"default\":", stdout); string(info.info_str.dflt); break;
      case CVC5_OPTION_INFO_INT64:
        string("int64"); printf(",\"default\":\"%" PRId64 "\"", info.info_int.dflt);
        if (info.info_int.has_min) printf(",\"minimum\":\"%" PRId64 "\"", info.info_int.min);
        if (info.info_int.has_max) printf(",\"maximum\":\"%" PRId64 "\"", info.info_int.max);
        break;
      case CVC5_OPTION_INFO_UINT64:
        string("uint64"); printf(",\"default\":\"%" PRIu64 "\"", info.info_uint.dflt);
        if (info.info_uint.has_min) printf(",\"minimum\":\"%" PRIu64 "\"", info.info_uint.min);
        if (info.info_uint.has_max) printf(",\"maximum\":\"%" PRIu64 "\"", info.info_uint.max);
        break;
      case CVC5_OPTION_INFO_DOUBLE:
        string("double"); printf(",\"default\":\"%.17g\"", info.info_double.dflt);
        if (info.info_double.has_min) printf(",\"minimum\":\"%.17g\"", info.info_double.min);
        if (info.info_double.has_max) printf(",\"maximum\":\"%.17g\"", info.info_double.max);
        break;
      case CVC5_OPTION_INFO_MODES:
        string("modes"); fputs(",\"default\":", stdout); string(info.info_mode.dflt);
        fputs(",\"modes\":", stdout); strings(info.info_mode.num_modes, info.info_mode.modes);
        break;
      default:
        fputs("Unknown option info kind\n", stderr); return 1;
    }
    putchar('}');
  }
  puts("]");
  cvc5_delete(solver);
  cvc5_term_manager_delete(tm);
  return 0;
}
