#ifndef BLOOM_TEST_WORKSPACE_ABI_H
#define BLOOM_TEST_WORKSPACE_ABI_H

#include "bloom/workspace_abi.h"

/* Test-only status/size values for the workspace fixtures. */
#define BLOOM_TEST_WORKSPACE_ABI_VERSION BLOOM_PRIMITIVE_WORKSPACE_ABI_VERSION
#define BLOOM_TEST_WORKSPACE_OK ((int32_t)0)
#define BLOOM_TEST_WORKSPACE_INVALID_ARGUMENT ((int32_t)1)
#define BLOOM_TEST_WORKSPACE_UNSUPPORTED_SHAPE ((int32_t)3)
#define BLOOM_TEST_WORKSPACE_INSUFFICIENT ((int32_t)4)
#define BLOOM_TEST_WORKSPACE_MISALIGNED ((int32_t)5)
#define BLOOM_TEST_WORKSPACE_REQUIRED ((size_t)32u)
#define BLOOM_TEST_WORKSPACE_ALIGNMENT ((size_t)8u)

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

#endif
