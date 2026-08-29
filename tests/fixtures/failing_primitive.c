#include "bloom/primitive_abi.h"

uint32_t bloom_primitive_abi_version(void) { return BLOOM_PRIMITIVE_ABI_VERSION; }
int32_t bloom_primitive_run_vbuf(const uint8_t *input, size_t input_size,
                                 bloom_primitive_write_fn write, void *context) {
  (void)input;
  (void)input_size;
  (void)write;
  (void)context;
  return 42;
}
