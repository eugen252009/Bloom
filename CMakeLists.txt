cmake_minimum_required(VERSION 3.20)
project(Bloom VERSION 0.1.0 LANGUAGES C)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "The first native Bloom slice supports Linux only")
endif()

find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
find_program(CARGO_EXECUTABLE cargo REQUIRED)
find_program(RUSTC_EXECUTABLE rustc REQUIRED)

string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" BLOOM_PROCESSOR)
if(BLOOM_PROCESSOR MATCHES "^(x86_64|amd64)$")
  set(BLOOM_TARGET "x86_64-linux-gnu")
elseif(BLOOM_PROCESSOR MATCHES "^(aarch64|arm64)$")
  set(BLOOM_TARGET "aarch64-linux-gnu")
elseif(BLOOM_PROCESSOR STREQUAL "riscv64")
  set(BLOOM_TARGET "riscv64-linux-gnu")
else()
  message(FATAL_ERROR "Unsupported native target processor: ${CMAKE_SYSTEM_PROCESSOR}")
endif()

if(DEFINED ENV{VBUF_ROOT} AND NOT "$ENV{VBUF_ROOT}" STREQUAL "")
  set(_vbuf_root "$ENV{VBUF_ROOT}")
else()
  set(_vbuf_root "${CMAKE_SOURCE_DIR}/../vBuf")
endif()
set(VBUF_ROOT "${_vbuf_root}" CACHE PATH "Path to the authoritative vBuf checkout")
set(VBUF_RUST_MANIFEST "${VBUF_ROOT}/rust/Cargo.toml")
set(VBUF_CORE_LIBRARY "${VBUF_ROOT}/rust/target/debug/libvbuf_core.so")
if(NOT EXISTS "${VBUF_RUST_MANIFEST}")
  message(FATAL_ERROR "vBuf Core not found. Set VBUF_ROOT to the vBuf checkout")
endif()

add_custom_command(
  OUTPUT "${VBUF_CORE_LIBRARY}"
  COMMAND "${CARGO_EXECUTABLE}" build --manifest-path "${VBUF_RUST_MANIFEST}" -p vbuf-core
  WORKING_DIRECTORY "${VBUF_ROOT}"
  COMMENT "Building authoritative vBuf Core"
  VERBATIM
)
add_custom_target(vbuf_core DEPENDS "${VBUF_CORE_LIBRARY}")

function(bloom_native_library target source)
  add_library(${target} SHARED "${source}")
  target_include_directories(${target} PRIVATE "${CMAKE_SOURCE_DIR}/include")
  target_compile_definitions(${target} PRIVATE BLOOM_PRIMITIVE_IMPLEMENTATION=1)
  target_compile_options(${target} PRIVATE -fno-stack-protector)
  target_link_options(${target} PRIVATE -nostdlib -Wl,--no-undefined)
  set_target_properties(${target} PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/primitives"
  )
endfunction()

bloom_native_library(bytes_identity "primitives/bytes.identity/identity.c")
bloom_native_library(math_min_u32 "primitives/math.min.u32/min.c")
bloom_native_library(math_argmin_u32 "primitives/math.argmin.u32/argmin.c")
add_library(math_argsort_u32 SHARED "primitives/math.argsort.u32/argsort.c")
target_include_directories(math_argsort_u32 PRIVATE "${CMAKE_SOURCE_DIR}/include")
target_compile_definitions(math_argsort_u32 PRIVATE BLOOM_PRIMITIVE_IMPLEMENTATION=1)
target_compile_options(math_argsort_u32 PRIVATE -fno-stack-protector)
target_link_options(math_argsort_u32 PRIVATE -nostdlib -Wl,--no-undefined)
set_target_properties(math_argsort_u32 PROPERTIES
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/primitives"
)

set(MATH_MIN_FIXTURE_DIR "${CMAKE_BINARY_DIR}/fixtures/math.min.u32")
add_custom_command(
  OUTPUT "${MATH_MIN_FIXTURE_DIR}/.stamp"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/generate_math_min_fixtures.py"
    --vbuf-library "${VBUF_CORE_LIBRARY}"
    --output "${MATH_MIN_FIXTURE_DIR}"
  DEPENDS "${VBUF_CORE_LIBRARY}"
          "${CMAKE_SOURCE_DIR}/scripts/generate_math_min_fixtures.py"
  COMMENT "Generating authoritative math.min.u32 vBuf fixtures"
  VERBATIM
)
add_custom_target(math_min_fixtures ALL DEPENDS "${MATH_MIN_FIXTURE_DIR}/.stamp")
add_dependencies(math_min_fixtures vbuf_core)

