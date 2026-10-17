# 采集流程和版本

## 为什么用 Linux

UEFI 能读到 PCI、SMBIOS、ACPI，但仅靠这些不能稳定拿到已绑定的音频 codec、DRM 内屏连接、输入设备和 USB 蓝牙的信息。这里让 GRUB 直接启动 SystemRescue，再运行采集器。它不经过 OpenCore，也不依赖目标机器上的操作系统。

顺序为：UEFI → GRUB 菜单 → Linux → 加载常见设备模块 → Hardware-Sniffer → 实测修正 → 校验 → 保存 → 关机。每次结果放进独立目录。采集失败会保留错误并停在控制台，不会自动生成 EFI。

关闭了 NetworkManager 和 sshd；启动参数包含 `nomdlvm noswap`。只把启动 U 盘重新挂载为可写。完整自动采集设置了 240 秒超时，个别无法完成的机器会保存失败诊断。

## 固定上游版本

- Hardware-Sniffer：`403cc25bc14be65c45a1e0ea9cfd3567103e9a73`
- OpCore-Simplify 校验器：`f0e1e441bb455c33e9695a9c9c50e8ca931d4de8`
- SystemRescue：13.02 amd64
- 镜像 SHA256：`ad4d670b72859d887c7960142a9a9d36a3e50446694a035e254442f65d6e7572`

`vendor/Hardware-Sniffer` 保留上游源文件。`vendor/OpCore-Simplify` 只包含校验器及其依赖 `utils.py`，不包含 EFI 生成器。两个项目都有名为 `Scripts` 的 Python 包，因此校验器在独立子进程中运行。

## 本地修正

- 按 CPU package/core 拓扑统计物理核心，避免把逻辑线程当作物理核数。
- Secure Boot 按 efivarfs 的二进制结构读取，跳过四字节属性头；读取失败保留未知。
- PCI 根路径来自 ACPI 根桥 UID，不能把 PCI segment 号直接写成 `PciRoot`。
- PCI 数字 class 和 VID/PID 用来枚举设备，设备是否绑定驱动不决定它是否存在。
- 音频读取实际 HDA codec ID，并单独记录所属 PCI 控制器 ID。HDA 控制器 ID 不能当成 Realtek codec ID。
- 内屏和外接屏读取 DRM 连接、GPU PCI 位置、模式列表和 EDID。报告中的分辨率取最高面积的可用模式，不保证等同 Windows 当前显示模式。
- ReBAR 尝试读取 PCIe 扩展配置中的实际控制值，不根据 BAR 的地址大小猜测；无法判断时标记复核。
- 上游可选主板 DMI 字符串为空时可能抛异常，因此使用可读的系统 DMI，并按上游 PCI 数据库补查芯片组。

所有修正都在包装层中完成，同时保存上游原始输出、异常和证据，不修改 vendored 源码。

## 与生成器的边界

OpCore-Simplify 的驱动选择不仅取决于硬件，还取决于目标 Darwin 版本、声音和无线选项、OCLP 路径以及下载的资源版本。例如缺少 Sound 条目可能跳过声音选项，从而改变 AMFIPass 选择；不能为了得到某个 kext 而伪造声卡。

`generation_ready` 只是本工具当前检查项的结果。`windows_equivalence_verified` 固定为 false：尚未对同一机器、同一固件、同一设备状态的 Windows/Linux 报告做逐项实测认证。成功生成或通过校验不能代替这一步。

## 测试范围

单元测试覆盖物理核心、Secure Boot、PCI UID、HDA codec 与控制器、ReBAR 可读性。QEMU 完整启动测试检查 UEFI 引导、autorun、实际设备采集、USB 文件写回和自动关机。QEMU 的未知 GPU/CPU 或缺失固件变量仍应触发复核，不能把测试设备硬改成受支持设备来获得通过状态。

尚不能据此宣称所有实体机器兼容。ARM、Legacy BIOS、Secure Boot 签名链、Windows 原生采集与 USB 端口映射不在当前范围内。
