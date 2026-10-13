/* Test-only DSO lifetime markers. Writes finish before a Mojo checkpoint. */
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void event(const char* text)
{
  const char* path = getenv("CVC5_MOJO_TEST_EVENTS");
  if (!path) abort();
  int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0600);
  if (fd < 0) abort();
  size_t n = strlen(text);
  if (write(fd, text, n) != (ssize_t)n || close(fd)) abort();
}

__attribute__((constructor)) static void loaded(void) { event("open " TAG "\n"); }
__attribute__((destructor)) static void unloaded(void) { event("close " TAG "\n"); }
