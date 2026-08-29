#include "bloom/primitive_abi.h"

#define ARGMIN_INVALID_ARGUMENT 1
#define ARGMIN_EMPTY_INPUT 2
#define ARGMIN_CONTRACT_MISMATCH 3

static uint16_t read_u16_le(const uint8_t *data) {
  return (uint16_t)data[0] | ((uint16_t)data[1] << 8);
}

static uint32_t read_u32_le(const uint8_t *data) {
  return (uint32_t)data[0] | ((uint32_t)data[1] << 8) |
         ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
}

static uint64_t read_u64_le(const uint8_t *data) {
  uint64_t value = 0;
  for (uint32_t index = 0; index < 8; ++index) {
    value |= (uint64_t)data[index] << (index * 8);
  }
  return value;
}

static void write_u16_le(uint8_t *data, uint16_t value) {
  data[0] = (uint8_t)value;
  data[1] = (uint8_t)(value >> 8);
}

static void write_u32_le(uint8_t *data, uint32_t value) {
  for (uint32_t index = 0; index < 4; ++index) {
    data[index] = (uint8_t)(value >> (index * 8));
  }
}

static void write_u64_le(uint8_t *data, uint64_t value) {
  for (uint32_t index = 0; index < 8; ++index) {
    data[index] = (uint8_t)(value >> (index * 8));
  }
}

static int align_up_size(size_t value, uint64_t alignment, size_t *result) {
  if (alignment == 0 || alignment > (uint64_t)SIZE_MAX) {
    return 0;
  }
  const size_t local_alignment = (size_t)alignment;
  if (value > SIZE_MAX - (local_alignment - 1)) {
    return 0;
  }
  *result = (value + local_alignment - 1) & ~(local_alignment - 1);
  return 1;
}

uint32_t bloom_primitive_abi_version(void) {
  return BLOOM_PRIMITIVE_ABI_VERSION;
}

int32_t bloom_primitive_run_vbuf(const uint8_t *input, size_t input_size,
                                 bloom_primitive_write_fn write,
                                 void *write_context) {
  if (input == 0 || write == 0) {
    return ARGMIN_INVALID_ARGUMENT;
  }

  /* Core validates first; these checks establish this capability's narrower
   * one-block, known-size, unsigned-u32-array contract defensively. */
  if (input_size < 24 || input[0] != 'V' || input[1] != 'B' ||
      input[2] != 'U' || input[3] != 'F' || read_u32_le(input + 4) != 0x00060000u ||
      input[8] < 3 || input[8] > 8 || input[9] != 0) {
    return ARGMIN_CONTRACT_MISMATCH;
  }

  const uint16_t header_size = read_u16_le(input + 10);
  const uint64_t base_step = UINT64_C(1) << input[8];
  size_t block_start;
  if (header_size < 24 || !align_up_size((size_t)header_size, base_step, &block_start) ||
      block_start > input_size || read_u64_le(input + 16) != input_size - block_start ||
      input_size - block_start < 8) {
    return ARGMIN_CONTRACT_MISMATCH;
  }

  const uint64_t anchor = read_u64_le(input + block_start);
  const uint8_t semantic = (uint8_t)(anchor & UINT64_C(0x0f));
  const uint8_t physical = (uint8_t)((anchor >> 4) & UINT64_C(0x0f));
  const uint8_t continuation = (uint8_t)((anchor >> 8) & UINT64_C(1));
  const uint8_t count64 = (uint8_t)((anchor >> 9) & UINT64_C(1));
  const uint8_t payload_shift = (uint8_t)((anchor >> 10) & UINT64_C(0x3f));
  const uint16_t bit_width = (uint16_t)((anchor >> 32) & UINT64_C(0xffff));
  const uint16_t inline_count = (uint16_t)(anchor >> 48);
  if (semantic != 0 || physical != 1 || continuation != 0 || bit_width != 32) {
    return ARGMIN_CONTRACT_MISMATCH;
  }

  size_t header_end = block_start + 8;
  uint64_t count = inline_count;
  if (count64) {
    if (inline_count != 0 || input_size - header_end < 8) {
      return ARGMIN_CONTRACT_MISMATCH;
    }
    count = read_u64_le(input + header_end);
    header_end += 8;
    if (count <= 65535) {
      return ARGMIN_CONTRACT_MISMATCH;
    }
  }

  const uint16_t combined_shift = (uint16_t)input[8] + payload_shift;
  if (combined_shift > 63) {
    return ARGMIN_CONTRACT_MISMATCH;
  }
  const uint64_t payload_alignment = UINT64_C(1) << combined_shift;
  size_t payload_start;
  if (!align_up_size(header_end, payload_alignment, &payload_start) ||
      count > (uint64_t)SIZE_MAX / 4) {
    return ARGMIN_CONTRACT_MISMATCH;
  }
  const size_t payload_size = (size_t)count * 4;
  if (payload_start > input_size || payload_size != input_size - payload_start) {
    return ARGMIN_CONTRACT_MISMATCH;
  }
  if (count == 0) {
    return ARGMIN_EMPTY_INPUT;
  }

  const uint8_t *payload = input + payload_start;
  uint32_t best_value = read_u32_le(payload);
  uint64_t best_index = 0;
  for (uint64_t index = 1; index < count; ++index) {
    const uint32_t value = read_u32_le(payload + (size_t)index * 4);
    if (value < best_value) {
      best_value = value;
      best_index = index;
    }
  }

  /* Canonical known-size v0.6 stream: BaseShift=3, KeyID=0, scalar u64. */
  uint8_t output[40] = {0};
  output[0] = 'V';
  output[1] = 'B';
  output[2] = 'U';
  output[3] = 'F';
  write_u32_le(output + 4, 0x00060000u);
  output[8] = 3;
  write_u16_le(output + 10, 24);
  write_u64_le(output + 16, 16);
  const uint64_t output_anchor = (UINT64_C(64) << 32) | (UINT64_C(1) << 48);
  write_u64_le(output + 24, output_anchor);
  write_u64_le(output + 32, best_index);
  return write(write_context, output, sizeof(output));
}
