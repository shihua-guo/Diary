# 2026-05-13 OpenWrt 路由器 CordCloud 升级记录

## 背景

目标是登录家里的 OpenWrt 路由器，确认设备架构，并升级 CordCloud 插件及其使用的 Mihomo Meta 核心。

路由器登录信息：

- 设备地址：`root@192.168.5.1`
- SSH 端口：`5624`
- 备注：默认 `22` 端口连接时返回 `Connection refused`

## 设备与架构确认

登录路由器后，先确认系统、设备型号和包架构。

关键结果：

- OpenWrt：`23.05.4`
- Target：`ramips/mt7621`
- 设备型号：`Xiaomi Mi Router 3G`
- CPU/系统：`MediaTek MT7621`
- OpenWrt 包架构：`mipsel_24kc`
- `uname -m`：`mips`

因此在 CordCloud 提供的架构选项中，应该选择：

- `MIPSLE`

不是：

- `ARM64(aarch64)-GL-MT3000`
- `ARMv7`
- `x86_64`

CordCloud 配置里对应的核心架构值为：

```text
linux-mipsle-softfloat
```

## 升级前状态

升级前 CordCloud LuCI 插件版本：

```text
luci-app-cordcloud - 1.0.6
```

服务状态：

```text
running
```

升级前 Mihomo Meta 核心版本：

```text
Mihomo Meta alpha-g86257fc linux mipsle with go1.25.7 Fri Feb  6 18:42:53 UTC 2026
```

路由器空间大致情况：

```text
overlayfs:/overlay  57.6M  used 32.2M  available 22.4M
/tmp                122.1M available about 120.8M
```

## 核心升级过程

CordCloud 自带脚本会从 OpenClash 的 core 分支下载对应核心。脚本根据 `DISTRIB_ARCH=mipsel_24kc` 自动映射为：

```text
linux-mipsle-softfloat
```

先通过插件脚本检查到远端 Meta 核心版本为：

```text
alpha-gd801e6b
```

直接执行插件自带核心更新脚本时，下载失败。失败原因不是架构错误，而是默认下载源返回了 GitHub/jsDelivr 限流内容：

```text
429: Too Many Requests
```

插件脚本默认尝试下载：

```text
https://cdn.jsdelivr.net/gh/vernesong/OpenClash@core/master/meta/clash-linux-mipsle-softfloat.tar.gz
```

该路径当时只下载到了一个约 `199` 字节的错误响应。

随后改用 GitHub raw 地址手动下载：

```text
https://raw.githubusercontent.com/vernesong/OpenClash/core/master/meta/clash-linux-mipsle-softfloat.tar.gz
```

下载后校验：

- 压缩包大小：约 `8.9M`
- `gzip -t`：通过
- `tar tzf`：包内文件为 `clash`
- SHA256：

```text
135096a207df321f7843bb8a2efc61e51a4d45f861645040ad43c79a5e65df9b
```

解压后先在临时路径验证新核心：

```text
Mihomo Meta alpha-gd801e6b linux mipsle with go1.25.9 Wed Apr  8 15:45:05 UTC 2026
```

确认可执行后，将旧核心备份到临时路径，并替换：

```text
/etc/cordcloud/core/clash_meta
```

然后重启 CordCloud 服务。

重启输出中出现过一行：

```text
sh: out of range
```

但服务随后正常启动，最终确认状态为：

```text
running
```

核心升级后的版本：

```text
Mihomo Meta alpha-gd801e6b linux mipsle with go1.25.9 Wed Apr  8 15:45:05 UTC 2026
```

## LuCI 插件升级过程

随后确认需要升级的是 LuCI 插件包本身。安装包地址为：

```text
https://dl.cordcloud.us/client/luci-app-cordcloud_1.0.8_mipsle.ipk
```

路由器直接用 `curl` 下载该地址时失败，错误为 TLS 握手中断：

```text
curl: (35) ssl_handshake returned - mbedTLS: (-0x7280) SSL - The connection indicated an EOF
```

因此改为先在本机下载，再传到路由器。

本机下载路径：

```text
C:\tmp\luci-app-cordcloud_1.0.8_mipsle.ipk
```

文件大小：

