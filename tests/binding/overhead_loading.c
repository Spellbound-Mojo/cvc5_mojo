/* Cold dynamic loading with the binding's extracted symbol list and version. */
#define _POSIX_C_SOURCE 200809L
#include "support.h"
#include <cvc5/c/cvc5_parser.h>
#include <dlfcn.h>
#include <inttypes.h>
#include <time.h>

static uint64_t now(void)
{
  struct timespec t;
  require(clock_gettime(CLOCK_MONOTONIC, &t) == 0, "clock failed");
  return (uint64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

int main(int argc, char **argv)
{
  require(argc == 6, "expected main/parser/symbols/version/mapping-stem");
  (void)check; (void)record;
  FILE *file = fopen(argv[3], "r");
  require(file != NULL, "symbol manifest missing");
  char names[1024][160];
  int owners[1024], count = 0;
  while (count < 1024 && fscanf(file, "%d %159s", &owners[count], names[count]) == 2) ++count;
  require(count > 0 && feof(file), "invalid symbol manifest");
  fclose(file);
  void *symbols[1024];
  uint64_t start = now();
  void *libs[] = {dlopen(argv[1], RTLD_NOW | RTLD_LOCAL), dlopen(argv[2], RTLD_NOW | RTLD_LOCAL)};
  require(libs[0] && libs[1], "dlopen failed");
  for (int i = 0; i < count; ++i)
  {
    require(owners[i] == 0 || owners[i] == 1, "invalid library selector");
    symbols[i] = dlsym(libs[owners[i]], names[i]);
    require(symbols[i] != NULL, names[i]);
  }
  /* Lifecycle names/types come from the included pinned C header. The symbol
     list above covers every lookup, including those unused by the fixture. */
#define FN(name) __typeof__(&name) p_##name = (__typeof__(&name))dlsym(libs[0], #name)
  FN(cvc5_term_manager_new); FN(cvc5_term_manager_delete); FN(cvc5_new);
  FN(cvc5_delete); FN(cvc5_get_version); FN(cvc5_has_error);
#define OK() require(!p_cvc5_has_error(), "native initialization error")
  Cvc5TermManager *tm = p_cvc5_term_manager_new(); OK();
  Cvc5 *solver = p_cvc5_new(tm); OK();
  const char *version = p_cvc5_get_version(solver); OK();
  char *owned = strdup(version);
  require(owned != NULL, "version allocation failed");
  p_cvc5_delete(solver); OK(); p_cvc5_term_manager_delete(tm); OK();
  require(strcmp(owned, argv[4]) == 0, "version mismatch");
  free(owned);
  uint64_t elapsed = now() - start;
  /* Consume the lookup results after timing; reject any optimized-away work. */
  for (int i = 0; i < count; ++i) require(symbols[i] != NULL, "missing symbol");
  save_maps(argv[5]);
  printf("-1 1 %" PRIu64 " 1 0\noverhead passed\n", elapsed);
  dlclose(libs[1]); dlclose(libs[0]);
}
