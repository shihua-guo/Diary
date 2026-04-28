# **Linux 远程调试与红米 K20 (Raphael) 深度配置指南**

本文档总结了在 Linux 服务器环境下，通过 WiFi 对红米 K20 手机进行无线 ADB 调试的完整流程，涵盖了从基础连接到 Root 权限获取，以及实现开机自启无线调试和解锁硬件权限的进阶操作。

## **一、 无线 ADB 调试基础配置**

在未获取 Root 权限或初始配置阶段，需要通过 USB 线缆建立初始监听通道。

### **1.1 环境准备**

- **硬件：** Linux 服务器（已安装 WiFi 网卡）、红米 K20。
- **网络：** 确保两台设备连接至同一局域网（同一路由器或服务器热点）。
- **软件：** Linux 已安装 adb 命令行工具。

### **1.2 初始连接步骤**

1. 通过 USB 线连接手机，执行 adb devices 确认连接。
2. 开启手机 TCP/IP 监听端口：
   adb tcpip 5555
3. 获取手机 IP 地址（设置 -> 全部参数 -> 状态信息）。
4. 拔掉 USB 线，执行无线连接：
   adb connect [手机IP]:5555

## **二、 进阶：获取 Root 权限 (Magisk)**

对于红米 K20，获取 Root 权限是实现深度自动化的前提。文档记录了已安装 Magisk 后的状态确认及后续配置。

### **2.1 权限确认**

通过 Magisk App 界面确认：

- **Magisk 状态：** 显示具体版本号（如 30.6）即代表已成功安装。
- **超级用户菜单：** 导航栏出现“盾牌”图标，说明权限管理功能已激活。

### **2.2 终端提权**

在 ADB 环境下切换至 root 用户：

adb shell
su

*注：首次执行 su 时，需在手机屏幕点击“允许”授予 Shell 超级用户权限。*

## **三、 自动化：开机自动开启无线 ADB**

利用 Magisk 的开机自启脚本机制，解决手机重启后无线 ADB 端口自动关闭的问题。

### **3.1 创建自启脚本**

在手机的 /data/adb/service.d/ 目录下创建脚本文件：

\# 进入 root shell
adb shell
su

\# 创建并写入脚本内容
echo '#!/system/bin/sh' > /data/adb/service.d/adb_wifi.sh
echo 'setprop service.adb.tcp.port 5555' >> /data/adb/service.d/adb_wifi.sh
echo 'stop adbd' >> /data/adb/service.d/adb_wifi.sh
echo 'start adbd' >> /data/adb/service.d/adb_wifi.sh

\# 赋予可执行权限
chmod +x /data/adb/service.d/adb_wifi.sh



### **3.2 验证方式**

重启手机后，直接执行 adb connect [手机IP]:5555。若能直接连接，说明脚本运行正常。

## **四、 硬件扩展：解锁广角摄像头权限**

MIUI 系统默认限制第三方应用调用非主摄镜头，获取 Root 后可通过以下方式解锁。

| 方案类型        | 实施方法                                      | 适用场景                                   |
| --------------- | --------------------------------------------- | ------------------------------------------ |
| **Magisk 模块** | 安装“全镜头解锁”或“Camera2 API Enabler”模块。 | 全局解锁，适用于大多数第三方相机。         |
| **修改白名单**  | 修改 vendor.camera.aux.packagelist 系统属性。 | 针对特定包名的应用（如监控推流工具）授权。 |
| **包名伪装**    | 将应用包名改为 com.android.camera。           | 自有开发项目，直接欺骗系统权限检查。       |

## **五、 常见问题排查 (Troubleshooting)**

- **Connection Refused：** 确认手机 5555 端口是否开启（使用 netstat -an | grep 5555 检查），或重启 adbd 服务。
- **More than one device/emulator：** 当同时存在 USB 和 WiFi 连接时，使用 adb -s [序列号/IP] 指定目标。
- **WSL 环境问题：** WSL2 默认无法读取物理 USB，需使用 usbipd 映射或直接在 Windows 宿主机执行连接。

*文档由调试日志自动总结生成，适用于高级开发者技术参考。*
