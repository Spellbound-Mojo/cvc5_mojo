/* Independent semantic oracle for compound Mojo FFI crossings. */
#include <cvc5/c/cvc5_parser.h>
#include <inttypes.h>
#include <stdint.h>
#include "support.h"

static int rejected(void)
{
  int result = cvc5_has_error();
  cvc5_reset_error();
  require(result, "expected a recoverable native error");
  return result;
}

static void scalar_outputs(Cvc5TermManager* tm)
{
  Cvc5Term r32 = V(cvc5_mk_real(tm, "-2147483648/4294967295"));
  Cvc5Term r64 = V(cvc5_mk_real(tm, "-9223372036854775808/18446744073709551615"));
  int32_t n32[3] = {12345, 0, 12345};
  uint32_t d32[3] = {12345, 0, 12345};
  int64_t n64[3] = {12345, 0, 12345};
  uint64_t d64[3] = {12345, 0, 12345};
  DO(cvc5_term_get_real32_value(r32, &n32[1], &d32[1]));
  DO(cvc5_term_get_real64_value(r64, &n64[1], &d64[1]));
  require(n32[0] == 12345 && n32[2] == 12345 && d32[0] == 12345 && d32[2] == 12345, "32-bit overwrite");
  require(n64[0] == 12345 && n64[2] == 12345 && d64[0] == 12345 && d64[2] == 12345, "64-bit overwrite");
  require(n32[1] == INT32_MIN && d32[1] == UINT32_MAX && n64[1] == INT64_MIN && d64[1] == UINT64_MAX, "scalar boundary");
  printf("real32 %" PRId32 "/%" PRIu32 "\n", n32[1], d32[1]);
  printf("real64 %" PRId64 "/%" PRIu64 "\n", n64[1], d64[1]);

  Cvc5Term bits = V(cvc5_mk_bv_uint64(tm, 16, 0xbeef));
  Cvc5Term fp = V(cvc5_mk_fp(tm, 5, 11, bits));
  uint32_t ew[3] = {12345, 0, 12345}, sw[3] = {12345, 0, 12345};
  Cvc5Term value[3] = {bits, NULL, bits};
  DO(cvc5_term_get_fp_value(fp, &ew[1], &sw[1], &value[1]));
  require(ew[0] == 12345 && ew[2] == 12345 && sw[0] == 12345 && sw[2] == 12345 && value[0] == bits && value[2] == bits, "tuple overwrite");
  require(ew[1] == 5 && sw[1] == 11 && V(cvc5_term_is_equal(bits, value[1])), "FP tuple");
  printf("fp %u %u %s\n", ew[1], sw[1], V(cvc5_term_get_bv_value(value[1], 16)));
  DO(cvc5_term_release(value[1]));
  cvc5_term_get_fp_value(r32, &ew[1], &sw[1], &value[1]);
  rejected();
  DO(cvc5_term_get_fp_value(fp, &ew[1], &sw[1], &value[1]));
  DO(cvc5_term_release(value[1]));
  puts("fp-error recovered");

  Cvc5Sort sort = V(cvc5_mk_uninterpreted_sort(tm, "U"));
  Cvc5Term cc = V(cvc5_mk_cardinality_constraint(tm, sort, UINT32_MAX));
  Cvc5Sort out[3] = {sort, NULL, sort};
  uint32_t upper[3] = {12345, 0, 12345};
  DO(cvc5_term_get_cardinality_constraint(cc, &out[1], &upper[1]));
  require(out[0] == sort && out[2] == sort && upper[0] == 12345 && upper[2] == 12345, "cardinality overwrite");
  require(V(cvc5_sort_is_equal(sort, out[1])) && upper[1] == UINT32_MAX, "cardinality boundary");
  printf("cardinality %u\n", upper[1]);
  DO(cvc5_sort_release(out[1]));
  DO(cvc5_term_release(cc)); DO(cvc5_sort_release(sort));
  DO(cvc5_term_release(fp)); DO(cvc5_term_release(bits));
  DO(cvc5_term_release(r32)); DO(cvc5_term_release(r64));
}