set(MATH_ARGSORT_FIXTURE_DIR "${CMAKE_BINARY_DIR}/fixtures/math.argsort.u32")
add_custom_command(
  OUTPUT "${MATH_ARGSORT_FIXTURE_DIR}/.stamp"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/generate_math_argsort_fixtures.py"
    --vbuf-library "${VBUF_CORE_LIBRARY}"
    --output "${MATH_ARGSORT_FIXTURE_DIR}"
  DEPENDS "${VBUF_CORE_LIBRARY}"
          "${CMAKE_SOURCE_DIR}/scripts/generate_math_argsort_fixtures.py"
  COMMENT "Generating authoritative math.argsort.u32 vBuf fixtures"
  VERBATIM
)
add_custom_target(math_argsort_fixtures ALL DEPENDS "${MATH_ARGSORT_FIXTURE_DIR}/.stamp")
add_dependencies(math_argsort_fixtures vbuf_core)

set(MATH_ARGMIN_FIXTURE_DIR "${CMAKE_BINARY_DIR}/fixtures/math.argmin.u32")
add_custom_command(
  OUTPUT "${MATH_ARGMIN_FIXTURE_DIR}/.stamp"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/generate_math_argmin_fixtures.py"
    --vbuf-library "${VBUF_CORE_LIBRARY}"
    --output "${MATH_ARGMIN_FIXTURE_DIR}"
  DEPENDS "${VBUF_CORE_LIBRARY}"
          "${CMAKE_SOURCE_DIR}/scripts/generate_math_argmin_fixtures.py"
          "${CMAKE_SOURCE_DIR}/scripts/generate_math_min_fixtures.py"
  COMMENT "Generating authoritative math.argmin.u32 vBuf fixtures"
  VERBATIM
)
add_custom_target(math_argmin_fixtures ALL DEPENDS "${MATH_ARGMIN_FIXTURE_DIR}/.stamp")
add_dependencies(math_argmin_fixtures vbuf_core)

set(BLOOM_SOURCE_DIR "${CMAKE_SOURCE_DIR}")
set(BLOOM_BINARY_DIR "${CMAKE_BINARY_DIR}")
configure_file("scripts/bloom.in" "${CMAKE_BINARY_DIR}/bloom" @ONLY)
file(CHMOD "${CMAKE_BINARY_DIR}/bloom"
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)

add_custom_command(
  OUTPUT "${CMAKE_BINARY_DIR}/catalog.json"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/register_artifact.py"
    --capability "${CMAKE_SOURCE_DIR}/primitives/bytes.identity/manifest.template.json"
                 "$<TARGET_FILE:bytes_identity>"
    --capability "${CMAKE_SOURCE_DIR}/primitives/math.min.u32/manifest.template.json"
                 "$<TARGET_FILE:math_min_u32>"
    --capability "${CMAKE_SOURCE_DIR}/primitives/math.argmin.u32/manifest.template.json"
                 "$<TARGET_FILE:math_argmin_u32>"
    --capability "${CMAKE_SOURCE_DIR}/primitives/math.argsort.u32/manifest.template.json"
                 "$<TARGET_FILE:math_argsort_u32>"
    --output "${CMAKE_BINARY_DIR}/catalog.json"
    --target "${BLOOM_TARGET}"
  DEPENDS bytes_identity math_min_u32 math_argmin_u32 math_argsort_u32
          "${CMAKE_SOURCE_DIR}/scripts/register_artifact.py"
          "${CMAKE_SOURCE_DIR}/primitives/bytes.identity/manifest.template.json"
          "${CMAKE_SOURCE_DIR}/primitives/math.min.u32/manifest.template.json"
          "${CMAKE_SOURCE_DIR}/primitives/math.argmin.u32/manifest.template.json"
          "${CMAKE_SOURCE_DIR}/primitives/math.argsort.u32/manifest.template.json"
  COMMENT "Registering native capabilities in the local catalog"
  VERBATIM
)
add_custom_target(bloom_catalog ALL DEPENDS "${CMAKE_BINARY_DIR}/catalog.json")
add_dependencies(bloom_catalog vbuf_core)

