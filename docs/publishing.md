# 发布 / Publishing

## 中文

项目名为 **Hackintosh AutoEFI**，仓库名 `Hackintosh-AutoEFI`。首版只发布源码，不托管 SystemRescue 镜像。

### 源码仓库

在 GitHub 创建一个空仓库，不自动添加 README 或许可证。进入本项目源码目录后执行，替换账号和仓库地址：

```sh
git init
git add .
git diff --cached --stat
git commit -m "Initial source release"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/Hackintosh-AutoEFI.git
git push -u origin main
```

提交前检查暂存列表。应包括采集脚本、构建和安装脚本、测试、固定版本的第三方源码、README 与许可文件。不能包含实际硬件报告、个人 EFI、设备序列号、ISO、测试磁盘或缓存。`.gitignore` 已排除这些常见构建产物，但仍要检查实际提交内容。

GitHub 普通仓库拒绝超过 100MiB 的文件，不能直接把约 1.3GB 的 Linux 运行环境推进去。构建脚本会从官方站点下载固定版本的 SystemRescue ISO 并校验 SHA256，也支持 `--iso` 使用本地镜像。

### 可下载启动包

可运行的包需要 GRUB EFI、内核、initramfs、压缩根文件系统和采集器，单独一个 Linux 内核不够。完整包应放在 GitHub Releases 的附件中，不放进 Git 历史；同时提供 SHA256 和支持范围说明。参见 [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。

公开发布完整包之前，要完成第三方二进制的对应源码准备：

- SystemRescue 的确切版本、构建仓库与构建配置，以及实际软件包对应源码。
- 实际使用的 GRUB 版本、发行版补丁、构建脚本和配置。
- Linux 内核的对应源码、补丁和配置；其他软件按各自许可证处理。
- 本项目的源码、完整许可证、第三方版权声明，以及取得对应材料的明确方式。

这些材料需要与分发的二进制版本匹配。不能把本站 Git 仓库的自动 Source code.zip 当成整个 Linux 环境的源码，也不能只附一个上游首页链接就称为已完成。源码可以与启动包放在同一次 Release，分卷提供；具体分发安排要符合各组件许可。

当前已经验证的启动包是本地测试产物，**第三方完整对应源码发布材料尚未整理完成**，不能把它直接标成可公开发布的完整发行版。可以先发布不含这些二进制的项目源码和构建说明。

参考：[GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#UnchangedJustBinary)、[SystemRescue 源码构建](https://www.system-rescue.org/manual/Building_SystemRescue_from_Source/)、[Linux 内核许可](https://docs.kernel.org/process/license-rules.html)。

## English

The project name is **Hackintosh AutoEFI**, with repository name `Hackintosh-AutoEFI`. The initial release is source-only and does not host the SystemRescue image.

### Source repository

Create an empty GitHub repository without an automatically generated README or license. Run the commands above from this source directory, replacing `YOUR_ACCOUNT` and the repository URL.

Review the staged file list before committing. Include collector code, build/install scripts, tests, pinned third-party sources, documentation, and license notices. Exclude real hardware reports, personal EFI folders, machine identifiers, ISOs, virtual disks, and caches. `.gitignore` helps but does not replace this review.

Ordinary GitHub repositories block files over 100MiB. Keep the Linux runtime outside Git history. The builder downloads the pinned official SystemRescue ISO and verifies its SHA256. Users may also pass a local ISO with `--iso`.

### Downloadable boot packages

A working boot package needs the GRUB EFI loader, kernel, initramfs, compressed root filesystem, and collector. The kernel alone is insufficient. Publish complete packages as GitHub Release assets, with hashes and a description of tested hardware.

Before publicly distributing the runtime binaries, prepare their matching corresponding source, required build/configuration materials, and license notices. That includes the exact SystemRescue build and package sources, the GRUB source with distribution patches, and the Linux kernel source, patches, and configuration. The project's automatic GitHub source archive does not contain the source for the entire Linux environment. A link to an upstream homepage alone is not enough.

The tested local boot package is **not yet prepared as a public binary distribution**: its complete third-party source distribution materials remain to be assembled. A source-only release with build instructions can be published first.

Sources may be supplied with the same release, split into assets as needed, using arrangements permitted by the respective licenses. See the [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#UnchangedJustBinary), [SystemRescue source instructions](https://www.system-rescue.org/manual/Building_SystemRescue_from_Source/), and [kernel licensing rules](https://docs.kernel.org/process/license-rules.html).