static void arrays(Cvc5TermManager* tm)
{
  Cvc5* solver = V(cvc5_new(tm));
  DO(cvc5_set_logic(solver, "QF_LIA"));
  DO(cvc5_set_option(solver, "produce-models", "true"));
  size_t size[3] = {12345, 999, 12345};
  const Cvc5Term* empty = V(cvc5_get_assertions(solver, &size[1]));
  (void)empty;
  require(size[0] == 12345 && size[1] == 0 && size[2] == 12345, "empty size_t result");
  puts("assertions 0");
  Cvc5Result sat = V(cvc5_check_sat(solver));
  require(V(cvc5_result_is_sat(sat)), "constant model");
  DO(cvc5_result_release(sat));
  size_t lengths[] = {0, 1, 2, 7, 31, 257};
  for (size_t k = 0; k < sizeof(lengths) / sizeof(lengths[0]); ++k)
  {
    size_t n = lengths[k];
    Cvc5Term inputs[257];
    for (size_t i = 0; i < n; ++i) inputs[i] = V(cvc5_mk_integer_int64(tm, (int64_t)(i * 37 % 101) - 50));
    const Cvc5Term* native = V(cvc5_get_values(solver, n, inputs, &size[1]));
    require(size[0] == 12345 && size[1] == n && size[2] == 12345, "returned length");
    Cvc5Term held[257];
    if (n) memcpy(held, native, n * sizeof(*held));
    /* A second call overwrites the native array, while exports remain owned. */
    Cvc5Term later = V(cvc5_mk_integer_int64(tm, 999));
    const Cvc5Term* replaced = V(cvc5_get_values(solver, 1, &later, &size[1]));
    DO(cvc5_term_release(replaced[0])); DO(cvc5_term_release(later));
    int64_t checksum = 0;
    for (size_t i = 0; i < n; ++i)
    {
      int64_t value = V(cvc5_term_get_int64_value(held[i]));
      require(value == (int64_t)(i * 37 % 101) - 50, "array value/order");
      checksum += (int64_t)(i + 1) * value;
      DO(cvc5_term_release(held[i])); DO(cvc5_term_release(inputs[i]));
    }
    printf("values %zu %" PRId64 "\n", n, checksum);
  }
  DO(cvc5_delete(solver));

  solver = V(cvc5_new(tm));
  DO(cvc5_set_option(solver, "produce-unsat-cores", "true"));
  Cvc5Term ff = V(cvc5_mk_false(tm));
  DO(cvc5_assert_formula(solver, ff));
  Cvc5Result result = NULL;
  const Cvc5Term* core = V(cvc5_get_timeout_core(solver, &result, &size[1]));
  require(V(cvc5_result_is_unsat(result)) && size[1] == 1 && V(cvc5_term_is_equal(core[0], ff)), "result and array");
  puts("timeout-core unsat 1");
  DO(cvc5_term_release(core[0])); DO(cvc5_result_release(result));
  DO(cvc5_term_release(ff)); DO(cvc5_delete(solver));
}

static void symbols(Cvc5TermManager* tm)
{
  Cvc5Sort integer = V(cvc5_get_integer_sort(tm));
  const char* symbols[] = {NULL, NULL, "", "sigma_π"};
  for (int kind = 0; kind < 5; ++kind)
    for (int mode = 0; mode < 4; ++mode)
    {
      const char* name = symbols[mode];
      int has;
      if (kind < 2)
      {
        Cvc5Term term = kind == 0 ? V(cvc5_mk_const(tm, integer, name)) : V(cvc5_mk_var(tm, integer, name));
        has = V(cvc5_term_has_symbol(term));
        printf("symbol %d %d %d %s\n", kind, mode, has, has ? V(cvc5_term_get_symbol(term)) : "-");
        DO(cvc5_term_release(term));
      }
      else
      {
        if (kind == 2 && mode < 2)
        {
          cvc5_mk_param_sort(tm, name);
          rejected();
          printf("symbol %d %d rejected\n", kind, mode);
          continue;
        }
        Cvc5Sort sort = kind == 2 ? V(cvc5_mk_param_sort(tm, name)) : kind == 3 ? V(cvc5_mk_uninterpreted_sort(tm, name)) : V(cvc5_mk_uninterpreted_sort_constructor_sort(tm, 2, name));
        has = V(cvc5_sort_has_symbol(sort));
        printf("symbol %d %d %d %s\n", kind, mode, has, has ? V(cvc5_sort_get_symbol(sort)) : "-");
        DO(cvc5_sort_release(sort));
      }
    }
  DO(cvc5_sort_release(integer));
}

