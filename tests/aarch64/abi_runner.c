#define _GNU_SOURCE
#include "bloom/primitive_abi.h"

#include <dlfcn.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

_Static_assert(sizeof(void *) == 8, "AArch64 runner requires 64-bit pointers");
_Static_assert(sizeof(size_t) == 8, "AArch64 runner requires 64-bit size_t");

typedef uint32_t(BLOOM_CALL *version_fn)(void);
typedef int32_t(BLOOM_CALL *run_fn)(const uint8_t *, size_t,
                                    bloom_primitive_write_fn, void *);

static int32_t BLOOM_CALL write_output(void *context, const uint8_t *data,
                                       size_t size) {
  FILE *output = context;
  return fwrite(data, 1, size, output) == size ? 0 : -1;
}

int main(int argc, char **argv) {
  if (argc != 4) {
    fprintf(stderr, "usage: abi_runner ARTIFACT INPUT OUTPUT\n");
    return 2;
  }
  FILE *input = fopen(argv[2], "rb");
  FILE *output = fopen(argv[3], "wb");
  if (input == NULL || output == NULL || fseek(input, 0, SEEK_END) != 0) {
    return 3;
  }
  long length = ftell(input);
  if (length < 0 || fseek(input, 0, SEEK_SET) != 0) {
    return 3;
  }
  size_t size = (size_t)length;
  uint8_t *bytes = size == 0 ? NULL : malloc(size);
  if ((size != 0 && bytes == NULL) || fread(bytes, 1, size, input) != size) {
    return 3;
  }

  int artifact_fd = open(argv[1], O_RDONLY | O_CLOEXEC);
  char load_path[64];
  if (artifact_fd < 0 || snprintf(load_path, sizeof(load_path), "/proc/%ld/fd/%d",
                                  (long)getpid(), artifact_fd) <= 0) {
    return 4;
  }
  void *library = dlopen(load_path, RTLD_NOW | RTLD_LOCAL);
  if (library == NULL) {
    fprintf(stderr, "dlopen: %s\n", dlerror());
    return 4;
  }
  version_fn version = (version_fn)dlsym(library, "bloom_primitive_abi_version");
  run_fn run = (run_fn)dlsym(library, "bloom_primitive_run_vbuf");
  if (version == NULL || run == NULL) {
    return 5;
  }
  if (version() != BLOOM_PRIMITIVE_ABI_VERSION) {
    return 6;
  }
  int32_t status = run(bytes, size, write_output, output);
  if (fclose(output) != 0 || status != 0) {
    return 7;
  }
  free(bytes);
  dlclose(library);
  close(artifact_fd);
  fclose(input);
  return 0;
}
