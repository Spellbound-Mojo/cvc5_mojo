/* Shared native test support: checked calls, tracing, and loaded mappings. */
#ifndef CVC5_MOJO_TEST_SUPPORT_H
#define CVC5_MOJO_TEST_SUPPORT_H
#include <cvc5/c/cvc5.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static FILE *trace;
static void require(int condition, const char *message)
{
  if (!condition) { fprintf(stderr, "%s\n", message); exit(1); }
}
static void record(const char *expression)
{
  if (trace) fprintf(trace, "%.*s\n", (int)strcspn(expression, "("), expression);
}
static void check(void)
{
  if (cvc5_has_error())
  {
    fprintf(stderr, "cvc5: %s\n", cvc5_get_error_message());
    cvc5_reset_error();
    exit(1);
  }
}
/* Both value and void calls check errors, like the raw Mojo layer. */
#define V(expr) ({ record(#expr); __auto_type value_ = (expr); check(); value_; })
#define DO(expr) do { record(#expr); (expr); check(); } while (0)

static void save_maps(const char *path)
{
  char *name = malloc(strlen(path) + 6);
  require(name != NULL, "allocation failed");
  sprintf(name, "%s.maps", path);
  FILE *in = fopen("/proc/self/maps", "r"), *out = fopen(name, "w");
  require(in && out, "open maps failed");
  char bytes[4096];
  size_t n;
  while ((n = fread(bytes, 1, sizeof(bytes), in)))
    require(fwrite(bytes, 1, n, out) == n, "write maps failed");
  require(!ferror(in), "read maps failed");
  fclose(in);
  require(fclose(out) == 0, "close maps failed");
  free(name);
}

#endif
