#include "workspace_abi.h"

uint32_t bloom_primitive_workspace_abi_version(void) { return 0x00020000u; }

int32_t BLOOM_CALL bloom_primitive_workspace_required(
    const uint8_t *input, size_t input_size, size_t *required_size,
    size_t *required_alignment) {
  (void)input; (void)input_size; (void)required_size; (void)required_alignment;
  return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
}

int32_t BLOOM_CALL bloom_primitive_run_vbuf_workspace(
    const uint8_t *input, size_t input_size, uint8_t *workspace,
    size_t workspace_size, bloom_primitive_write_fn write, void *write_context) {
  (void)input; (void)input_size; (void)workspace; (void)workspace_size;
  (void)write; (void)write_context;
  return BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT;
}
