/* A deliberately leaked allocation in an uninstrumented DSO. */
#include <stdlib.h>
#include <stdio.h>

__attribute__((noinline)) void native_leak(void)
{
  void* p = malloc(37);
  printf("native allocation %p\n", p);
}
