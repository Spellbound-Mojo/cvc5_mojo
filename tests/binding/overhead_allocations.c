/* Linux/glibc diagnostic only. Never preload this library for timing runs.
   Counts interposed libc requests, not live bytes, leaks, or every allocator. */
#include <stdint.h>
#include <stddef.h>

extern void *__libc_malloc(size_t);
extern void *__libc_calloc(size_t, size_t);
extern void *__libc_realloc(void *, size_t);
extern void __libc_free(void *);
extern void *__libc_memalign(size_t, size_t);

static _Thread_local int enabled;
static _Thread_local uint64_t counts[6];

void overhead_begin(void)
{
  for (int i = 0; i < 6; ++i) counts[i] = 0;
  enabled = 1;
}
void overhead_end(void) { enabled = 0; }
uint64_t overhead_metric(int i) { return i >= 0 && i < 6 ? counts[i] : UINT64_MAX; }

void *malloc(size_t n)
{
  if (enabled) { ++counts[0]; counts[5] += n; }
  return __libc_malloc(n);
}
void *calloc(size_t n, size_t size)
{
  if (enabled) { ++counts[1]; counts[5] += n * size; }
  return __libc_calloc(n, size);
}
void *realloc(void *p, size_t n)
{
  if (enabled) { ++counts[2]; counts[5] += n; }
  return __libc_realloc(p, n);
}
void free(void *p)
{
  if (enabled && p) ++counts[3];
  __libc_free(p);
}
void *aligned_alloc(size_t alignment, size_t n)
{
  if (enabled) { ++counts[4]; counts[5] += n; }
  return __libc_memalign(alignment, n);
}
/* Exercise the actual interposed entry points; -fno-builtin prevents elision. */
int overhead_sensitivity(void)
{
  overhead_begin();
  void *a = malloc(17), *b = calloc(2, 7);
  a = realloc(a, 31);
  free(a); free(b);
  overhead_end();
  return counts[0] == 1 && counts[1] == 1 && counts[2] == 1
         && counts[3] == 2 && counts[4] == 0 && counts[5] == 62;
}
