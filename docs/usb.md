# Hackintosh AutoEFI

## 中文

从电脑固件的启动菜单选择这块 U 盘的 UEFI 启动项。

- 第一项 `Collect hardware automatically - offline Linux`：采集硬件，保存到 U 盘，然后自动关机。不需要联网或输入命令。
- 第二项 `macOS / OpenCore - existing EFI`：继续使用原有 OpenCore。
- 第三项：采集黑屏时尝试的基础显示模式，可能无法读取完整内屏信息。

关机后拔出 U 盘，查看 `HardwareReports/时间-编号/Readiness.json`。有缺项时先复核，再把同目录的 `Report.json` 和 `ACPI/` 用于 OpCore-Simplify。不要只看 JSON 格式是否通过。

需要关闭 Secure Boot。固件中直接指向 OpenCore 的旧启动项会绕过本菜单。

本工具不挂载内置磁盘的文件系统。采集报告可能包含设备序列号，公开分享前请脱敏。Linux 是否能读全还取决于具体硬件；目前不能保证与 Windows 原生采集完全一致。

原启动文件备份在 U 盘根目录的 `HardwareCollector-backup-时间/`。要恢复直接启动 OpenCore，把其中 `BOOTx64-original.efi` 复制回 `EFI/BOOT/BOOTx64.efi`。

详细流程见同目录的 `design.md`，第三方许可见 `THIRD_PARTY.md`；本项目自己的许可见 `LICENSE`。

项目自己的代码采用 GPL-3.0-only，版权和授权范围见 `NOTICE`。第三方组件保留原许可。

## English

Select this USB's UEFI entry in the firmware boot menu. Disable Secure Boot first.

- First entry: automatically collect hardware, save the report to the USB, and shut down. No network connection or commands are needed.
- Second entry: start the USB's existing OpenCore.
- Third entry: basic-display fallback if normal collection has a display problem. Panel information may be missing.

After shutdown, open `HardwareReports/timestamp-id/Readiness.json`. Review missing fields before using `Report.json` and the matching `ACPI/` with OpCore-Simplify. A valid report format does not establish completeness or equivalence to a Windows capture. Reports can contain serial numbers; redact them before public sharing.

The collector does not mount internal disk filesystems. To restore direct OpenCore boot, copy `BOOTx64-original.efi` from `HardwareCollector-backup-timestamp/` back to `EFI/BOOT/BOOTx64.efi`.

Project code is GPL-3.0-only; see `LICENSE` and `NOTICE`. Third-party licenses remain in effect; see `THIRD_PARTY.md`. Collection details are in `design.md`.
