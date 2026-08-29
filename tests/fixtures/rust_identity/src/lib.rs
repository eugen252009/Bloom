#![no_std]

use core::ffi::c_void;

const BLOOM_PRIMITIVE_ABI_VERSION: u32 = 0x0001_0000;
#[cfg(target_arch = "aarch64")]
const _: [(); 8] = [(); core::mem::size_of::<usize>()];
#[cfg(target_arch = "aarch64")]
const _: [(); 8] = [(); core::mem::size_of::<*const u8>()];
type WriteFn = unsafe extern "C" fn(*mut c_void, *const u8, usize) -> i32;

#[unsafe(no_mangle)]
pub extern "C" fn bloom_primitive_abi_version() -> u32 {
    BLOOM_PRIMITIVE_ABI_VERSION
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn bloom_primitive_run_vbuf(
    input: *const u8,
    input_size: usize,
    write: Option<WriteFn>,
    write_context: *mut c_void,
) -> i32 {
    let Some(write) = write else {
        return 1;
    };
    if input.is_null() && input_size != 0 {
        return 1;
    }
    // SAFETY: Bloom ABI v1 guarantees the borrowed input range for this call;
    // the callback consumes or copies it synchronously.
    unsafe { write(write_context, input, input_size) }
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! {
    // The crate is built with panic=abort, so language unwinding cannot cross
    // the C ABI. This no-std fixture has no panic-producing execution path.
    loop {
        core::hint::spin_loop();
    }
}
