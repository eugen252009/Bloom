#include "bloom/workspace_abi.h"

#include <stdint.h>

#define ARGSORT_INVALID_ARGUMENT 1
#define ARGSORT_CONTRACT_MISMATCH 3
#define ARGSORT_INSUFFICIENT_WORKSPACE 4
#define ARGSORT_MISALIGNED_WORKSPACE 5

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
  if (alignment == 0 || alignment > (uint64_t)SIZE_MAX) return 0;
  const size_t local_alignment = (size_t)alignment;
  if (value > SIZE_MAX - (local_alignment - 1)) return 0;
  *result = (value + local_alignment - 1) & ~(local_alignment - 1);
  return 1;
}

static int parse_input(const uint8_t *input, size_t input_size,
                       const uint8_t **payload_out, uint64_t *count_out) {
  if (input == 0 || input_size < 24 || input[0] != 'V' || input[1] != 'B' ||
      input[2] != 'U' || input[3] != 'F' || read_u32_le(input + 4) != 0x00060000u ||
      input[8] < 3 || input[8] > 8 || input[9] != 0) return 0;

  const uint16_t header_size = read_u16_le(input + 10);
  const uint64_t base_step = UINT64_C(1) << input[8];
  size_t block_start;
  if (header_size < 24 || !align_up_size((size_t)header_size, base_step, &block_start) ||
      block_start > input_size || read_u64_le(input + 16) != input_size - block_start ||
      input_size - block_start < 8) return 0;

  const uint64_t anchor = read_u64_le(input + block_start);
  const uint8_t semantic = (uint8_t)(anchor & UINT64_C(0x0f));
  const uint8_t physical = (uint8_t)((anchor >> 4) & UINT64_C(0x0f));
  const uint8_t continuation = (uint8_t)((anchor >> 8) & UINT64_C(1));
  const uint8_t count64 = (uint8_t)((anchor >> 9) & UINT64_C(1));
  const uint8_t payload_shift = (uint8_t)((anchor >> 10) & UINT64_C(0x3f));
  const uint16_t bit_width = (uint16_t)((anchor >> 32) & UINT64_C(0xffff));
  const uint16_t inline_count = (uint16_t)(anchor >> 48);
  if (semantic != 0 || physical != 1 || continuation != 0 || bit_width != 32) return 0;

  size_t header_end = block_start + 8;
  uint64_t count = inline_count;
  if (count64) {
    if (inline_count != 0 || input_size - header_end < 8) return 0;
    count = read_u64_le(input + header_end);
    header_end += 8;
    if (count <= 65535) return 0;
  }
  const uint16_t combined_shift = (uint16_t)input[8] + payload_shift;
  if (combined_shift > 63) return 0;
  size_t payload_start;
  if (!align_up_size(header_end, UINT64_C(1) << combined_shift, &payload_start) ||
      count > (uint64_t)SIZE_MAX / 4 || payload_start > input_size) return 0;
  const size_t payload_size = (size_t)count * 4;
  if (payload_size != input_size - payload_start) return 0;
  *payload_out = input + payload_start;
  *count_out = count;
  return 1;
}

static int required_workspace(uint64_t count, size_t *required) {
  if (count > (uint64_t)SIZE_MAX / 8) return 0;
  const size_t one = (size_t)count * 8;
  if (one > SIZE_MAX - one) return 0;
  *required = one + one;
  return 1;
}

uint32_t bloom_primitive_workspace_abi_version(void) {
  return BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION;
}

int32_t bloom_primitive_workspace_required(const uint8_t *input, size_t input_size,
                                           size_t *required_size,
                                           size_t *required_alignment) {
  if (required_size == 0 || required_alignment == 0) return ARGSORT_INVALID_ARGUMENT;
  *required_size = 0;
  *required_alignment = 0;
  const uint8_t *payload = 0;
  uint64_t count = 0;
  if (!parse_input(input, input_size, &payload, &count)) return ARGSORT_CONTRACT_MISMATCH;
  (void)payload;
  if (!required_workspace(count, required_size)) return ARGSORT_CONTRACT_MISMATCH;
  *required_alignment = 8;
  return 0;
}

static uint32_t value_at(const uint8_t *payload, uint64_t index) {
  return read_u32_le(payload + (size_t)index * 4);
}

static uint64_t index_at(const uint8_t *range, size_t index) {
  return read_u64_le(range + index * 8);
}

static void store_index(uint8_t *range, size_t index, uint64_t value) {
  write_u64_le(range + index * 8, value);
}

