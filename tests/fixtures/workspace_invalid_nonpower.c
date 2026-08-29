#include "workspace_abi.h"

uint32_t bloom_primitive_workspace_abi_version(void) {
  return BLOOM_TEST_WORKSPACE_ABI_VERSION;
}

int32_t BLOOM_CALL bloom_primitive_workspace_required(
    const uint8_t *input, size_t input_size, size_t *required_size,
    size_t *required_alignment) {
  if (required_size == 0 || required_alignment == 0 ||
      (input == 0 && input_size != 0)) return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
  *required_size = BLOOM_TEST_WORKSPACE_REQUIRED;
  *required_alignment = 12;
  return BLOOM_TEST_WORKSPACE_OK;
}

int32_t BLOOM_CALL bloom_primitive_run_vbuf_workspace(
    const uint8_t *input, size_t input_size, uint8_t *workspace,
    size_t workspace_size, bloom_primitive_write_fn write, void *write_context) {
  (void)input; (void)input_size; (void)workspace; (void)workspace_size;
  (void)write; (void)write_context;
  return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
}
