# M6 bring-up build

Development starts from the MIT snapshot identified by `last-mit` (`809541515659bf4e504807fd72bc0a539be5eee7`). Keep that tag unchanged. Use feature branches and squash validated changes into `main`. New bootloader changes remain MIT and retain the existing component notices. Keep research notes, hardware captures, and experimental scripts outside Git.

## Build

On an Apple Silicon macOS host, install the dependencies described in the root README, including LLVM, LLD, and the Rust `aarch64-unknown-none-softfloat` target. Then run:

```sh
./tools/build-m6-bringup.sh
```

The script cleans the existing build directory before changing compiler flags, then builds with `BRINGUP`, `TARGET=T8152`, `RELEASE=0`, and `CHAINLOADING=0`. Set `JOBS` to override the default eight build jobs. Outputs are `build/m1n1.bin` and `build/m1n1.macho`; the minimal profile's embedded version ends with `-m6-bringup`.

This uses the existing minimal initialization path. It skips the normal MMU, interrupt-controller, secondary-CPU, power-management, display, SEP, and USB-controller initialization. Dockchannel UART setup remains available for the DebugUSB connection established by the host.

To add interrupt-controller initialization while leaving the other subsystems disabled:

```sh
./tools/build-m6-bringup.sh aic
```

This adds `BRINGUP_AIC` and uses the version suffix `-m6-bringup-aic`. It initializes the existing AIC driver but does not test interrupt delivery or establish Linux interrupt support. Omitting the argument, or passing `minimal`, selects the original minimal profile.

To test paging and caches together with AIC initialization:

```sh
./tools/build-m6-bringup.sh mmu
```

This adds `BRINGUP_MMU` and uses the suffix `-m6-bringup-mmu`. RAM mappings cover the boot-data region beginning at `phys_base` and a heap of at most 64 MiB. The allocator is limited to that window. This profile skips MCC initialization and the broader firmware `pmap-io-ranges` remapping; ARM-IO MMIO mappings remain available. It is an early paging test, not a complete physical-memory map for Linux or device firmware. Cache maintenance across devices and subsequent payloads remains unvalidated. Secondary CPUs and the other disabled subsystems remain disabled.

## Target and connection

The initial target is a Mac mini with `Mac18,5`, `J873gAP`, and `T8152`. DebugUSB enumeration was verified on macOS 27.2 using an M4 Max MacBook Pro host and a direct Thunderbolt 4 cable:

- Host port: left USB-C port closest to MagSafe.
- Target port: middle rear USB-C port.
- Host utility: Apache-2.0 `macvdmtool`, using its `debugusb` command.
- USB identity: `05ac:1881`, protocol version 5.00.

Find the current `/dev/cu.kis-*-ch-0` device and set `M1N1DEVICE` to that path. Successful enumeration while the target runs macOS does not establish m1n1 proxy communication.

## First boot

Prepare a separate test OS volume group using a macOS version compatible with the target. Install the raw binary as that test system's custom boot object from its paired recovery environment, following the current macOS boot-policy requirements. Verify the intended test volume before running `kmutil configure-boot`; the existing `tools/kmutil.py` helper selects the default boot volume automatically.

The preserved installer does not list `T8152` or `J873gAP` and has no compatible M6 firmware entry. Its existing M1–M3 installation recipes are not a validated M6 installation path.
