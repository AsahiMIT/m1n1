# M6 bring-up build

Development continues on `main` from the MIT snapshot identified by `last-mit` (`809541515659bf4e504807fd72bc0a539be5eee7`). Keep that tag unchanged. New bootloader changes remain MIT and retain the existing component notices.

## Build

On an Apple Silicon macOS host, install the dependencies described in the root README, including LLVM, LLD, and the Rust `aarch64-unknown-none-softfloat` target. Then run:

```sh
./tools/build-m6-bringup.sh
```

The script cleans the existing build directory before changing compiler flags, then builds with `BRINGUP`, `TARGET=T8152`, `RELEASE=0`, and `CHAINLOADING=0`. Set `JOBS` to override the default eight build jobs. Outputs are `build/m1n1.bin` and `build/m1n1.macho`; the embedded version ends with `-m6-bringup`.

This uses the existing minimal initialization path. It skips the normal MMU, interrupt-controller, secondary-CPU, power-management, display, SEP, and USB-controller initialization. Dockchannel UART setup remains available for the DebugUSB connection established by the host. The first runtime milestone is reaching the proxy and capturing the firmware-provided device tree. Compilation alone does not establish that the firmware boots on M6.

## Target and connection

The initial target is a Mac mini with `Mac18,5`, `J873gAP`, and `T8152`. DebugUSB enumeration was verified on macOS 27.2 using an M4 Max MacBook Pro host and a direct Thunderbolt 4 cable:

- Host port: left USB-C port closest to MagSafe.
- Target port: middle rear USB-C port.
- Host utility: Apache-2.0 `macvdmtool`, using its `debugusb` command.
- USB identity: `05ac:1881`, protocol version 5.00.

Find the current `/dev/cu.kis-*-ch-0` device and set `M1N1DEVICE` to that path. Successful enumeration while the target runs macOS does not establish m1n1 proxy communication.

## First boot

Prepare a separate test OS volume group using a macOS version compatible with the target. Install the raw binary as that test system's custom boot object from its paired recovery environment, following the current macOS boot-policy requirements. Verify the intended test volume before running `kmutil configure-boot`; the existing `tools/kmutil.py` helper selects the default boot volume automatically.

The preserved installer does not list `T8152` or `J873gAP` and has no compatible M6 firmware entry. Its existing M1–M3 installation recipes are not a validated M6 installation path. Booting this image on M6 and collecting a proxy response remain pending hardware validation.
