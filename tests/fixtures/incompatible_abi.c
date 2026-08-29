#include "bloom/primitive_abi.h"

uint32_t bloom_primitive_abi_version(void) { return 0x00020000u; }
int32_t bloom_primitive_run_vbuf(const uint8_t *input, size_t input_size,
                                 bloom_primitive_write_fn write, void *context) {
  return write(context, input, input_size);
}
