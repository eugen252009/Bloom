#ifndef BLOOM_WORKSPACE_ABI_H
#define BLOOM_WORKSPACE_ABI_H

#include "bloom/primitive_abi.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION ((uint32_t)0x00010000u)

BLOOM_EXPORT uint32_t BLOOM_CALL
bloom_primitive_workspace_abi_version(void);

BLOOM_EXPORT int32_t BLOOM_CALL
bloom_primitive_workspace_required(const uint8_t *input, size_t input_size,
                                   size_t *required_size,
                                   size_t *required_alignment);

BLOOM_EXPORT int32_t BLOOM_CALL
bloom_primitive_run_vbuf_workspace(
    const uint8_t *input, size_t input_size, uint8_t *workspace,
    size_t workspace_size, bloom_primitive_write_fn write, void *write_context);

#ifdef __cplusplus
}
#endif

#endif