```text
17350543 bytes
```

上传到路由器后读到的 SHA256：

```text
fa9d761e795937ba7bb1f4f0ef73e738ec9454c7f5ef0015f542f9b1d79959b4
```

安装前用 `opkg --noaction` 做预检查，确认会从 `1.0.6` 升级到 `1.0.8`：

```text
Upgrading luci-app-cordcloud on root from 1.0.6 to 1.0.8...
```

### 第一次安装失败

第一次正式安装时，使用了 `/tmp/luci-app-cordcloud_1.0.8_mipsle.ipk` 作为包路径。

安装过程中出现失败：

```text
wfopen: /tmp/luci-app-cordcloud_1.0.8_mipsle.ipk: No such file or directory.
pkg_get_installed_files: Error extracting file list from /tmp/luci-app-cordcloud_1.0.8_mipsle.ipk.
opkg_install_pkg: Failed to determine obsolete files from previously installed luci-app-cordcloud
opkg_install_pkg: Failed to extract maintainer scripts for luci-app-cordcloud. Package debris may remain!
```

失败后 `opkg` 状态短暂变成：

```text
Package: luci-app-cordcloud
Version: 1.0.6
Status: deinstall user installed
Architecture: all
```

但服务和实际文件仍在，CordCloud 仍能运行。

判断原因：安装过程中 `/tmp` 下原安装包被清理，导致 `opkg` 后续步骤找不到原始 `.ipk`。

### 第二次安装成功

重新将安装包上传为更短路径：

```text
/tmp/cc108.ipk
```

再次执行安装：

```text
opkg install /tmp/cc108.ipk
```

这次安装成功，输出中有配置文件冲突提示：

```text
Existing conffile /etc/config/cordcloud is different from the conffile in the new package.
The new conffile will be placed at /etc/config/cordcloud-opkg.

Existing conffile /etc/cordcloud/custom/cordcloud_custom_fake_filter.list is different from the conffile in the new package.
The new conffile will be placed at /etc/cordcloud/custom/cordcloud_custom_fake_filter.list-opkg.
```

这表示原配置被保留，新包默认配置被另存为 `*-opkg` 文件。

## 升级后状态

最终确认 LuCI 插件版本：

```text
Package: luci-app-cordcloud
Version: 1.0.8
Status: install user installed
Architecture: all
```

服务状态：

```text
running
```

核心版本：

```text
Mihomo Meta alpha-gd801e6b linux mipsle with go1.25.9 Wed Apr  8 15:45:05 UTC 2026
```

关键配置仍保持：

```text
cordcloud.config.enable='1'
cordcloud.config.core_version='linux-mipsle-softfloat'
cordcloud.config.core_type='Meta'
cordcloud.config.release_branch='master'
cordcloud.config.github_address_mod='0'
```

升级后空间：

```text
overlayfs:/overlay  57.6M  used 41.9M  available 12.7M
/tmp                122.1M available about 121.7M
```

## 备份

升级后重新备份了 CordCloud 配置：

```text
/etc/config/cordcloud
/etc/cordcloud/custom
```

本机备份位置：

```text
C:\tmp\cordcloud-config-backup-after-1.0.8.tar.gz
```

注意：升级过程中曾经放在路由器 `/tmp` 下的临时备份、旧核心备份和安装包，后来被安装脚本或手动清理移除。不要依赖 `/tmp` 作为长期备份位置。

## 经验记录

- 这台路由器是 `ramips/mt7621`，选择架构时应选 `MIPSLE`。
- CordCloud 核心下载默认源可能遇到 jsDelivr/GitHub 限流，表现为下载到 `429: Too Many Requests`。
- 路由器自带 `curl` 访问 `dl.cordcloud.us` 时可能因 TLS 库问题握手失败，可以改为本机下载后上传。
- 安装 `.ipk` 前先用 `opkg install <file> --noaction` 预检查，能提前确认升级路径。
- 不要在升级过程中让安装包依赖容易被脚本清理的长路径临时文件；这次第二次使用 `/tmp/cc108.ipk` 安装成功。
- `opkg` 遇到配置文件差异时，会保留现有配置，并将新默认配置另存为 `*-opkg`。
