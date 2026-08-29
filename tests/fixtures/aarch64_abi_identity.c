#include "bloom/primitive_abi.h"

_Static_assert(sizeof(void *) == 8, "validated AArch64 target must use 64-bit pointers");
_Static_assert(sizeof(size_t) == 8, "validated AArch64 target must use 64-bit size_t");

uint32_t bloom_primitive_abi_version(void) {
  return BLOOM_PRIMITIVE_ABI_VERSION;
}

int32_t bloom_primitive_run_vbuf(const uint8_t *input, size_t input_size,
                                 bloom_primitive_write_fn write,
                                 void *write_context) {
  if (write == 0 || (input == 0 && input_size != 0)) {
    return 1;
  }
  return write(write_context, input, input_size);
}