static Cvc5Term term2(Cvc5TermManager* tm, Cvc5Kind kind, Cvc5Term a, Cvc5Term b)
{
  Cvc5Term args[] = {a, b};
  return V(cvc5_mk_term(tm, kind, 2, args));
}

static void nested(Cvc5TermManager* tm, int mode)
{
  Cvc5* solver = V(cvc5_new(tm));
  DO(cvc5_set_logic(solver, "ALL"));
  Cvc5Sort integer = V(cvc5_get_integer_sort(tm));
  Cvc5Sort domains[] = {integer, integer};
  Cvc5Sort unary = V(cvc5_mk_fun_sort(tm, 1, domains, integer));
  Cvc5Sort binary = V(cvc5_mk_fun_sort(tm, 2, domains, integer));
  Cvc5Term funs[] = {V(cvc5_mk_const(tm, integer, "f0")), V(cvc5_mk_const(tm, unary, "f1")), V(cvc5_mk_const(tm, binary, "f2"))};
  Cvc5Term x = V(cvc5_mk_var(tm, integer, "x")), y = V(cvc5_mk_var(tm, integer, "y")), z = V(cvc5_mk_var(tm, integer, "z"));
  Cvc5Term pair[] = {y, z};
  size_t sizes[] = {0, 1, 2};
  const Cvc5Term* vars[] = {NULL, &x, pair};
  Cvc5Term one = V(cvc5_mk_integer_int64(tm, 1)), seven = V(cvc5_mk_integer_int64(tm, 7));
  Cvc5Term bodies[] = {seven, term2(tm, CVC5_KIND_ADD, x, one), term2(tm, CVC5_KIND_SUB, y, z)};
  /* Same lengths, invalid bound-variable kind: native error then recovery. */
  const Cvc5Term* invalid[] = {NULL, &one, pair};
  cvc5_define_funs_rec(solver, 3, funs, sizes, invalid, bodies, false);
  rejected();
  DO(cvc5_push(solver, 1));
  DO(cvc5_define_funs_rec(solver, 3, funs, sizes, vars, bodies, mode == 2));
  Cvc5Term args1[] = {funs[1], seven}, args2[] = {funs[2], seven, one};
  Cvc5Term calls[] = {funs[0], V(cvc5_mk_term(tm, CVC5_KIND_APPLY_UF, 2, args1)), V(cvc5_mk_term(tm, CVC5_KIND_APPLY_UF, 3, args2))};
  int64_t expected[] = {7, 8, 6};
  for (int i = 0; i < 3; ++i)
  {
    Cvc5Term target = V(cvc5_mk_integer_int64(tm, expected[i]));
    Cvc5Term wrong = term2(tm, CVC5_KIND_DISTINCT, calls[i], target);
    DO(cvc5_push(solver, 1)); DO(cvc5_assert_formula(solver, wrong));
    Cvc5Result res = V(cvc5_check_sat(solver));
    require(V(cvc5_result_is_unsat(res)), "nested row not transmitted correctly");
    DO(cvc5_result_release(res)); DO(cvc5_pop(solver, 1));
    DO(cvc5_term_release(wrong)); DO(cvc5_term_release(target));
  }
  DO(cvc5_pop(solver, 1));
  /* f0 = 1 is incompatible with the retained global definition f0 = 7. */
  Cvc5Term eq = term2(tm, CVC5_KIND_EQUAL, funs[0], one);
  DO(cvc5_assert_formula(solver, eq));
  Cvc5Result res = V(cvc5_check_sat(solver));
  require(mode == 2 ? V(cvc5_result_is_unsat(res)) : V(cvc5_result_is_sat(res)), "global definition flag");
  printf("nested %d %s\n", mode, mode == 2 ? "unsat" : "sat");
  DO(cvc5_result_release(res)); DO(cvc5_term_release(eq));
  DO(cvc5_term_release(calls[1])); DO(cvc5_term_release(calls[2]));
  DO(cvc5_term_release(bodies[1])); DO(cvc5_term_release(bodies[2]));
  for (int i = 0; i < 3; ++i) DO(cvc5_term_release(funs[i]));
  DO(cvc5_term_release(x)); DO(cvc5_term_release(y)); DO(cvc5_term_release(z));
  DO(cvc5_term_release(one)); DO(cvc5_term_release(seven));
  DO(cvc5_sort_release(unary)); DO(cvc5_sort_release(binary)); DO(cvc5_sort_release(integer));
  DO(cvc5_delete(solver));
}

