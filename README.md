# Hackintosh AutoEFI

[中文](#中文) · [English](#english)

## 中文

给 OpCore-Simplify 用的离线硬件采集启动盘。

做这个工具的起因很简单：机器已经装不了 Windows，但重新生成 EFI 又需要硬件报告。靠型号和旧 EFI 拼报告，很容易漏掉声卡芯片、内屏连接或 ACPI 路径。这个工具从 U 盘启动一个 Linux 环境，采完后把报告写回 U 盘，再自动关机。

它负责采集，不负责生成 EFI。后续仍然使用 OpCore-Simplify，并保留音频、无线网卡、目标 macOS 等选项的选择过程。

### 怎么用

使用已经制作好的启动盘：

1. 关闭目标电脑的 Secure Boot，插入 U 盘，从固件启动菜单选择它的 UEFI 启动项。
2. 选择 `Collect hardware automatically - offline Linux`。不需要联网，也不需要输入命令。
3. 等待屏幕提示报告已保存，机器会自动关机。关机后再拔 U 盘。
4. 打开 U 盘里的 `HardwareReports/时间-编号/`。

里面先看 `Readiness.json`。`generation_ready` 为 `false` 时，按 `missing_or_review` 检查缺项，不要直接拿报告生成 EFI。通过检查后，在 OpCore-Simplify 中导入同一目录的 `Report.json`，并使用配套的 `ACPI/`。

菜单里的 `macOS / OpenCore - existing EFI` 会转到 U 盘原有的 OpenCore。如果普通采集黑屏，可以试第三项基础显示模式；这个模式可能读不到内屏信息，报告会提示复核。

采集必须在 OpenCore **之前**启动。经 OpenCore 启动 Linux，会把已注入的 ACPI、SMBIOS 当成机器原始信息。

### 报告里有什么

| 文件 | 用途 |
| --- | --- |
| `Report.json` | 经固定版本 OpCore-Simplify 校验器整理的报告 |
| `Readiness.json` | 校验结果、缺项和待复核信息 |
| `Report.upstream.json` | Hardware-Sniffer 原始 Linux 输出 |
| `Report.raw.json` | 加入实测修正后的完整报告 |
| `Evidence.json` | PCI、USB、ACPI 设备及修正依据 |
| `ACPI/` | 从固件表接口读取的二进制表，包括 DSDT、SSDT |
| `Raw/` | 可读取的 SMBIOS 原始表和声卡 codec 信息 |
| `Validation.json` | 上游校验器的错误、警告和清理结果 |
| `SHA256.json` | 采集文件校验值；不包含自身和随后保存的 `startup.log` |

另外保存 `lspci`、`lsusb`、`dmidecode`、`dmesg` 等诊断输出。报告可能含序列号等设备标识，提交 issue 前先检查并脱敏。

### 能做什么，哪些地方还有限制

支持 x86-64 UEFI 电脑，使用 FAT32 U 盘。采集环境不挂载内置硬盘的文件系统，也不安装系统或改写现有 EFI 配置。

目前不能承诺每台机器都能读全，更不能把 Linux 报告称为 Windows 报告的完全替代。固件隐藏的设备、没有 Linux 驱动的控制器、独显断电后的状态，都可能影响结果。内屏、触摸板、音频 codec、PCI 路径等读取失败时会留下原始证据和复核提示；没有读取到不等于没有这块设备。

本工具不做 USB 端口映射，也不替用户选择 AMFIPass、AppleALC 或无线驱动。通过 JSON 格式校验，只说明格式符合要求，不代表 EFI 一定能启动。

已在 QEMU 的 UEFI 环境测试完整的“启动 → 自动采集 → 写回 U 盘 → 关机”流程，并有针对核心数、PCI 根路径、声卡 codec、Secure Boot 和 ReBAR 的测试。实体机器的兼容性还需要继续积累。

### 自己制作启动包

源码仓库不带 Linux 镜像和编译好的 EFI。

在 Linux 上准备 Python 3.11+、7-Zip、GRUB 的 `grub-mkstandalone` 和 `x86_64-efi` 模块。Debian/Ubuntu 对应的软件包一般是 `python3`、`7zip`、`grub-common`、`grub-efi-amd64-bin`。

运行下面的命令。首次制作时会从 SystemRescue 官方站点下载固定版本的镜像并校验 SHA256，以后复用已校验的缓存。目标机器的采集过程仍然完全离线。

```sh
python3 build.py --output /path/to/new-build
python3 -m unittest -v test_collector test_download
```

已有 [SystemRescue 13.02 amd64](https://www.system-rescue.org/Download/) 镜像时，可以加 `--iso /path/to/systemrescue-13.02-amd64.iso`，跳过下载。镜像仍会校验；下载中断或校验失败不会生成可用缓存。`--cache-dir` 可以指定缓存位置。

构建脚本只接受新的输出目录，不碰物理磁盘。结果中包含 `package/`、校验清单和 Windows 写入脚本。

在 Windows 中先用 `Get-Disk` 确认 U 盘的序列号、容量和盘符，再从构建目录运行：

```powershell
.\Install-Collector.ps1 -DriveLetter X -ExpectedSerial '你的U盘序列号' -ExpectedSize 你的磁盘容量字节数
```

安装器要求 FAT32，不会格式化。它先逐文件校验，再暂存、写入并回读；原来的 `EFI/BOOT/BOOTx64.efi` 会备份到 `HardwareCollector-backup-时间/`，`EFI/OC/` 保留。已有同名采集器和 autorun 文件也会备份。

要恢复原来的直接启动方式，把备份中的 `BOOTx64-original.efi` 复制回 `EFI/BOOT/BOOTx64.efi` 即可。请保留这个备份。固件里直接指向 `EFI/OC/OpenCore.efi` 的旧启动项会绕过采集菜单，需要选择 U 盘的 UEFI 启动项。

### 依赖与许可证

采集器使用 [Hardware-Sniffer](https://github.com/lzhoang2801/Hardware-Sniffer) 的 Linux 实现；格式检查使用 [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify) 的报告校验器。固定版本与本地修正见 [docs/design.md](docs/design.md)。

我们自己写的代码采用 **GPL-3.0-only**，见 [LICENSE](LICENSE)。对外分发受其约束的修改版，需要提供对应源码；私人内部修改不必公开。参见 [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#GPLRequireSourcePostedPublic)。

引用的 BSD-3-Clause 代码保留原作者、许可证和免责声明，不擅自用作者名义背书。BSD 不要求修改版开源，也不妨碍我们自己的代码使用 GPLv3。其他依赖保留各自许可，见 [THIRD_PARTY.md](THIRD_PARTY.md)。

### 源码和启动包怎么发布

Git 仓库放源码、构建脚本、文档和许可证，不把 Linux 镜像提交进去。当前启动环境使用 SystemRescue 13.02：内核约 16MB，initramfs 约 184MB，压缩根文件系统约 1.15GB。它还没有做专门裁剪；只有内核不能运行采集器，还需要驱动、Python 和相关工具。

首版发布源码和构建脚本，**不上传或托管 SystemRescue 镜像**。制作时由脚本从官方站点下载并校验，用户在自己的电脑上组装启动包。以后若提供完整启动包，放到 GitHub Releases，并准备二进制对应的源码、构建材料和许可说明。普通 Git 仓库会拒绝大于 100MiB 的文件；见 [GitHub 大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

准备仓库和发布包的具体步骤见 [docs/publishing.md](docs/publishing.md)。源码包不包含个人 EFI、采集报告或设备序列号。

## English

An offline hardware collection USB for OpCore-Simplify.

This started with a practical problem: the target machine could no longer run Windows, but rebuilding its EFI still needed a hardware report. Reconstructing that report from a model number and an old EFI can miss the audio codec, panel connection, or ACPI paths. This tool boots Linux from a USB drive, collects the report, saves it back to the USB, and shuts down.

The current version collects hardware. EFI generation still takes place in OpCore-Simplify, including the choices for audio, Wi-Fi, and the target macOS version.

### Using the USB

1. Disable Secure Boot on the target computer, then select the USB's UEFI entry in the firmware boot menu.
2. Select `Collect hardware automatically - offline Linux`. No network connection or commands are needed.
3. Wait for the report-saved message and automatic shutdown. Remove the USB after the computer powers off.
4. Open `HardwareReports/timestamp-id/` on the USB.

Read `Readiness.json` first. If `generation_ready` is `false`, review `missing_or_review` before generating an EFI. Once the report has been reviewed, import `Report.json` into OpCore-Simplify and use the `ACPI/` directory from the same collection.

The second menu entry, `macOS / OpenCore - existing EFI`, starts the USB's existing OpenCore. If normal collection has a display problem, try the basic-display entry. It may not expose panel details; the report will flag missing information.

Run the collector **before OpenCore**. Starting Linux through OpenCore can expose injected SMBIOS and ACPI data instead of the original firmware data.

### Output

| File | Contents |
| --- | --- |
| `Report.json` | Report cleaned by the pinned OpCore-Simplify validator |
| `Readiness.json` | Validation status, missing fields, and review items |
| `Report.upstream.json` | Original Hardware-Sniffer Linux output |
| `Report.raw.json` | Full report after measured corrections |
| `Evidence.json` | PCI, USB, ACPI inventory and correction evidence |
| `ACPI/` | Binary firmware tables, including DSDT and SSDTs |
| `Raw/` | Readable SMBIOS tables and audio codec data |
| `Validation.json` | Upstream validation errors, warnings, and cleaned data |
| `SHA256.json` | File hashes, excluding itself and the later `startup.log` |

Diagnostic output from tools such as `lspci`, `lsusb`, `dmidecode`, and `dmesg` is also saved. Reports can contain device identifiers and serial numbers. Review and redact them before posting an issue.

### Scope and limitations

The boot package targets x86-64 UEFI computers and FAT32 USB drives. It does not mount internal disk filesystems, install an operating system, or change the existing OpenCore configuration.

Firmware-hidden devices and missing Linux drivers can leave gaps. The wrapper records evidence and review items when checks fail; an unreadable device is not proof that the device is absent. A valid JSON report does not establish completeness, equivalence to a Windows capture, or a working EFI.

USB port mapping is separate. The collector does not choose AMFIPass, AppleALC, or wireless drivers for you. Those choices remain part of the generator workflow.

The full UEFI boot, collection, USB write-back, and shutdown flow has been tested in QEMU. Unit tests cover physical core counts, PCI root UIDs, HDA codec IDs, Secure Boot variables, and ReBAR. Physical-machine compatibility still needs broader testing.

### Building a package

The source repository does not contain a Linux ISO or a prebuilt EFI binary. On Linux, install Python 3.11+, 7-Zip, `grub-mkstandalone`, and the matching GRUB `x86_64-efi` modules. Typical Debian/Ubuntu package names are `python3`, `7zip`, `grub-common`, and `grub-efi-amd64-bin`.

Run the following command. The first build downloads the pinned ISO from the official SystemRescue site and verifies its SHA256. Later builds reuse the verified cache. Hardware collection on the target machine remains fully offline.

```sh
python3 build.py --output /path/to/new-build
python3 -m unittest -v test_collector test_download
```

To use an existing [SystemRescue 13.02 amd64](https://www.system-rescue.org/Download/) ISO, add `--iso /path/to/systemrescue-13.02-amd64.iso`. Its hash is still verified. Interrupted or invalid downloads do not become valid cached images. Use `--cache-dir` to choose a cache location.

The builder requires a new output directory. It creates files only; it does not write a physical disk. The result contains `package/`, a manifest, and a Windows installer script.

On Windows, inspect the USB's serial number, disk size in bytes, and drive letter with `Get-Disk` and `Get-Partition`. Run this from the build directory, replacing the sample values:

```powershell
.\Install-Collector.ps1 -DriveLetter X -ExpectedSerial 'YOUR_USB_SERIAL' -ExpectedSize 64000000000
```

The installer requires FAT32 and does not format the drive. It verifies the package, stages files, flushes writes, and checks their hashes after writing. The original `EFI/BOOT/BOOTx64.efi` is backed up under `HardwareCollector-backup-timestamp/`. Existing `EFI/OC/` files are preserved. Previous collector and autorun files are backed up if present.

To restore direct OpenCore boot, copy `BOOTx64-original.efi` from that backup to `EFI/BOOT/BOOTx64.efi`. Keep the backup. A firmware boot entry that points directly to `EFI/OC/OpenCore.efi` bypasses the collector menu; select the USB's UEFI entry instead.

### Dependencies and license

The collector uses the Linux implementation of [Hardware-Sniffer](https://github.com/lzhoang2801/Hardware-Sniffer), with the report validator from [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify). Pinned revisions and wrapper corrections are documented in [docs/design.md](docs/design.md).

Our own code is **GPL-3.0-only**; see [LICENSE](LICENSE). Distributing covered modified versions requires their corresponding source. Private internal changes need not be published. See the [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#GPLRequireSourcePostedPublic).

Vendored BSD-3-Clause code keeps its original copyright, license, and disclaimer. Do not use upstream authors' names to imply endorsement. BSD does not require modified versions to be open source, and it permits use alongside our GPLv3 code. Other dependencies keep their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).

### Publishing

Push source, build scripts, documentation, and license notices to Git. Keep Linux images outside Git history. The current runtime is SystemRescue 13.02, with a roughly 16MB kernel, 184MB initramfs, and 1.15GB compressed root filesystem. It has not been trimmed into a custom minimal distribution. The kernel alone cannot run the collector.

The initial release contains source and build scripts, **not a hosted SystemRescue image**. The builder downloads and verifies the official ISO, then assembles the package locally. A complete boot package can later be attached to GitHub Releases once its corresponding source, build materials, and license notices are prepared. GitHub blocks files over 100MiB in ordinary Git repositories; see its [large-file documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

See [docs/publishing.md](docs/publishing.md) for publishing steps. Personal EFI folders, hardware reports, and machine identifiers are excluded from the source package.
