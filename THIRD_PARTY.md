# 第三方组件

| 组件 | 使用范围 | 许可证 / 来源 |
| --- | --- | --- |
| Hardware-Sniffer | 固定版本完整源码，Linux 采集入口 | BSD-3-Clause，`package/HardwareCollector/vendor/Hardware-Sniffer/LICENSE`；[上游](https://github.com/lzhoang2801/Hardware-Sniffer) |
| OpCore-Simplify | `Scripts/report_validator.py`、`Scripts/utils.py` | BSD-3-Clause，`package/HardwareCollector/vendor/OpCore-Simplify/LICENSE`；[上游](https://github.com/lzhoang2801/OpCore-Simplify) |
| GNU GRUB | 使用本机工具构建 UEFI 菜单 | GPL-3.0-or-later；[GNU 源码与许可证](https://www.gnu.org/software/grub/)；发行版补丁应从对应发行版获取 |
| Linux kernel | SystemRescue 中的独立操作系统内核 | GPL-2.0-only，带 syscall note；[内核许可说明](https://docs.kernel.org/process/license-rules.html) |
| SystemRescue | 外部下载的 Linux 启动环境 | 镜像内各组件分别授权；[项目与源码说明](https://www.system-rescue.org/)，[官方镜像](https://www.system-rescue.org/Download/) |

本项目自行编写的代码和文档使用 GPL-3.0-only。上游原始版权和许可证随源码保留，不把第三方组件统一改标为 GPLv3。BSD-3-Clause 组件的版权、条件与免责声明必须保留；其独立使用仍按原许可处理。

BSD-3-Clause 可以理解为“可以拿去用、改、商用，甚至闭源，但要保留原声明，也不能冒用作者名义宣传”。它不要求别人公开修改版。我们保留两份上游 LICENSE，在第三方说明中列出来源；本项目自己的代码继续用 GPLv3。[BSD 原文](https://opensource.org/license/bsd-3-clause)、[GPL 与 BSD 兼容性说明](https://www.fsf.org/blogs/licensing/relicensing-versus-compatibility)。

本项目首版只分发源码和构建工具，不托管 Linux 或 GRUB 二进制。构建脚本从官方站点下载固定版本的 SystemRescue，校验后在使用者本机组装。

当前源码包不包含 SystemRescue 镜像或 GRUB 二进制。公开发布完整启动包时，除了项目源码，还要准备所分发 GPL 组件的对应源码、必要构建脚本与各自许可材料；仅放一个上游首页链接不能代替这些材料。[SystemRescue 源码构建说明](https://www.system-rescue.org/manual/Building_SystemRescue_from_Source/) 列出了其构建仓库及 Arch 软件包源码的取得方式。

## English

Original code and documentation in this project are licensed under GPL-3.0-only. Vendored Hardware-Sniffer and OpCore-Simplify code retains its BSD-3-Clause copyright, conditions, and disclaimer. Independent reuse of those upstream components remains governed by their original licenses.

BSD-3-Clause allows use, modification, commercial use, and closed-source redistribution. It requires retaining the notices and prohibits claiming upstream endorsement without permission. It does not require modified versions to be open source. We keep the upstream LICENSE files; our own code uses GPLv3. See the [BSD text](https://opensource.org/license/bsd-3-clause) and [FSF compatibility explanation](https://www.fsf.org/blogs/licensing/relicensing-versus-compatibility).

The initial release distributes source and build tools only, with no hosted Linux or GRUB binaries. The builder downloads the pinned official SystemRescue image, verifies it, and assembles the package locally.

GRUB, the Linux kernel, and the SystemRescue environment are separate third-party components with their own licenses. The kernel remains GPL-2.0-only with the syscall note. They are not relicensed by the project's LICENSE file.

The source archive does not include the Linux ISO or GRUB binaries. Before distributing a complete boot package, prepare the corresponding source and required build materials for the GPL binaries actually included, along with their license notices. An upstream homepage link alone is not a substitute. See the [SystemRescue source build instructions](https://www.system-rescue.org/manual/Building_SystemRescue_from_Source/) and [docs/publishing.md](docs/publishing.md).