static Cvc5DatatypeDecl declaration(Cvc5TermManager* tm, const char* name)
{
  Cvc5DatatypeDecl decl = V(cvc5_mk_dt_decl(tm, name, false));
  char ctor_name[64];
  snprintf(ctor_name, sizeof(ctor_name), "make_%s", name);
  Cvc5DatatypeConstructorDecl ctor = V(cvc5_mk_dt_cons_decl(tm, ctor_name));
  DO(cvc5_dt_decl_add_constructor(decl, ctor));
  DO(cvc5_dt_cons_decl_release(ctor));
  return decl;
}

static void bulk_sorts(Cvc5TermManager* tm)
{
  for (size_t n = 1; n <= 7; n += 6)
  {
    Cvc5DatatypeDecl decls[7];
    char name[64];
    for (size_t i = 0; i < n; ++i)
    {
      snprintf(name, sizeof(name), "D%zu_%zu", n, i);
      decls[i] = declaration(tm, name);
    }
    const Cvc5Sort* native = V(cvc5_mk_dt_sorts(tm, n, decls));
    Cvc5Sort held[7];
    memcpy(held, native, n * sizeof(*held));
    snprintf(name, sizeof(name), "Spare%zu", n);
    Cvc5DatatypeDecl spare = declaration(tm, name);
    const Cvc5Sort* replaced = V(cvc5_mk_dt_sorts(tm, 1, &spare));
    DO(cvc5_sort_release(replaced[0])); DO(cvc5_dt_decl_release(spare));
    for (size_t i = 0; i < n; ++i)
    {
      snprintf(name, sizeof(name), "D%zu_%zu", n, i);
      Cvc5Datatype dt = V(cvc5_sort_get_datatype(held[i]));
      require(strcmp(V(cvc5_dt_get_name(dt)), name) == 0, "input-sized sort array");
      DO(cvc5_dt_release(dt)); DO(cvc5_sort_release(held[i])); DO(cvc5_dt_decl_release(decls[i]));
    }
    printf("datatype-array %zu\n", n);
  }
}

static void options(Cvc5TermManager* tm)
{
  Cvc5* solver = V(cvc5_new(tm));
  const char* names[] = {"bv-abstraction-size", "enum-inst-limit", "deep-restart-factor", "produce-models"};
  const char* values[] = {"18446744073709551615", "-17", "3.5", "true"};
  for (int i = 0; i < 4; ++i)
  {
    DO(cvc5_set_option(solver, names[i], values[i]));
    struct { uint64_t before; Cvc5OptionInfo info; uint64_t after; } box = {0};
    box.before = box.after = 12345;
    DO(cvc5_get_option_info(solver, names[i], &box.info));
    require(box.before == 12345 && box.after == 12345 && box.info.is_set_by_user, "struct overwrite or bool");
    if (i == 0)
    {
      require(box.info.info_uint.cur == UINT64_MAX && box.info.info_uint.max == UINT64_MAX, "uint64 struct field");
      printf("option %d %" PRIu64 "\n", i, box.info.info_uint.cur);
    }
    else if (i == 1)
    {
      require(box.info.info_int.cur == -17, "signed struct field");
      printf("option %d %" PRId64 "\n", i, box.info.info_int.cur);
    }
    else if (i == 2)
    {
      require(box.info.info_double.cur == 3.5, "double struct field");
      printf("option %d %.1f\n", i, box.info.info_double.cur);
    }
    else
    {
      require(box.info.info_bool.cur, "bool struct field");
      printf("option %d %d\n", i, box.info.info_bool.cur);
    }
  }
  DO(cvc5_delete(solver));
}

int main(int argc, char** argv)
{
  require(argc == 2, "expected mapping output stem");
  Cvc5TermManager* tm = V(cvc5_term_manager_new());
  scalar_outputs(tm); arrays(tm); symbols(tm);
  for (int mode = 0; mode < 3; ++mode) nested(tm, mode);
  bulk_sorts(tm); options(tm);
  save_maps(argv[1]);
  DO(cvc5_term_manager_delete(tm));
  puts("compound FFI passed");
}
