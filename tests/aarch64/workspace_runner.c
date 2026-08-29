#define _GNU_SOURCE
#include "../fixtures/workspace_abi.h"

#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(void *) == 8, "AArch64 runner requires 64-bit pointers");
_Static_assert(sizeof(size_t) == 8, "AArch64 runner requires 64-bit size_t");

typedef uint32_t(BLOOM_CALL *version_fn)(void);
typedef int32_t(BLOOM_CALL *query_fn)(const uint8_t *, size_t, size_t *, size_t *);
typedef int32_t(BLOOM_CALL *run_fn)(const uint8_t *, size_t, uint8_t *, size_t,
                                    bloom_primitive_write_fn, void *);

typedef struct {
  const uint8_t *expected;
  size_t expected_size;
  int fail;
} callback_state;

static int32_t BLOOM_CALL check_output(void *context, const uint8_t *data,
                                       size_t size) {
  callback_state *state = context;
  if (size != state->expected_size ||
      (size != 0 && memcmp(data, state->expected, size) != 0)) {
    state->fail = 1;
    return -1;
  }
  return 0;
}

static int32_t BLOOM_CALL fail_output(void *context, const uint8_t *data,
                                      size_t size) {
  (void)context; (void)data; (void)size;
  return -1;
}

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  FILE *file = fopen(argv[2], "rb");
  if (file == NULL || fseek(file, 0, SEEK_END) != 0) return 3;
  long length = ftell(file);
  if (length < 0 || fseek(file, 0, SEEK_SET) != 0) return 3;
  size_t input_size = (size_t)length;
  uint8_t *input = input_size == 0 ? NULL : malloc(input_size);
  if ((input_size != 0 && input == NULL) || fread(input, 1, input_size, file) != input_size) return 3;

  void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (library == NULL) return 4;
  void *version_symbol = dlsym(library, "bloom_primitive_workspace_abi_version");
  void *query_symbol = dlsym(library, "bloom_primitive_workspace_required");
  void *run_symbol = dlsym(library, "bloom_primitive_run_vbuf_workspace");
  version_fn version = NULL;
  query_fn query = NULL;
  run_fn run = NULL;
  _Static_assert(sizeof(version) == sizeof(version_symbol),
                 "POSIX dlsym function pointers must have equal size");
  memcpy(&version, &version_symbol, sizeof(version));
  memcpy(&query, &query_symbol, sizeof(query));
  memcpy(&run, &run_symbol, sizeof(run));
  if (version == NULL || query == NULL || run == NULL ||
      version() != BLOOM_TEST_WORKSPACE_ABI_VERSION) return 5;

  size_t required = 0, alignment = 0;
  if (query(input, input_size, &required, &alignment) != 0 ||
      required != BLOOM_TEST_WORKSPACE_REQUIRED ||
      alignment != BLOOM_TEST_WORKSPACE_ALIGNMENT) return 6;
  size_t required_again = 0, alignment_again = 0;
  if (query(input, input_size, &required_again, &alignment_again) != 0 ||
      required != required_again || alignment != alignment_again) return 7;

  uint8_t bad_shape[44];
  if (input_size != sizeof(bad_shape)) return 8;
  memcpy(bad_shape, input, sizeof(bad_shape));
  bad_shape[32] = 2;
  size_t ignored_size = 99, ignored_alignment = 99;
  if (query(bad_shape, sizeof(bad_shape), &ignored_size, &ignored_alignment) !=
      BLOOM_TEST_WORKSPACE_UNSUPPORTED_SHAPE || ignored_size != 0 || ignored_alignment != 0) return 9;

  _Alignas(8) uint8_t workspace[BLOOM_TEST_WORKSPACE_REQUIRED + 8];
  callback_state state = {input, input_size, 0};
  if (run(input, input_size, workspace, required, check_output, &state) != 0 || state.fail) return 10;
  if (run(input, input_size, workspace, required + 1, check_output, &state) != 0) return 11;
  if (run(input, input_size, workspace, required - 1, check_output, &state) != BLOOM_TEST_WORKSPACE_INSUFFICIENT) return 12;
  if (run(input, input_size, workspace + 1, required, check_output, &state) != BLOOM_TEST_WORKSPACE_MISALIGNED) return 13;
  if (run(input, input_size, workspace, required, fail_output, NULL) != -1) return 14;
  if (run(input, input_size, workspace, required, check_output, &state) != 0) return 15;

  size_t zero_size = 99, zero_alignment = 99;
  callback_state zero_state = {NULL, 0, 0};
  if (query(NULL, 0, &zero_size, &zero_alignment) != 0 || zero_size != 0 || zero_alignment != 8 ||
      run(NULL, 0, NULL, 0, check_output, &zero_state) != 0) return 16;
  dlclose(library);
  fclose(file);
  free(input);
  return 0;
}
