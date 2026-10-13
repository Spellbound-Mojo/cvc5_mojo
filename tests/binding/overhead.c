/* Independent steady-state controls. No solving in the measured region. */
#define _POSIX_C_SOURCE 200809L
#include "support.h"
#include <inttypes.h>
#include <time.h>
#ifdef ALLOCATION_PROBE
#include <dlfcn.h>
#endif

/* Compile separate bare/checked binaries: no per-call mode dispatch. */
#ifdef BARE
#undef V
#undef DO
#define V(expr) (expr)
#define DO(expr) (expr)
#elif !defined(TRACE_PROBE)
/* Timing/profiling controls have no conditional trace branch per call. */
#undef V
#undef DO
#define V(expr) ({ __auto_type value_ = (expr); check(); value_; })
#define DO(expr) do { (expr); check(); } while (0)
#endif

static uint64_t now(void)
{
  struct timespec t;
  require(clock_gettime(CLOCK_MONOTONIC, &t) == 0, "clock failed");
  return (uint64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

static const char *decimal = "115792089237316195423570985008687907853269984665640564039457584007913129639935";
typedef struct {
  Cvc5TermManager *tm;
  Cvc5 *solver;
  Cvc5Term integer, expression, inputs[8];
} Fixture;

static inline __attribute__((always_inline)) uint64_t step(Fixture *f, int mode)
{
  if (mode == 0) return V(cvc5_term_get_num_children(f->expression));
  if (mode == 1)
  {
    Cvc5Term copied = V(cvc5_term_copy(f->expression));
    uint64_t n = V(cvc5_term_get_num_children(copied));
    DO(cvc5_term_release(copied));
    return n;
  }
  if ((mode >= 2 && mode <= 4) || mode == 12)
  {
    Cvc5Term t;
    if (mode == 2 || mode == 3) t = V(cvc5_mk_integer_int64(f->tm, 42));
    else
    {
      /* Owned transient input buffer, as in the public string argument. */
      char *text = strdup(decimal);
      require(text != NULL, "allocation failed");
      t = V(cvc5_mk_integer(f->tm, text));
      free(text);
    }
    uint64_t result = V(cvc5_term_is_integer_value(t));
    DO(cvc5_term_release(t));
    return result;
  }
  if (mode >= 5 && mode <= 7)
  {
    size_t n = mode == 5 ? 2 : 8;
    Cvc5Term *args = malloc(n * sizeof(*args));
    require(args != NULL, "allocation failed");
    memcpy(args, f->inputs, n * sizeof(*args));
    Cvc5Term t = V(cvc5_mk_term(f->tm, CVC5_KIND_ADD, n, args));
    free(args);
    uint64_t result = V(cvc5_term_get_num_children(t));
    DO(cvc5_term_release(t));
    return result;
  }
  if (mode == 8)
  {
    Cvc5Term *args = malloc(sizeof(f->inputs));
    require(args != NULL, "allocation failed");
    memcpy(args, f->inputs, sizeof(f->inputs));
    size_t n = 0;
    const Cvc5Term *native = V(cvc5_get_values(f->solver, 8, args, &n));
    free(args);
    require(n == 8, "wrong returned size");
    Cvc5Term *owned = malloc(n * sizeof(*owned));
    require(owned != NULL, "allocation failed");
    memcpy(owned, native, n * sizeof(*owned));
    uint64_t result = n;
    for (size_t i = 0; i < n; ++i)
    {
      result += V(cvc5_term_is_integer_value(owned[i]));
      DO(cvc5_term_release(owned[i]));
    }
    free(owned);
    return result;
  }
  if (mode == 9 || mode == 10 || mode == 11)
  {
    /* An owned, validated ASCII/UTF-8 result, retained past the native call. */
    const char *native = mode == 10 ? V(cvc5_term_get_integer_value(f->integer))
                                   : V(cvc5_term_to_string(f->integer));
    char *owned = strdup(native);
    require(owned != NULL, "allocation failed");
    uint64_t sum = 0;
    for (const unsigned char *p = (const unsigned char *)owned; *p; ++p)
    {
      require(*p >= '0' && *p <= '9', "non-decimal output");
      sum += *p;
    }
    free(owned);
    return sum;
  }
  if (mode == 13 || mode == 14)
  {
    size_t n;
    const Cvc5Term *native = NULL;
    if (mode == 13) n = V(cvc5_term_get_num_children(f->expression));
    else native = V(cvc5_get_assertions(f->solver, &n));
    require(n == (mode == 13 ? 8u : 32u), "wrong collection size");
    Cvc5Term *owned = malloc(n * sizeof(*owned));
    require(owned != NULL, "allocation failed");
    for (size_t i = 0; i < n; ++i)
      owned[i] = mode == 13 ? V(cvc5_term_get_child(f->expression, i)) : native[i];
    uint64_t result = n;
    for (size_t i = 0; i < n; ++i)
    {
      result += mode == 13 ? V(cvc5_term_is_integer_value(owned[i]))
                           : V(cvc5_term_has_symbol(owned[i]));
      DO(cvc5_term_release(owned[i]));
    }
    free(owned);
    return result;
  }
  if (mode == 15)
  {
    size_t n = 0;
    const char **native = V(cvc5_get_option_names(f->solver, &n));
    require(n > 0, "no option names");
    char **owned = malloc(n * sizeof(*owned));
    require(owned != NULL, "allocation failed");
    for (size_t i = 0; i < n; ++i)
    {
      owned[i] = strdup(native[i]);
      require(owned[i] != NULL, "allocation failed");
      for (const unsigned char *p = (const unsigned char *)owned[i]; *p; ++p)
        require(*p < 128, "non-ASCII option name needs a UTF-8 control");
    }
    uint64_t found = 0;
    for (size_t i = 0; i < n; ++i)
    {
      found |= strcmp(owned[i], "produce-models") == 0;
      free(owned[i]);
    }
    free(owned);
    return found;
  }
  if (mode == 16 || mode == 24 || mode == 19 || mode == 20 || mode == 23)
  {
    Cvc5Term t;
    if (mode == 16) t = V(cvc5_mk_integer_int64(f->tm, 42));
    else if (mode == 24)
    {
      char *text = strdup(decimal);
      require(text != NULL, "allocation failed");
      t = V(cvc5_mk_integer(f->tm, text));
      free(text);
    }
    else if (mode == 23) t = V(cvc5_mk_bv_uint64(f->tm, 64, UINT64_MAX));
    else t = V(cvc5_mk_real_num_den(f->tm, 3, 7));
    uint64_t result;
    if (mode == 16 || mode == 24) result = V(cvc5_term_is_integer_value(t));
    else if (mode == 23) result = V(cvc5_term_is_bv_value(t));
    else result = V(cvc5_term_is_real_value(t));
    DO(cvc5_term_release(t));
    return result;
  }
  if (mode == 17 || mode == 18)
  {
    if (V(cvc5_term_is_int64_value(f->integer)))
      return V(cvc5_term_get_int64_value(f->integer)) == 42;
    if (V(cvc5_term_is_uint64_value(f->integer)))
      return V(cvc5_term_get_uint64_value(f->integer)) == 42;
    char *owned = strdup(V(cvc5_term_get_integer_value(f->integer)));
    require(owned != NULL, "allocation failed");
    uint64_t result = strcmp(owned, decimal) == 0;
    free(owned);
    return result;
  }
  if (mode == 21 || mode == 22)
  {
    if (V(cvc5_term_is_real64_value(f->integer)))
    {
      int64_t num = 0;
      uint64_t den = 0;
      DO(cvc5_term_get_real64_value(f->integer, &num, &den));
      return num == 3 && den == 7;
    }
    char *owned = strdup(V(cvc5_term_get_real_value(f->integer)));
    require(owned != NULL, "allocation failed");
    uint64_t result = strncmp(owned, decimal, strlen(decimal)) == 0
        && strcmp(owned + strlen(decimal), "/7") == 0;
    free(owned);
    return result;
  }
  require(0, "unknown workload");
  return 0;
}

/* Keep one operation implementation, specialized into independent timing loops.
 * The mode is a compile-time constant after mandatory inlining of step(). */
#define WORKLOADS(M) \
  M(0) M(1) M(2) M(3) M(4) M(5) M(6) M(7) \
  M(8) M(9) M(10) M(11) M(12) M(13) M(14) M(15) \
  M(16) M(17) M(18) M(19) M(20) M(21) M(22) M(23) M(24)

typedef struct {
  void (*end)(void);
  uint64_t (*metric)(int);
} AllocationProbe;

static void probe_begin(AllocationProbe *probe)
{
  (void)probe;
#ifdef ALLOCATION_PROBE
  void (*begin)(void) = dlsym(RTLD_DEFAULT, "overhead_begin");
  probe->end = dlsym(RTLD_DEFAULT, "overhead_end");
  probe->metric = dlsym(RTLD_DEFAULT, "overhead_metric");
  int (*sensitivity)(void) = dlsym(RTLD_DEFAULT, "overhead_sensitivity");
  require(begin && probe->end && probe->metric && sensitivity && sensitivity(),
          "allocation probe sensitivity failed");
  begin();
#endif
}

static void probe_end(AllocationProbe *probe)
{
  (void)probe;
#ifdef ALLOCATION_PROBE
  probe->end();
#endif
}

typedef struct {
  uint64_t warmed, checksum, elapsed;
} Measurement;

#define EXECUTE(n) \
  static __attribute__((noinline, used)) Measurement execute_##n( \
      Fixture *f, uint64_t count, uint64_t warmup, AllocationProbe *probe) \
  { \
    Measurement measured = {0}; \
    for (uint64_t i = 0; i < warmup; ++i) measured.warmed += step(f, n); \
    probe_begin(probe); \
    uint64_t before = now(); \
    for (uint64_t i = 0; i < count; ++i) measured.checksum += step(f, n); \
    measured.elapsed = now() - before; \
    probe_end(probe); \
    return measured; \
  }
WORKLOADS(EXECUTE)
#undef EXECUTE

int main(int argc, char **argv)
{
  (void)record;
  require(argc == 5, "expected mode/count/warmup/mapping-stem");
  int mode = atoi(argv[1]);
  uint64_t count = strtoull(argv[2], NULL, 10), warmup = strtoull(argv[3], NULL, 10);
  require(mode >= 0 && mode <= 24 && count > 0, "invalid workload/count");
  const char *trace_path = getenv("CVC5_BINDING_TRACE");
  if (trace_path) { trace = fopen(trace_path, "w"); require(trace != NULL, "trace open failed"); }
  Fixture f;
  f.tm = V(cvc5_term_manager_new());
  f.solver = V(cvc5_new(f.tm));
  DO(cvc5_set_logic(f.solver, "QF_LIA"));
  DO(cvc5_set_option(f.solver, "produce-models", "true"));
  for (size_t i = 0; i < 8; ++i) f.inputs[i] = V(cvc5_mk_integer_int64(f.tm, (int64_t)i));
  if (mode == 16 || mode == 17) f.integer = V(cvc5_mk_integer_int64(f.tm, 42));
  else if (mode == 21) f.integer = V(cvc5_mk_real(f.tm, "3/7"));
  else if (mode == 22)
  {
    char text[128];
    require(snprintf(text, sizeof(text), "%s/7", decimal) < (int)sizeof(text), "buffer too small");
    f.integer = V(cvc5_mk_real(f.tm, text));
  }
  else f.integer = V(cvc5_mk_integer(f.tm, decimal));
  f.expression = V(cvc5_mk_term(f.tm, CVC5_KIND_ADD, 8, f.inputs));
  if (mode == 14)
  {
    Cvc5Sort boolean = V(cvc5_get_boolean_sort(f.tm));
    for (size_t i = 0; i < 32; ++i)
    {
      char name[32];
      snprintf(name, sizeof(name), "assertion_%zu", i);
      Cvc5Term assertion = V(cvc5_mk_const(f.tm, boolean, name));
      DO(cvc5_assert_formula(f.solver, assertion));
      DO(cvc5_term_release(assertion));
    }
    DO(cvc5_sort_release(boolean));
  }
  Cvc5Result result = V(cvc5_check_sat(f.solver));
  require(V(cvc5_result_is_sat(result)), "setup not sat");
  DO(cvc5_result_release(result));
  AllocationProbe probe = {0};
  Measurement measured = {0};
  switch (mode)
  {
#define DISPATCH(n) case n: measured = execute_##n(&f, count, warmup, &probe); break;
    WORKLOADS(DISPATCH)
#undef DISPATCH
  }
  DO(cvc5_term_release(f.expression)); DO(cvc5_term_release(f.integer));
  for (size_t i = 0; i < 8; ++i) DO(cvc5_term_release(f.inputs[i]));
  DO(cvc5_delete(f.solver)); DO(cvc5_term_manager_delete(f.tm));
  check();
  save_maps(argv[4]);
  if (trace) require(fclose(trace) == 0, "trace close failed");
  printf("%d %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\noverhead passed\n",
         mode, count, measured.elapsed, measured.checksum, measured.warmed);
#ifdef ALLOCATION_PROBE
  printf("allocations");
  for (int i = 0; i < 6; ++i) printf(" %" PRIu64, probe.metric(i));
  puts("");
#endif
}
