#include "workspace_abi.h"

#include <stdint.h>

_Static_assert(sizeof(void *) == 8, "fixture requires 64-bit pointers");
_Static_assert(sizeof(size_t) == 8, "fixture requires 64-bit size_t");

uint32_t bloom_primitive_workspace_abi_version(void) {
  return BLOOM_TEST_WORKSPACE_ABI_VERSION;
}

static int32_t query(const uint8_t *input, size_t input_size,
                     size_t *required_size, size_t *required_alignment) {
  if (required_size == 0 || required_alignment == 0 ||
      (input == 0 && input_size != 0)) {
    return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
  }
  *required_size = 0;
  *required_alignment = 0;
  if (input_size == 0) {
    *required_alignment = BLOOM_TEST_WORKSPACE_ALIGNMENT;
    return BLOOM_TEST_WORKSPACE_OK;
  }
  /* A valid vBuf fixture whose first payload byte is not 1 is a
     capability-specific shape failure, not a Core validation failure. */
  if (input_size < 44 || input[0] != 'V' || input[32] != 1) {
    return BLOOM_TEST_WORKSPACE_UNSUPPORTED_SHAPE;
  }
  *required_size = BLOOM_TEST_WORKSPACE_REQUIRED;
  *required_alignment = BLOOM_TEST_WORKSPACE_ALIGNMENT;
  return BLOOM_TEST_WORKSPACE_OK;
}

int32_t bloom_primitive_workspace_required(const uint8_t *input, size_t input_size,
                                           size_t *required_size,
                                           size_t *required_alignment) {
  return query(input, input_size, required_size, required_alignment);
}

int32_t bloom_primitive_run_vbuf_workspace(
    const uint8_t *input, size_t input_size, uint8_t *workspace,
    size_t workspace_size, bloom_primitive_write_fn write, void *write_context) {
  size_t required_size = 0;
  size_t required_alignment = 0;
  int32_t status = query(input, input_size, &required_size, &required_alignment);
  if (status != BLOOM_TEST_WORKSPACE_OK) {
    return status;
  }
  if (workspace == 0 && workspace_size != 0) {
    return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
  }
  if (workspace_size < required_size) {
    return BLOOM_TEST_WORKSPACE_INSUFFICIENT;
  }
  if (required_size != 0 &&
      ((uintptr_t)workspace % required_alignment) != 0) {
    return BLOOM_TEST_WORKSPACE_MISALIGNED;
  }
  if (write == 0) {
    return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
  }
  for (size_t i = 0; i < required_size; ++i) {
    workspace[i] = (uint8_t)(i ^ 0xa5u);
  }
  for (size_t i = 0; i < required_size; ++i) {
    if (workspace[i] != (uint8_t)(i ^ 0xa5u)) {
      return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
    }
  }
  return write(write_context, input, input_size);
}
