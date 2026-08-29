#include "bloom/primitive_abi.h"

#include <stdlib.h>

uint32_t bloom_primitive_abi_version(void) {
  return BLOOM_PRIMITIVE_ABI_VERSION;
}

int32_t bloom_primitive_run_vbuf(const uint8_t *input, size_t input_size,
                                 bloom_primitive_write_fn write,
                                 void *write_context) {
  /* Deliberately creates a libc dependency for admission rejection testing. */
  if (getenv("BLOOM_TEST_DEPENDENCY") != 0) {
    return 9;
  }
  return write(write_context, input, input_size);
}
