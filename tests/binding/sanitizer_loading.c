/* Minimal native-only shutdown diagnostic. No cvc5 API calls or Mojo. */
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv)
{
  assert(argc > 1);
  void** libraries = calloc((size_t)argc - 1, sizeof(void*));
  assert(libraries);
  for (int i = 1; i < argc; ++i)
  {
    libraries[i - 1] = dlopen(argv[i], RTLD_NOW | RTLD_LOCAL);
    assert(libraries[i - 1]);
  }
  for (int i = argc - 1; i > 0; --i) assert(dlclose(libraries[i - 1]) == 0);
  free(libraries);
  puts("native libraries unloaded");
  fflush(stdout);
}