static int less_or_equal(const uint8_t *payload, uint64_t left, uint64_t right) {
  const uint32_t left_value = value_at(payload, left);
  const uint32_t right_value = value_at(payload, right);
  return left_value < right_value ||
         (left_value == right_value && left <= right);
}

static void stable_sort_indices(const uint8_t *payload, uint64_t count,
                                uint8_t *permutation, uint8_t *scratch) {
  const size_t n = (size_t)count;
  for (size_t index = 0; index < n; ++index) store_index(permutation, index, index);
  for (size_t width = 1; width < n;) {
    for (size_t left = 0; left < n;) {
      const size_t mid = width <= n - left ? left + width : n;
      const size_t right = width <= n - mid ? mid + width : n;
      size_t a = left, b = mid, out = left;
      while (a < mid && b < right) {
        const uint64_t ai = index_at(permutation, a);
        const uint64_t bi = index_at(permutation, b);
        if (less_or_equal(payload, ai, bi)) {
          store_index(scratch, out++, ai);
          ++a;
        } else {
          store_index(scratch, out++, bi);
          ++b;
        }
      }
      while (a < mid) store_index(scratch, out++, index_at(permutation, a++));
      while (b < right) store_index(scratch, out++, index_at(permutation, b++));
      for (size_t index = left; index < right; ++index)
        store_index(permutation, index, index_at(scratch, index));
      if (right == n) break;
      left = right;
    }
    if (width > n / 2) break;
    width *= 2;
  }
}

static int32_t emit_output(uint64_t count, const uint8_t *permutation,
                           bloom_primitive_write_fn write, void *write_context) {
  if (count > (uint64_t)SIZE_MAX / 8) return ARGSORT_CONTRACT_MISMATCH;
  const size_t payload_size = (size_t)count * 8;
  const int extended = count > 65535;
  const size_t block_size = 8 + (extended ? 8 : 0) + payload_size;
  if (block_size > UINT64_MAX) return ARGSORT_CONTRACT_MISMATCH;
  uint8_t header[40] = {0};
  header[0] = 'V'; header[1] = 'B'; header[2] = 'U'; header[3] = 'F';
  write_u32_le(header + 4, 0x00060000u);
  header[8] = 3;
  write_u16_le(header + 10, 24);
  write_u64_le(header + 16, (uint64_t)block_size);
  const uint64_t anchor_base = (UINT64_C(1) << 4) | (UINT64_C(64) << 32);
  uint64_t anchor = anchor_base;
  if (extended) anchor |= UINT64_C(1) << 9;
  else anchor |= count << 48;
  write_u64_le(header + 24, anchor);
  size_t header_size = 32;
  if (extended) {
    write_u64_le(header + 32, count);
    header_size = 40;
  }
  int32_t status = write(write_context, header, header_size);
  if (status != 0) return status;
  uint8_t chunk[256];
  for (size_t offset = 0; offset < payload_size;) {
    size_t bytes = payload_size - offset;
    if (bytes > sizeof(chunk)) bytes = sizeof(chunk);
    for (size_t index = 0; index < bytes / 8; ++index)
      write_u64_le(chunk + index * 8, index_at(permutation, offset / 8 + index));
    status = write(write_context, chunk, bytes);
    if (status != 0) return status;
    offset += bytes;
  }
  return 0;
}

int32_t bloom_primitive_run_vbuf_workspace(
    const uint8_t *input, size_t input_size, uint8_t *workspace,
    size_t workspace_size, bloom_primitive_write_fn write, void *write_context) {
  if (write == 0 || (input == 0 && input_size != 0) ||
      (workspace == 0 && workspace_size != 0)) return ARGSORT_INVALID_ARGUMENT;
  const uint8_t *payload = 0;
  uint64_t count = 0;
  if (!parse_input(input, input_size, &payload, &count)) return ARGSORT_CONTRACT_MISMATCH;
  size_t required = 0;
  if (!required_workspace(count, &required)) return ARGSORT_CONTRACT_MISMATCH;
  if (workspace_size < required) return ARGSORT_INSUFFICIENT_WORKSPACE;
  if (required != 0 && ((uintptr_t)workspace & (uintptr_t)7) != 0)
    return ARGSORT_MISALIGNED_WORKSPACE;
  if (required != 0) {
    const size_t permutation_size = required / 2;
    stable_sort_indices(payload, count, workspace, workspace + permutation_size);
    return emit_output(count, workspace, write, write_context);
  }
  return emit_output(count, workspace, write, write_context);
}
