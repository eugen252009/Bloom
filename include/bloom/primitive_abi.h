#ifndef BLOOM_PRIMITIVE_ABI_H
#define BLOOM_PRIMITIVE_ABI_H

#include <stddef.h>
#include <stdint.h>

/*
 * BLOOM_CALL fixes the C calling convention where a target offers multiple
 * conventions. BLOOM_EXPORT is an implementation visibility helper, not a
 * semantic capability identifier. Define BLOOM_PRIMITIVE_IMPLEMENTATION when
 * compiling a C/C++ primitive artifact on Windows.
 */
#if defined(_WIN32)
#define BLOOM_CALL __cdecl
#if defined(BLOOM_PRIMITIVE_IMPLEMENTATION)
#define BLOOM_EXPORT __declspec(dllexport)
#else
#define BLOOM_EXPORT
#endif
#elif defined(__GNUC__) || defined(__clang__)
#define BLOOM_CALL
#define BLOOM_EXPORT __attribute__((visibility("default")))
#else
#define BLOOM_CALL
#define BLOOM_EXPORT
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Version 1.0 of the calling ABI. This is not a vBuf wire-format version. */
#define BLOOM_PRIMITIVE_ABI_VERSION ((uint32_t)0x00010000u)
#define BLOOM_PRIMITIVE_OK ((int32_t)0)

/*
 * The primitive borrows input for the duration of bloom_primitive_run_vbuf.
 * The runtime has already validated that it is one complete bounded vBuf.
 *
 * A primitive emits canonical vBuf bytes through write. The bytes passed to
 * write are borrowed only for that callback invocation; write must consume or
 * copy them before returning. A nonzero write result aborts execution.
 *
 * These pointers and lengths define the host calling boundary only. They do
 * not define or reinterpret the persistent vBuf wire representation.
 */
typedef int32_t(BLOOM_CALL *bloom_primitive_write_fn)(void *context,
                                                       const uint8_t *data,
                                                       size_t size);

/* Required C ABI exports. No language exception or unwind may cross them. */
BLOOM_EXPORT uint32_t BLOOM_CALL bloom_primitive_abi_version(void);
BLOOM_EXPORT int32_t BLOOM_CALL
bloom_primitive_run_vbuf(const uint8_t *input, size_t input_size,
                         bloom_primitive_write_fn write, void *write_context);

#ifdef __cplusplus
}
#endif

#endif
