#![no_std]

use core::ffi::c_void;

const WORKSPACE_ABI_VERSION: u32 = 0x0001_0000;
const OK: i32 = 0;
const INVALID_ARGUMENT: i32 = 1;
const UNSUPPORTED_SHAPE: i32 = 3;
const INSUFFICIENT: i32 = 4;
const MISALIGNED: i32 = 5;
const REQUIRED: usize = 32;
const ALIGNMENT: usize = 8;

type WriteFn = unsafe extern "C" fn(*mut c_void, *const u8, usize) -> i32;

#[unsafe(no_mangle)]
pub extern "C" fn bloom_primitive_workspace_abi_version() -> u32 {
    WORKSPACE_ABI_VERSION
}

unsafe fn query(
    input: *const u8,
    input_size: usize,
    required_size: *mut usize,
    required_alignment: *mut usize,
) -> i32 {
    if required_size.is_null()
        || required_alignment.is_null()
        || (input.is_null() && input_size != 0)
    {
        return INVALID_ARGUMENT;
    }
    // SAFETY: output pointers were checked non-null and belong to the caller.
    unsafe {
        *required_size = 0;
        *required_alignment = 0;
    }
    if input_size == 0 {
        // SAFETY: output pointers were checked above.
        unsafe { *required_alignment = ALIGNMENT };
        return OK;
    }
    // SAFETY: the caller supplies the borrowed range for this call.
    let bytes = unsafe { core::slice::from_raw_parts(input, input_size) };
    if input_size < 44 || bytes[0] != b'V' || bytes[32] != 1 {
        return UNSUPPORTED_SHAPE;
    }
    // SAFETY: output pointers were checked above.
    unsafe {
        *required_size = REQUIRED;
        *required_alignment = ALIGNMENT;
    }
    OK
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn bloom_primitive_workspace_required(
    input: *const u8,
    input_size: usize,
    required_size: *mut usize,
    required_alignment: *mut usize,
) -> i32 {
    // SAFETY: this function's caller provides ABI pointers; query validates them.
    unsafe { query(input, input_size, required_size, required_alignment) }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn bloom_primitive_run_vbuf_workspace(
    input: *const u8,
    input_size: usize,
    workspace: *mut u8,
    workspace_size: usize,
    write: Option<WriteFn>,
    write_context: *mut c_void,
) -> i32 {
    let Some(write) = write else { return INVALID_ARGUMENT };
    let mut required_size = 0;
    let mut required_alignment = 0;
    // SAFETY: query validates the borrowed input and output pointers.
    let status = unsafe { query(input, input_size, &mut required_size, &mut required_alignment) };
    if status != OK {
        return status;
    }
    if workspace.is_null() && workspace_size != 0 {
        return INVALID_ARGUMENT;
    }
    if workspace_size < required_size {
        return INSUFFICIENT;
    }
    if required_size != 0 && (workspace as usize) % required_alignment != 0 {
        return MISALIGNED;
    }
    if required_size == 0 {
        // Avoid constructing a Rust slice from a null zero-length pointer;
        // the C ABI permits that representation for an empty range.
        // SAFETY: the callback is synchronous and the empty input is borrowed
        // for this call.
        return unsafe { write(write_context, input, input_size) };
    }
    // SAFETY: the caller supplied at least REQUIRED writable bytes. The loop
    // stays within that range and verifies the mutation before output.
    let scratch = unsafe { core::slice::from_raw_parts_mut(workspace, required_size) };
    for (index, byte) in scratch.iter_mut().enumerate() {
        *byte = (index as u8) ^ 0xa5;
    }
    for (index, byte) in scratch.iter().enumerate() {
        if *byte != (index as u8) ^ 0xa5 {
            return INVALID_ARGUMENT;
        }
    }
    // SAFETY: the callback is synchronous and the input is borrowed for this call.
    unsafe { write(write_context, input, input_size) }
}

#[unsafe(no_mangle)]
pub extern "C" fn rust_eh_personality() {}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! {
    loop {
        core::hint::spin_loop();
    }
}
