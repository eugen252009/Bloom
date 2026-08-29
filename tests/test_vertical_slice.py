from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bloom.artifact import validate_artifact
from bloom.registry import LocalCatalog
from bloom.vbuf import VBufValidator


class VerticalSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = Path(os.environ["BLOOM_BUILD_DIR"])
        cls.catalog_path = cls.build / "catalog.json"
        cls.vbuf_library = Path(os.environ["BLOOM_VBUF_LIBRARY"])
        cls.target = os.environ["BLOOM_TARGET"]
        cls.rust_identity = Path(os.environ["BLOOM_RUST_IDENTITY"])
        cls.valid_vbuf = Path(os.environ["VBUF_ROOT"]) / "tests/fixtures/v06/valid-basic.vbuf"
        cls.math_fixtures = Path(os.environ["BLOOM_MATH_FIXTURES"])
        cls.argmin_fixtures = Path(os.environ["BLOOM_ARGMIN_FIXTURES"])
        cls.argsort_fixtures = Path(os.environ["BLOOM_ARGSORT_FIXTURES"])
        cls.argsort_artifact = Path(os.environ["BLOOM_ARGSORT_ARTIFACT"])
        if not cls.valid_vbuf.is_file():
            raise RuntimeError(f"authoritative vBuf fixture is missing: {cls.valid_vbuf}")
        if not cls.rust_identity.is_file():
            raise RuntimeError(f"Rust ABI fixture is missing: {cls.rust_identity}")
        if not (cls.math_fixtures / ".stamp").is_file():
            raise RuntimeError(f"math fixtures are missing: {cls.math_fixtures}")
        if not (cls.argmin_fixtures / ".stamp").is_file():
            raise RuntimeError(f"argmin fixtures are missing: {cls.argmin_fixtures}")
        if not (cls.argsort_fixtures / ".stamp").is_file():
            raise RuntimeError(f"argsort fixtures are missing: {cls.argsort_fixtures}")
        if not cls.argsort_artifact.is_file():
            raise RuntimeError(f"argsort artifact is missing: {cls.argsort_artifact}")

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp = Path(self.temporary.name)

    def run_cli(self, *arguments: str, data: bytes = b"") -> subprocess.CompletedProcess[bytes]:
        command = [
            sys.executable, "-m", "bloom", "--catalog", str(self.catalog_path),
            "--vbuf-library", str(self.vbuf_library), *arguments,
        ]
        return subprocess.run(command, input=data, capture_output=True, check=False)

    def catalog_for(self, artifact: Path, *, abi: int = 0x00010000,
                    target: str | None = None,
                    execution: dict[str, object] | None = None) -> Path:
        catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        entry = catalog["capabilities"][0]
        entry["artifact"]["path"] = str(artifact.resolve())
        entry["artifact"]["identity"] = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
        entry["artifact"]["bloom_primitive_abi"]["base"] = abi
        entry["artifact"]["target"] = target or self.target
        if execution is not None:
            entry["execution"] = execution
        output = self.temp / f"catalog-{artifact.stem}-{abi}.json"
        output.write_text(json.dumps(catalog), encoding="utf-8")
        return output

    def run_with_catalog(self, catalog: Path, *arguments: str,
                         data: bytes = b"") -> subprocess.CompletedProcess[bytes]:
        command = [
            sys.executable, "-m", "bloom", "--catalog", str(catalog),
            "--vbuf-library", str(self.vbuf_library), *arguments,
        ]
        return subprocess.run(command, input=data, capture_output=True, check=False)

    def assert_core_u64_scalar(self, data: bytes, expected: int) -> None:
        path = self.temp / "typed-output.vbuf"
        path.write_bytes(data)
        library = ctypes.CDLL(str(self.vbuf_library))
        open_vbuf = library.vbuf_v06_open
        open_vbuf.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32)]
        open_vbuf.restype = ctypes.c_void_p
        get = library.vbuf_v06_get
        get.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_size_t,
                        ctypes.c_uint8, ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(ctypes.c_size_t)]
        get.restype = ctypes.c_uint32
        close = library.vbuf_v06_close
        close.argtypes = [ctypes.c_void_p]
        error = ctypes.c_uint32()
        instance = open_vbuf(str(path).encode(), ctypes.byref(error))
        self.assertTrue(instance, f"Core open failed with {error.value}")
        try:
            pointer = ctypes.c_void_p()
            count = ctypes.c_size_t()
            self.assertEqual(get(instance, 0, 0, 3, ctypes.byref(pointer), ctypes.byref(count)), 0)
            self.assertEqual(count.value, 1)
            self.assertEqual(ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint64))[0], expected)
        finally:
            close(instance)

    def test_registry_lists_and_describes_known_capability(self) -> None:
        catalog = LocalCatalog(self.catalog_path)
        self.assertEqual(
            [item.name for item in catalog.list()],
            ["bytes.identity", "math.argmin.u32", "math.argsort.u32", "math.min.u32"]
        )
        description = catalog.describe("bytes.identity").describe()
        self.assertEqual(description["contract_version"], "1.0.0")
        self.assertEqual(description["input"]["representation"], "vbuf-v0.6")
        self.assertEqual(description["effects"], [])

    def test_unknown_capability_fails_cleanly(self) -> None:
        result = self.run_cli("describe", "missing.capability")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"unknown capability", result.stderr)

    def test_cli_lists_and_describes_through_catalog(self) -> None:
        listed = self.run_cli("capabilities")
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(
            listed.stdout, b"bytes.identity\nmath.argmin.u32\nmath.argsort.u32\nmath.min.u32\n"
        )
        described = self.run_cli("describe", "bytes.identity")
        self.assertEqual(described.returncode, 0)
        payload = json.loads(described.stdout)
        self.assertEqual(payload["artifact"]["target"], self.target)
        self.assertEqual(payload["artifact"]["bloom_primitive_abi"]["base"], 0x00010000)

    def test_external_identity_artifact_preserves_valid_vbuf_exactly(self) -> None:
        original = self.valid_vbuf.read_bytes()
        result = self.run_cli("run", "bytes.identity", data=original)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, original)
        self.assertEqual(result.stderr, b"")
        VBufValidator(self.vbuf_library).validate(result.stdout)

    def test_binary_stdout_is_not_contaminated(self) -> None:
        original = self.valid_vbuf.read_bytes()
        result = self.run_cli("run", "bytes.identity", data=original)
        self.assertEqual(hashlib.sha256(result.stdout).digest(), hashlib.sha256(original).digest())
        self.assertNotIn(b"bloom", result.stdout.lower())

    def test_rust_artifact_satisfies_the_same_public_abi(self) -> None:
        original = self.valid_vbuf.read_bytes()
        catalog = self.catalog_for(self.rust_identity)
        result = self.run_with_catalog(catalog, "run", "bytes.identity", data=original)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, original)
        self.assertEqual(result.stderr, b"")
        VBufValidator(self.vbuf_library).validate(result.stdout)

    def test_invalid_vbuf_fails_before_writing_stdout(self) -> None:
        result = self.run_cli("run", "bytes.identity", data=b"not-vbuf\x00\xff")
        self.assertEqual(result.returncode, 6)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"vBuf Core rejected input", result.stderr)

    def test_missing_expected_symbol_is_rejected(self) -> None:
        artifact = self.build / "primitives/libtest_missing_symbol.so"
        result = self.run_with_catalog(self.catalog_for(artifact), "run", "bytes.identity",
                                       data=self.valid_vbuf.read_bytes())
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"missing required exports", result.stderr)

    def test_incompatible_reported_abi_is_rejected(self) -> None:
        artifact = self.build / "primitives/libtest_incompatible_abi.so"
        result = self.run_with_catalog(self.catalog_for(artifact), "run", "bytes.identity",
                                       data=self.valid_vbuf.read_bytes())
        self.assertEqual(result.returncode, 5)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"primitive reports ABI", result.stderr)

    def test_incompatible_manifest_abi_is_rejected(self) -> None:
        artifact = self.build / "primitives/libbytes_identity.so"
        result = self.run_with_catalog(self.catalog_for(artifact, abi=0x00020000),
                                       "run", "bytes.identity", data=self.valid_vbuf.read_bytes())
        self.assertEqual(result.returncode, 5)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"not supported", result.stderr)

    def test_invalid_artifact_and_hash_are_rejected(self) -> None:
        invalid = self.temp / "invalid.so"
        invalid.write_bytes(b"not an ELF")
        result = self.run_with_catalog(self.catalog_for(invalid), "run", "bytes.identity")
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"not an ELF", result.stderr)

        catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        catalog["capabilities"][0]["artifact"]["path"] = str(
            (self.build / "primitives/libbytes_identity.so").resolve()
        )
        catalog["capabilities"][0]["artifact"]["identity"] = "sha256:" + "0" * 64
        wrong_hash = self.temp / "wrong-hash.json"
        wrong_hash.write_text(json.dumps(catalog), encoding="utf-8")
        result = self.run_with_catalog(wrong_hash, "run", "bytes.identity")
        self.assertEqual(result.returncode, 4)
        self.assertIn(b"identity mismatch", result.stderr)

    def test_wrong_target_is_rejected(self) -> None:
        artifact = self.build / "primitives/libbytes_identity.so"
        catalog = self.catalog_for(artifact, target="aarch64-linux-gnu")
        result = self.run_with_catalog(catalog, "run", "bytes.identity")
        self.assertEqual(result.returncode, 4)
        self.assertIn(b"incompatible with host", result.stderr)

    def test_primitive_failure_has_stable_error_and_clean_stdout(self) -> None:
        artifact = self.build / "primitives/libtest_failing_primitive.so"
        catalog = self.catalog_for(artifact)
        result = self.run_with_catalog(catalog, "run", "bytes.identity",
                                       data=self.valid_vbuf.read_bytes())
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"status 42", result.stderr)

    def assert_core_u64_array(self, data: bytes, expected: list[int]) -> None:
        path = self.temp / "typed-array-output.vbuf"
        path.write_bytes(data)
        library = ctypes.CDLL(str(self.vbuf_library))
        open_vbuf = library.vbuf_v06_open
        open_vbuf.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32)]
        open_vbuf.restype = ctypes.c_void_p
        get = library.vbuf_v06_get
        get.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_size_t,
                        ctypes.c_uint8, ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(ctypes.c_size_t)]
        get.restype = ctypes.c_uint32
        close = library.vbuf_v06_close
        close.argtypes = [ctypes.c_void_p]
        error = ctypes.c_uint32()
        instance = open_vbuf(str(path).encode(), ctypes.byref(error))
        self.assertTrue(instance, f"Core open failed with {error.value}")
        try:
            pointer = ctypes.c_void_p()
            count = ctypes.c_size_t()
            self.assertEqual(get(instance, 0, 0, 3, ctypes.byref(pointer), ctypes.byref(count)), 0)
            values = [] if count.value == 0 else list(
                ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint64))[:count.value]
            )
            self.assertEqual(values, expected)
        finally:
            close(instance)

    def test_math_argsort_normal_and_permutation_invariants(self) -> None:
        cases = ("normal", "sorted", "reverse", "duplicates", "equal", "single", "boundary")
        for case in cases:
            with self.subTest(case=case):
                source = (self.argsort_fixtures / f"{case}-input.vbuf").read_bytes()
                expected = (self.argsort_fixtures / f"{case}-expected.vbuf").read_bytes()
                result = self.run_cli("--max-workspace-bytes", "1048576", "run", "math.argsort.u32",
                                      data=source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)
                VBufValidator(self.vbuf_library).validate(result.stdout)
                values = self._decode_u32_array(source)
                permutation = self._decode_u64_array(result.stdout)
                self.assertEqual(sorted(permutation), list(range(len(values))))
                self.assertEqual(
                    [values[index] for index in permutation],
                    sorted(values),
                )
                self.assertEqual(len(permutation), len(values))
                self.assert_core_u64_array(result.stdout, permutation)

    def _decode_u32_array(self, data: bytes) -> list[int]:
        path = self.temp / "typed-array-input.vbuf"
        path.write_bytes(data)
        library = ctypes.CDLL(str(self.vbuf_library))
        open_vbuf = library.vbuf_v06_open
        open_vbuf.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32)]
        open_vbuf.restype = ctypes.c_void_p
        get = library.vbuf_v06_get
        get.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_size_t,
                        ctypes.c_uint8, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t)]
        get.restype = ctypes.c_uint32
        close = library.vbuf_v06_close
        close.argtypes = [ctypes.c_void_p]
        error = ctypes.c_uint32()
        instance = open_vbuf(str(path).encode(), ctypes.byref(error))
        self.assertTrue(instance)
        try:
            pointer, count = ctypes.c_void_p(), ctypes.c_size_t()
            self.assertEqual(get(instance, 0, 0, 2, ctypes.byref(pointer), ctypes.byref(count)), 0)
            return [] if count.value == 0 else list(ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[:count.value])
        finally:
            close(instance)

    def _decode_u64_array(self, data: bytes) -> list[int]:
        path = self.temp / "typed-array-output-raw.vbuf"
        path.write_bytes(data)
        library = ctypes.CDLL(str(self.vbuf_library))
        open_vbuf = library.vbuf_v06_open
        open_vbuf.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32)]
        open_vbuf.restype = ctypes.c_void_p
        get = library.vbuf_v06_get
        get.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_size_t,
                        ctypes.c_uint8, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t)]
        get.restype = ctypes.c_uint32
        close = library.vbuf_v06_close
        close.argtypes = [ctypes.c_void_p]
        error = ctypes.c_uint32()
        instance = open_vbuf(str(path).encode(), ctypes.byref(error))
        self.assertTrue(instance)
        try:
            pointer, count = ctypes.c_void_p(), ctypes.c_size_t()
            self.assertEqual(get(instance, 0, 0, 3, ctypes.byref(pointer), ctypes.byref(count)), 0)
            return [] if count.value == 0 else list(ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint64))[:count.value])
        finally:
            close(instance)

    def test_math_argsort_empty_and_budget(self) -> None:
        source = (self.argsort_fixtures / "empty-input.vbuf").read_bytes()
        for arguments in (("--max-workspace-bytes", "0"), ("--max-workspace-bytes", "1")):
            result = self.run_cli(*arguments, "run", "math.argsort.u32", data=source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, (self.argsort_fixtures / "empty-expected.vbuf").read_bytes())
        source = (self.argsort_fixtures / "normal-input.vbuf").read_bytes()
        for limit, code in ((None, 7), (63, 7), (64, 0), (65, 0)): 
            args = ["run", "math.argsort.u32"] if limit is None else [
                "--max-workspace-bytes", str(limit), "run", "math.argsort.u32"
            ]
            result = self.run_cli(*args, data=source)
            self.assertEqual(result.returncode, code, result.stderr)
            if code:
                self.assertEqual(result.stdout, b"")

    def test_math_argsort_rejects_wrong_shapes_and_malformed_vbuf(self) -> None:
        for fixture in ("wrong-u16-input.vbuf", "wrong-u64-input.vbuf", "wrong-scalar-input.vbuf"):
            result = self.run_cli("--max-workspace-bytes", "32", "run", "math.argsort.u32",
                                  data=(self.argsort_fixtures / fixture).read_bytes())
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(result.stdout, b"")
        result = self.run_cli("--max-workspace-bytes", "32", "run", "math.argsort.u32",
                              data=b"not-vbuf\x00")
        self.assertEqual(result.returncode, 6)
        self.assertEqual(result.stdout, b"")

    def test_math_min_normal_case_uses_external_artifact(self) -> None:
        source = (self.math_fixtures / "normal-input.vbuf").read_bytes()
        expected = (self.math_fixtures / "normal-expected.vbuf").read_bytes()
        result = self.run_cli("run", "math.min.u32", data=source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, b"")
        VBufValidator(self.vbuf_library).validate(result.stdout)

    def test_math_min_boundary_and_single_element(self) -> None:
        for case in ("boundary", "single"):
            with self.subTest(case=case):
                source = (self.math_fixtures / f"{case}-input.vbuf").read_bytes()
                expected = (self.math_fixtures / f"{case}-expected.vbuf").read_bytes()
                result = self.run_cli("run", "math.min.u32", data=source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_math_min_empty_input_is_defined_error(self) -> None:
        source = (self.math_fixtures / "empty-input.vbuf").read_bytes()
        result = self.run_cli("run", "math.min.u32", data=source)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"status 2", result.stderr)

    def test_math_min_rejects_wrong_primitive_representation(self) -> None:
        for fixture in ("wrong-u16-input.vbuf", "wrong-scalar-input.vbuf"):
            with self.subTest(fixture=fixture):
                source = (self.math_fixtures / fixture).read_bytes()
                result = self.run_cli("run", "math.min.u32", data=source)
                self.assertEqual(result.returncode, 7)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"status 3", result.stderr)

    def test_math_min_malformed_vbuf_is_rejected_before_execution(self) -> None:
        result = self.run_cli("run", "math.min.u32", data=b"not-vbuf\x00\xff")
        self.assertEqual(result.returncode, 6)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"vBuf Core rejected input", result.stderr)

    def test_math_min_is_byte_deterministic(self) -> None:
        source = (self.math_fixtures / "normal-input.vbuf").read_bytes()
        first = self.run_cli("run", "math.min.u32", data=source)
        second = self.run_cli("run", "math.min.u32", data=source)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_math_argmin_normal_case_uses_external_artifact(self) -> None:
        source = (self.argmin_fixtures / "normal-input.vbuf").read_bytes()
        expected = (self.argmin_fixtures / "normal-expected.vbuf").read_bytes()
        result = self.run_cli("run", "math.argmin.u32", data=source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, b"")
        VBufValidator(self.vbuf_library).validate(result.stdout)
        self.assert_core_u64_scalar(result.stdout, 1)

    def test_math_argmin_positions_and_first_minimum(self) -> None:
        expected_indices = {
            "beginning": 0,
            "end": 2,
            "duplicate": 1,
            "single": 0,
            "boundary": 1,
        }
        for case, expected_index in expected_indices.items():
            with self.subTest(case=case):
                source = (self.argmin_fixtures / f"{case}-input.vbuf").read_bytes()
                expected = (self.argmin_fixtures / f"{case}-expected.vbuf").read_bytes()
                result = self.run_cli("run", "math.argmin.u32", data=source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)
                self.assert_core_u64_scalar(result.stdout, expected_index)

    def test_math_argmin_empty_input_is_defined_error(self) -> None:
        source = (self.argmin_fixtures / "empty-input.vbuf").read_bytes()
        result = self.run_cli("run", "math.argmin.u32", data=source)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"status 2", result.stderr)

    def test_math_argmin_rejects_wrong_primitive_representation(self) -> None:
        fixtures = ("wrong-u16-input.vbuf", "wrong-u64-input.vbuf", "wrong-scalar-input.vbuf")
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                source = (self.argmin_fixtures / fixture).read_bytes()
                result = self.run_cli("run", "math.argmin.u32", data=source)
                self.assertEqual(result.returncode, 7)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"status 3", result.stderr)

    def test_math_argmin_malformed_vbuf_is_rejected_before_execution(self) -> None:
        result = self.run_cli("run", "math.argmin.u32", data=b"not-vbuf\x00\xff")
        self.assertEqual(result.returncode, 6)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"vBuf Core rejected input", result.stderr)

    def test_math_argmin_is_byte_deterministic(self) -> None:
        source = (self.argmin_fixtures / "duplicate-input.vbuf").read_bytes()
        first = self.run_cli("run", "math.argmin.u32", data=source)
        second = self.run_cli("run", "math.argmin.u32", data=source)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def _workspace_functions(self, artifact: Path):
        library = ctypes.CDLL(str(artifact))
        version = library.bloom_primitive_workspace_abi_version
        version.argtypes = []
        version.restype = ctypes.c_uint32
        query = library.bloom_primitive_workspace_required
        query.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                          ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        query.restype = ctypes.c_int32
        run = library.bloom_primitive_run_vbuf_workspace
        run.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                        ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
                        ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p,
                                        ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t),
                        ctypes.c_void_p]
        run.restype = ctypes.c_int32
        return version, query, run

    def test_workspace_c_and_rust_fixtures_have_same_contract(self) -> None:
        source = self.valid_vbuf.read_bytes()
        bad_shape = bytearray(source)
        bad_shape[32] = 2
        self.assertIsNone(VBufValidator(self.vbuf_library).validate(bytes(bad_shape)))
        callback_type = ctypes.CFUNCTYPE(
            ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t
        )
        for artifact in (Path(os.environ["BLOOM_WORKSPACE_C"]),
                         Path(os.environ["BLOOM_WORKSPACE_RUST"])):
            with self.subTest(artifact=artifact.name):
                version, query, run = self._workspace_functions(artifact)
                self.assertEqual(version(), 0x00010000)
                undefined = subprocess.run(
                    ["nm", "-D", "--undefined-only", str(artifact)],
                    capture_output=True, text=True, check=True,
                ).stdout.strip()
                self.assertEqual(undefined, "")
                input_storage = (ctypes.c_uint8 * len(source)).from_buffer_copy(source)
                bad_storage = (ctypes.c_uint8 * len(bad_shape)).from_buffer_copy(bad_shape)
                required = ctypes.c_size_t(99)
                alignment = ctypes.c_size_t(99)
                self.assertEqual(query(input_storage, len(source), ctypes.byref(required),
                                         ctypes.byref(alignment)), 0)
                self.assertEqual((required.value, alignment.value), (32, 8))
                required_again = ctypes.c_size_t()
                alignment_again = ctypes.c_size_t()
                self.assertEqual(query(input_storage, len(source), ctypes.byref(required_again),
                                       ctypes.byref(alignment_again)), 0)
                self.assertEqual((required_again.value, alignment_again.value),
                                 (required.value, alignment.value))
                failed_size = ctypes.c_size_t(7)
                failed_alignment = ctypes.c_size_t(7)
                self.assertEqual(query(bad_storage, len(bad_shape), ctypes.byref(failed_size),
                                       ctypes.byref(failed_alignment)), 3)
                self.assertEqual((failed_size.value, failed_alignment.value), (0, 0))
                self.assertEqual(query(input_storage, len(source), None,
                                       ctypes.byref(failed_alignment)), 1)
                self.assertEqual(query(input_storage, len(source), ctypes.byref(failed_size),
                                       None), 1)

                output = bytearray()
                def collect(_context, pointer, size):
                    output.extend(ctypes.string_at(pointer, size))
                    return 0
                callback = callback_type(collect)
                workspace = ctypes.create_string_buffer(required.value)
                self.assertEqual(run(input_storage, len(source),
                                     ctypes.cast(workspace, ctypes.POINTER(ctypes.c_uint8)),
                                     required.value, callback, None), 0)
                self.assertEqual(bytes(output), source)

                output.clear()
                oversized = ctypes.create_string_buffer(required.value + 1)
                self.assertEqual(run(input_storage, len(source),
                                     ctypes.cast(oversized, ctypes.POINTER(ctypes.c_uint8)),
                                     required.value + 1, callback, None), 0)
                self.assertEqual(bytes(output), source)

                output.clear()
                undersized = ctypes.create_string_buffer(required.value - 1)
                self.assertEqual(run(input_storage, len(source),
                                     ctypes.cast(undersized, ctypes.POINTER(ctypes.c_uint8)),
                                     required.value - 1, callback, None), 4)
                self.assertEqual(bytes(output), b"")

                output.clear()
                misaligned_storage = ctypes.create_string_buffer(required.value + 8)
                misaligned = ctypes.cast(ctypes.addressof(misaligned_storage) + 1,
                                         ctypes.POINTER(ctypes.c_uint8))
                self.assertEqual(run(input_storage, len(source), misaligned, required.value,
                                     callback, None), 5)
                self.assertEqual(bytes(output), b"")

                def fail(_context, _pointer, _size):
                    return -1
                self.assertEqual(run(input_storage, len(source),
                                     ctypes.cast(workspace, ctypes.POINTER(ctypes.c_uint8)),
                                     required.value, callback_type(fail), None), -1)
                # The host still owns and can reuse the range after callback failure.
                output.clear()
                self.assertEqual(run(input_storage, len(source),
                                     ctypes.cast(workspace, ctypes.POINTER(ctypes.c_uint8)),
                                     required.value, callback, None), 0)

                zero_size = ctypes.c_size_t(7)
                zero_alignment = ctypes.c_size_t(7)
                self.assertEqual(query(None, 0, ctypes.byref(zero_size),
                                       ctypes.byref(zero_alignment)), 0)
                self.assertEqual((zero_size.value, zero_alignment.value), (0, 8))
                self.assertEqual(run(None, 0, None, 0, callback, None), 0)

    def test_workspace_fixture_runs_through_production_runtime_path(self) -> None:
        source = self.valid_vbuf.read_bytes()
        execution = {
            "family": "workspace", "version": 0x00010000,
            "query": "bloom_primitive_workspace_required",
            "run": "bloom_primitive_run_vbuf_workspace",
        }
        for artifact in (Path(os.environ["BLOOM_WORKSPACE_C"]),
                         Path(os.environ["BLOOM_WORKSPACE_RUST"])):
            with self.subTest(artifact=artifact.name):
                catalog = self.catalog_for(artifact, execution=execution)
                result = self.run_with_catalog(
                    catalog, "--max-workspace-bytes", "32", "run", "bytes.identity",
                    data=source,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, source)
                self.assertEqual(result.stderr, b"")

    def test_workspace_budget_and_disabled_default(self) -> None:
        source = self.valid_vbuf.read_bytes()
        execution = {
            "family": "workspace", "version": 0x00010000,
            "query": "bloom_primitive_workspace_required",
            "run": "bloom_primitive_run_vbuf_workspace",
        }
        artifact = Path(os.environ["BLOOM_WORKSPACE_C"])
        catalog = self.catalog_for(artifact, execution=execution)
        for limit, expected in ((31, 7), (32, 0), (33, 0)):
            with self.subTest(limit=limit):
                result = self.run_with_catalog(
                    catalog, "--max-workspace-bytes", str(limit), "run", "bytes.identity",
                    data=source,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                if limit == 31:
                    self.assertEqual(result.stdout, b"")
                    self.assertIn(b"exceeds limit", result.stderr)
        disabled = self.run_with_catalog(catalog, "run", "bytes.identity", data=source)
        self.assertEqual(disabled.returncode, 7)
        self.assertEqual(disabled.stdout, b"")
        self.assertIn(b"requires max_workspace_bytes", disabled.stderr)

    def test_workspace_invalid_query_results_fail_before_run(self) -> None:
        source = self.valid_vbuf.read_bytes()
        base = {"family": "workspace", "version": 0x00010000,
                "query": "bloom_primitive_workspace_required",
                "run": "bloom_primitive_run_vbuf_workspace"}
        for variable in ("BLOOM_WORKSPACE_INVALID_ALIGNMENT", "BLOOM_WORKSPACE_INVALID_NONPOWER"):
            with self.subTest(variable=variable):
                catalog = self.catalog_for(Path(os.environ[variable]), execution=base)
                result = self.run_with_catalog(
                    catalog, "--max-workspace-bytes", "32", "run", "bytes.identity",
                    data=source,
                )
                self.assertEqual(result.returncode, 7)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"invalid size or alignment", result.stderr)

    def test_workspace_binding_is_checked_and_fails_closed(self) -> None:
        source = self.valid_vbuf.read_bytes()
        artifact = Path(os.environ["BLOOM_WORKSPACE_C"])
        base = {"family": "workspace", "version": 0x00010000,
                "query": "bloom_primitive_workspace_required",
                "run": "bloom_primitive_run_vbuf_workspace"}
        for name, binding, expected_code in (
            ("missing-query", {**base, "query": "missing"}, 4),
            ("missing-run", {**base, "run": "missing"}, 4),
            ("wrong-version", {**base, "version": 0x00020000}, 5),
        ):
            with self.subTest(name=name):
                result = self.run_with_catalog(
                    self.catalog_for(artifact, execution=binding), "run", "bytes.identity",
                    data=source,
                )
                self.assertEqual(result.returncode, expected_code)
                self.assertEqual(result.stdout, b"")

    def test_workspace_exports_are_admitted_only_by_test_inspection(self) -> None:
        expected = {
            "bloom_primitive_workspace_abi_version",
            "bloom_primitive_workspace_required",
            "bloom_primitive_run_vbuf_workspace",
        }
        for artifact in (Path(os.environ["BLOOM_WORKSPACE_C"]),
                         Path(os.environ["BLOOM_WORKSPACE_RUST"])):
            symbols = subprocess.run(
                ["nm", "-D", "--defined-only", str(artifact)],
                capture_output=True, text=True, check=True,
            ).stdout
            names = {line.split()[-1].split("@", 1)[0]
                     for line in symbols.splitlines() if line.split()}
            self.assertTrue(expected <= names)
            with self.subTest(artifact=artifact.name):
                self.assertEqual(self._workspace_functions(artifact)[0](), 0x00010000)

        missing = Path(os.environ["BLOOM_WORKSPACE_MISSING_QUERY"])
        missing_names = {line.split()[-1] for line in subprocess.run(
            ["nm", "-D", "--defined-only", str(missing)],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines() if line.split()}
        self.assertNotIn("bloom_primitive_workspace_required", missing_names)
        wrong = Path(os.environ["BLOOM_WORKSPACE_WRONG_VERSION"])
        self.assertEqual(self._workspace_functions(wrong)[0](), 0x00020000)
        self.assertNotEqual(self._workspace_functions(wrong)[0](), 0x00010000)

    def test_pure_artifacts_have_no_runtime_private_or_unresolved_imports(self) -> None:
        catalog = LocalCatalog(self.catalog_path)
        for name, filename in (
            ("bytes.identity", "libbytes_identity.so"),
            ("math.min.u32", "libmath_min_u32.so"),
            ("math.argmin.u32", "libmath_argmin_u32.so"),
        ):
            with self.subTest(capability=name):
                artifact = self.build / "primitives" / filename
                capability = catalog.resolve(name)
                with validate_artifact(capability) as validated:
                    self.assertEqual(validated.source_path, artifact.resolve())
                symbols = subprocess.run(
                    ["nm", "-D", "--undefined-only", str(artifact)],
                    capture_output=True, text=True, check=True,
                ).stdout.strip()
                self.assertEqual(symbols, "")


if __name__ == "__main__":
    unittest.main()
