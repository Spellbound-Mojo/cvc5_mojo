/* Test-only adapters: real native exports, invalid UTF-8 or getter errors, and
 * per-address reference accounting. Loaded explicitly by test_return_conversion;
 * production library lookup and generated bindings are not modified for tests.
 */
#include <cvc5/c/cvc5.h>
#include <cvc5/c/cvc5_parser.h>
#include <assert.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum { NAMED = 1, OPTIONS, STAT_NAME, HISTOGRAM, STAT_STRING, OPTION_INFO, CHILD,
       STAT_ITER_NAME, STATS_HISTOGRAM, STATS_STRING };
static int mode, position, seen, fired, errors, exports, copies, releases;
static const char invalid[] = "\xff";
static const char** strings;
static size_t extent;
static struct reference { const void* ptr; int count; } *refs;
static size_t num_refs, ref_capacity;
static void *main_library, *parser_library;

void fault_libraries(const char* main_path, const char* parser_path)
{
  /* Open the exact files used by CApi, without a second SONAME copy. */
  main_library = dlopen(main_path, RTLD_NOW | RTLD_LOCAL);
  parser_library = dlopen(parser_path, RTLD_NOW | RTLD_LOCAL);
  assert(main_library && parser_library);
}

__attribute__((destructor)) static void close_libraries(void)
{
  free(refs);
  if (parser_library) dlclose(parser_library);
  if (main_library) dlclose(main_library);
}

static void* real_symbol(const char* name)
{
  void* result = dlsym(strcmp(name, "cvc5_sm_get_named_terms") == 0
                          ? parser_library : main_library, name);
  assert(result);
  return result;
}
#define REAL(name) ((__typeof__(&name))real_symbol(#name))

static void receipt(const void* ptr, int copy)
{
  if (!mode) return;
  assert(ptr);
  size_t i = 0;
  while (i < num_refs && refs[i].ptr != ptr) ++i;
  if (i == num_refs)
  {
    /* ASan quarantine prevents the address reuse seen with the production
     * allocator. Preserve every address for duplicate-release detection
     * without imposing an arbitrary limit on the number of native exports. */
    if (num_refs == ref_capacity)
    {
      size_t next = ref_capacity ? ref_capacity * 2 : 256;
      assert(next > ref_capacity && next <= SIZE_MAX / sizeof(*refs));
      struct reference* grown = realloc(refs, next * sizeof(*refs));
      assert(grown);
      refs = grown;
      ref_capacity = next;
    }
    refs[num_refs++] = (struct reference){ptr, 0};
  }
  ++refs[i].count;
  if (copy) ++copies; else ++exports;
}

static void release(const void* ptr)
{
  if (!mode) return;
  for (size_t i = 0; i < num_refs; ++i)
    if (refs[i].ptr == ptr)
    {
      if (refs[i].count <= 0) ++errors;
      --refs[i].count;
      ++releases;
      return;
    }
  ++errors;
}

void fault_begin(int selected, int index)
{
  assert(!mode);
  mode = selected;
  position = index;
  seen = fired = errors = exports = copies = releases = 0;
  extent = num_refs = 0;
}

/* Metrics are available after fault_end, so failures remain reviewable. */
int fault_metric(int which)
{
  if (which == 0) return fired;
  if (which == 1) return exports;
  if (which == 2) return copies;
  if (which == 3) return releases;
  if (which == 4) return (int)extent;
  if (which == 5) return errors;
  int outstanding = 0;
  for (size_t i = 0; i < num_refs; ++i) outstanding += refs[i].count;
  return outstanding;
}

void fault_end(void)
{
  assert(mode);
  mode = 0;
  free(strings);
  strings = NULL;
}

static const char** corrupt(const char** original, size_t count)
{
  extent = count;
  if (position < 0) return original; /* successful conversion control */
  assert((size_t)position < count);
  free(strings);
  strings = malloc(count * sizeof(*strings));
  assert(strings);
  memcpy(strings, original, count * sizeof(*strings));
  strings[position] = invalid;
  ++fired;
  return strings;
}

void test_cvc5_sm_get_named_terms(Cvc5SymbolManager* sm, size_t* size,
                                Cvc5Term** terms, const char*** names)
{
  REAL(cvc5_sm_get_named_terms)(sm, size, terms, names);
  for (size_t i = 0; i < *size; ++i) receipt((*terms)[i], 0);
  if (mode == NAMED) *names = corrupt(*names, *size);
}

Cvc5Term test_cvc5_term_copy(Cvc5Term term)
{
  Cvc5Term result = REAL(cvc5_term_copy)(term);
  receipt(result, 1);
  return result;
}

Cvc5Term test_cvc5_term_get_child(Cvc5Term term, size_t index)
{
  if (mode == CHILD && seen++ == position)
  {
    ++fired;
    /* Exercise the real native error path, before this child is exported. */
    return REAL(cvc5_term_get_child)(term, SIZE_MAX);
  }
  Cvc5Term result = REAL(cvc5_term_get_child)(term, index);
  receipt(result, 0);
  return result;
}

void test_cvc5_term_release(Cvc5Term term)
{
  release(term);
  REAL(cvc5_term_release)(term);
}

const char** test_cvc5_get_option_names(Cvc5* solver, size_t* size)
{
  const char** result = REAL(cvc5_get_option_names)(solver, size);
  return mode == OPTIONS ? corrupt(result, *size) : result;
}

Cvc5Stat test_cvc5_stats_get(Cvc5Statistics stats, const char* name)
{
  Cvc5Stat result = REAL(cvc5_stats_get)(stats, name);
  receipt(result, 0);
  return result;
}

Cvc5Stat test_cvc5_stats_iter_next(Cvc5Statistics stats, const char** name)
{
  Cvc5Stat result = REAL(cvc5_stats_iter_next)(stats, name);
  receipt(result, 0);
  if ((mode == STAT_NAME || mode == STAT_ITER_NAME) && seen++ == position)
  {
    *name = invalid;
    ++fired;
  }
  return result;
}

Cvc5Stat test_cvc5_stat_copy(Cvc5Stat stat)
{
  Cvc5Stat result = REAL(cvc5_stat_copy)(stat);
  receipt(result, 1);
  return result;
}

void test_cvc5_stat_release(Cvc5Stat stat)
{
  release(stat);
  REAL(cvc5_stat_release)(stat);
}

void test_cvc5_stat_get_histogram(Cvc5Stat stat, const char*** keys,
                                uint64_t** values, size_t* size)
{
  REAL(cvc5_stat_get_histogram)(stat, keys, values, size);
  if (mode == HISTOGRAM) *keys = corrupt(*keys, *size);
  /* The first nonempty histogram can fail after earlier dictionary entries. */
  if (mode == STATS_HISTOGRAM && !fired && *size)
    *keys = corrupt(*keys, *size);
}

const char* test_cvc5_stat_get_string(Cvc5Stat stat)
{
  const char* result = REAL(cvc5_stat_get_string)(stat);
  if ((mode == STAT_STRING && position == 0)
      || (mode == STATS_STRING && seen++ == position))
  {
    ++fired;
    return invalid;
  }
  return result;
}

void test_cvc5_get_option_info(Cvc5* solver, const char* name, Cvc5OptionInfo* info)
{
  REAL(cvc5_get_option_info)(solver, name, info);
  if (mode == OPTION_INFO)
    info->info_mode.modes = corrupt(info->info_mode.modes, info->info_mode.num_modes);
}