include(CTest)
if(BUILD_TESTING)
  set(RUST_IDENTITY_MANIFEST "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_identity/Cargo.toml")
  set(RUST_IDENTITY_ARTIFACT
      "${CMAKE_BINARY_DIR}/rust-fixtures/debug/libbloom_test_rust_identity.so")
  set(RUST_WORKSPACE_MANIFEST "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_workspace/Cargo.toml")
  set(RUST_WORKSPACE_ARTIFACT
      "${CMAKE_BINARY_DIR}/rust-workspace-fixtures/debug/libbloom_test_rust_workspace.so")
  add_custom_command(
    OUTPUT "${RUST_IDENTITY_ARTIFACT}"
    COMMAND "${CMAKE_COMMAND}" -E env
      "RUSTFLAGS=-C link-arg=-nostdlib -C link-arg=-Wl,--no-undefined"
      "${CARGO_EXECUTABLE}" build --locked
      --manifest-path "${RUST_IDENTITY_MANIFEST}"
      --target-dir "${CMAKE_BINARY_DIR}/rust-fixtures"
    DEPENDS "${RUST_IDENTITY_MANIFEST}"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_identity/Cargo.lock"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_identity/src/lib.rs"
    COMMENT "Building Rust public-ABI compatibility fixture"
    VERBATIM
  )
  add_custom_target(test_rust_identity ALL DEPENDS "${RUST_IDENTITY_ARTIFACT}")

  # Optional executable compatibility lane: cross-build AArch64 fixtures and
  # run them under explicit qemu-aarch64 user-mode in an isolated container.
  execute_process(
    COMMAND "${RUSTC_EXECUTABLE}" --print target-libdir
    OUTPUT_VARIABLE RUST_HOST_TARGET_LIBDIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    COMMAND_ERROR_IS_FATAL ANY
  )
  get_filename_component(RUST_HOST_TARGET_DIR "${RUST_HOST_TARGET_LIBDIR}" DIRECTORY)
  set(RUST_LLD "${RUST_HOST_TARGET_DIR}/bin/rust-lld")
  set(AARCH64_RUST_IDENTITY
      "${CMAKE_BINARY_DIR}/aarch64-rust/aarch64-unknown-linux-gnu/debug/libbloom_test_rust_identity.so")
  add_custom_command(
    OUTPUT "${AARCH64_RUST_IDENTITY}"
    COMMAND "${CMAKE_COMMAND}" -E env
      "RUSTFLAGS=-C linker=${RUST_LLD} -C linker-flavor=ld.lld -C link-arg=--no-undefined"
      "${CARGO_EXECUTABLE}" build --locked
      --manifest-path "${RUST_IDENTITY_MANIFEST}"
      --target aarch64-unknown-linux-gnu
      --target-dir "${CMAKE_BINARY_DIR}/aarch64-rust"
    DEPENDS "${RUST_IDENTITY_MANIFEST}"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_identity/Cargo.lock"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_identity/src/lib.rs"
    COMMENT "Cross-building Rust AArch64 public-ABI fixture"
    VERBATIM
  )
  add_custom_target(aarch64_rust_identity DEPENDS "${AARCH64_RUST_IDENTITY}")

  set(AARCH64_RUST_WORKSPACE
      "${CMAKE_BINARY_DIR}/aarch64-rust-workspace/aarch64-unknown-linux-gnu/debug/libbloom_test_rust_workspace.so")
  add_custom_command(
    OUTPUT "${AARCH64_RUST_WORKSPACE}"
    COMMAND "${CMAKE_COMMAND}" -E env
      "RUSTFLAGS=-C panic=abort -C linker=${RUST_LLD} -C linker-flavor=ld.lld -C link-arg=--no-undefined"
      "${CARGO_EXECUTABLE}" build --locked
      --manifest-path "${RUST_WORKSPACE_MANIFEST}"
      --target aarch64-unknown-linux-gnu
      --target-dir "${CMAKE_BINARY_DIR}/aarch64-rust-workspace"
    DEPENDS "${RUST_WORKSPACE_MANIFEST}"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_workspace/Cargo.lock"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_workspace/src/lib.rs"
    COMMENT "Cross-building Rust AArch64 workspace ABI fixture"
    VERBATIM
  )
  add_custom_target(aarch64_rust_workspace DEPENDS "${AARCH64_RUST_WORKSPACE}")

  find_program(DOCKER_EXECUTABLE docker)
  if(DOCKER_EXECUTABLE)
    add_custom_target(aarch64_abi_test
      COMMAND "${DOCKER_EXECUTABLE}" build
        --tag bloom-aarch64-abi-test
        --file "${CMAKE_SOURCE_DIR}/tests/aarch64/Dockerfile"
        "${CMAKE_SOURCE_DIR}"
      COMMAND "${DOCKER_EXECUTABLE}" run --rm
        --volume "${CMAKE_SOURCE_DIR}:/work/src:ro"
        --volume "${CMAKE_BINARY_DIR}:/work/build"
        --volume "${VBUF_ROOT}:/work/vbuf:ro"
        bloom-aarch64-abi-test
      DEPENDS aarch64_rust_identity aarch64_rust_workspace bytes_identity
              "${CMAKE_SOURCE_DIR}/tests/aarch64/Dockerfile"
              "${CMAKE_SOURCE_DIR}/tests/aarch64/run.sh"
              "${CMAKE_SOURCE_DIR}/tests/aarch64/abi_runner.c"
              "${CMAKE_SOURCE_DIR}/tests/aarch64/workspace_runner.c"
              "${CMAKE_SOURCE_DIR}/tests/aarch64/dependent_primitive.c"
              "${CMAKE_SOURCE_DIR}/tests/fixtures/workspace_abi.h"
              "${CMAKE_SOURCE_DIR}/tests/fixtures/workspace_identity.c"
              "${CMAKE_SOURCE_DIR}/tests/fixtures/workspace_missing_query.c"
              "${CMAKE_SOURCE_DIR}/tests/fixtures/workspace_wrong_version.c"
              "${CMAKE_SOURCE_DIR}/tests/fixtures/aarch64_abi_identity.c"
      COMMENT "Executing C and Rust ABI v1 fixtures on AArch64 Linux under QEMU"
      USES_TERMINAL
      VERBATIM
    )
  endif()

  bloom_native_library(test_missing_symbol "tests/fixtures/missing_symbol.c")
  bloom_native_library(test_incompatible_abi "tests/fixtures/incompatible_abi.c")
  bloom_native_library(test_failing_primitive "tests/fixtures/failing_primitive.c")
  bloom_native_library(test_workspace_identity "tests/fixtures/workspace_identity.c")
  bloom_native_library(test_workspace_missing_query "tests/fixtures/workspace_missing_query.c")
  bloom_native_library(test_workspace_wrong_version "tests/fixtures/workspace_wrong_version.c")
  bloom_native_library(test_workspace_invalid_alignment "tests/fixtures/workspace_invalid_alignment.c")
  bloom_native_library(test_workspace_invalid_nonpower "tests/fixtures/workspace_invalid_nonpower.c")

  add_custom_command(
    OUTPUT "${RUST_WORKSPACE_ARTIFACT}"
    COMMAND "${CMAKE_COMMAND}" -E env
      "RUSTFLAGS=-C panic=abort -C link-arg=-nostdlib -C link-arg=-Wl,--no-undefined"
      "${CARGO_EXECUTABLE}" build --locked
      --manifest-path "${RUST_WORKSPACE_MANIFEST}"
      --target-dir "${CMAKE_BINARY_DIR}/rust-workspace-fixtures"
    DEPENDS "${RUST_WORKSPACE_MANIFEST}"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_workspace/Cargo.lock"
            "${CMAKE_SOURCE_DIR}/tests/fixtures/rust_workspace/src/lib.rs"
    COMMENT "Building Rust workspace ABI compatibility fixture"
    VERBATIM
  )
  add_custom_target(test_rust_workspace ALL DEPENDS "${RUST_WORKSPACE_ARTIFACT}")

  add_test(
    NAME bloom_tests
    COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s "${CMAKE_SOURCE_DIR}/tests" -v
  )
  set_tests_properties(bloom_tests PROPERTIES ENVIRONMENT
    "PYTHONPATH=${CMAKE_SOURCE_DIR}/src;BLOOM_BUILD_DIR=${CMAKE_BINARY_DIR};VBUF_ROOT=${VBUF_ROOT};BLOOM_VBUF_LIBRARY=${VBUF_CORE_LIBRARY};BLOOM_TARGET=${BLOOM_TARGET};BLOOM_MATH_FIXTURES=${MATH_MIN_FIXTURE_DIR};BLOOM_ARGMIN_FIXTURES=${MATH_ARGMIN_FIXTURE_DIR};BLOOM_ARGSORT_FIXTURES=${MATH_ARGSORT_FIXTURE_DIR};BLOOM_ARGSORT_ARTIFACT=${CMAKE_BINARY_DIR}/primitives/libmath_argsort_u32.so;BLOOM_RUST_IDENTITY=${RUST_IDENTITY_ARTIFACT};BLOOM_WORKSPACE_C=${CMAKE_BINARY_DIR}/primitives/libtest_workspace_identity.so;BLOOM_WORKSPACE_RUST=${RUST_WORKSPACE_ARTIFACT};BLOOM_WORKSPACE_MISSING_QUERY=${CMAKE_BINARY_DIR}/primitives/libtest_workspace_missing_query.so;BLOOM_WORKSPACE_WRONG_VERSION=${CMAKE_BINARY_DIR}/primitives/libtest_workspace_wrong_version.so;BLOOM_WORKSPACE_INVALID_ALIGNMENT=${CMAKE_BINARY_DIR}/primitives/libtest_workspace_invalid_alignment.so;BLOOM_WORKSPACE_INVALID_NONPOWER=${CMAKE_BINARY_DIR}/primitives/libtest_workspace_invalid_nonpower.so"
  )
endif()
