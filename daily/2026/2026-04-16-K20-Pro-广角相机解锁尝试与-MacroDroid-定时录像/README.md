# 2026-04-16 K20 Pro 广角相机解锁尝试与 MacroDroid 定时录像

## 背景

这次折腾的目标本来有两个：

1. 让已经 `Root + Magisk` 的 `Redmi K20 Pro (raphael)` 对第三方应用开放广角镜头
2. 把这台手机继续作为一个稳定的监控节点，在指定时间段内自动开始和停止录像

最初的设想是：

- 解开 MIUI 对辅助摄像头的限制
- 让 `tinyCam Pro`、`IP Webcam Pro`、`Open Camera` 之类的应用直接看到多出来的广角镜头
- 最后再给 `tinyCam Pro` 配一个定时录像

实际排查下来，第一部分只成功了一半：

- 系统层的白名单限制确实解开了
- 但这几个目标应用并没有都把广角镜头作为独立选项展示出来

所以最终可落地的方案变成了：

- 系统层完成辅助摄像头白名单放开
- 认清目标应用自身的镜头选择限制
- 录像调度层改用 `MacroDroid -> tinyCam Pro Background mode`

## 设备环境

- 机型：`Redmi K20 Pro Premium Edition`
- 代号：`raphael`
- Android：`11`
- MIUI：`V12.5`
- Root：`Magisk`
- 连接方式：`ADB over TCP`

设备识别时的核心信息如下：

```bash
adb shell getprop ro.product.device
# raphael

adb shell getprop ro.build.version.release
# 11

adb shell getprop ro.miui.ui.version.name
# V125

adb shell su -c 'id'
# uid=0(root) gid=0(root) groups=0(root) context=u:r:magisk:s0
```

## 第一阶段：确认广角受限点到底在哪

### 1. 先看 Camera Service 暴露了多少个 camera device

通过：

```bash
adb shell dumpsys media.camera
```

可以看到系统里总共有 `11` 个公开 camera device，而不是只有前后两颗。

这一步很关键，因为它说明：

- 硬件本身没有“彻底隐藏”
- Camera HAL 已经把多个 ID 暴露给了系统
- 问题更可能出在 MIUI 的厂商白名单逻辑，而不是更底层的驱动缺失

### 2. 直接查厂商属性

进一步看相机相关属性：

```bash
adb shell su -c 'getprop | grep -i camera'
```

排查中最关键的一项是：

```text
vendor.camera.aux.packagelist=org.codeaurora.snapcam,com.xiaomi.cameratest,com.xiaomi.factory.mmi,com.xiaomi.runin
```

这说明 MIUI 确实有一个辅助摄像头包名白名单机制。

也就是说：

- 摄像头并没有完全消失
- 只是厂商默认只允许少数包名调用辅助镜头

### 3. 设备上三颗后摄的识别结果

通过 `persist.vendor.camera.*` 属性，实际识别到了三颗后摄模块：

- 主摄：`IMX586`
- 长焦：`OV8856`
- 广角：`S5K3L6`

对应的属性大致如下：

```text
persist.vendor.camera.rearMain.info=/vendor/lib64/camera/com.qti.sensormodule.raphael_ofilm_imx586.bin
persist.vendor.camera.rearTele.info=/vendor/lib64/camera/com.qti.sensormodule.raphael_ofilm_ov8856.bin
persist.vendor.camera.rearUltra.info=/vendor/lib64/camera/com.qti.sensormodule.raphael_ofilm_s5k3l6.bin
```

所以从硬件角度看，广角是确定存在的。

## 第二阶段：用 Magisk 模块放开辅助摄像头白名单

### 1. 为什么不直接改 system/vendor

虽然机器已经 `Root`，但这次没有直接去改真实分区，而是优先用了 `Magisk systemless` 方案。

这样做的优点是：

- 修改更集中
- 回滚更容易
- 升级系统或排查问题时更好处理

### 2. 模块做了什么

自定义了一个非常小的 Magisk 模块，只覆盖一件事：

- 在启动时重写 `vendor.camera.aux.packagelist`
- 同时写入 `persist.vendor.camera.aux.packagelist`

核心逻辑就是：

```sh
resetprop vendor.camera.aux.packagelist "$PACKAGE_LIST"
resetprop persist.vendor.camera.aux.packagelist "$PACKAGE_LIST"
```

### 3. 模块最终放开的包名

一开始尝试把更多应用都加进去，但后来发现这个属性有长度上限，超长后写入会失败。

最终为了兼容 `tinyCam Pro`，保留的是这四个：

- `com.pas.webcam`
- `com.pas.webcam.pro`
- `net.sourceforge.opencamera`
- `com.alexvas.dvr.pro`

也就是：

```text
com.pas.webcam,com.pas.webcam.pro,net.sourceforge.opencamera,com.alexvas.dvr.pro
```

这里顺带记录一个实际坑点：

- `vendor.camera.aux.packagelist` 在这台设备上的可用长度大约只有 `91` 个字符左右
- 因此不能无限追加包名
- 为了把 `tinyCam Pro` 加进去，最终把 `TimeLapseCam` 从白名单里移除了

### 4. 启动后校验

模块安装并重启后，实际校验结果是：

```bash
adb shell su -c 'getprop vendor.camera.aux.packagelist'
adb shell su -c 'getprop persist.vendor.camera.aux.packagelist'
```

两条都变成：

```text
com.pas.webcam,com.pas.webcam.pro,net.sourceforge.opencamera,com.alexvas.dvr.pro
```

这说明系统层白名单已经被稳定覆盖。

## 第三阶段：确认广角对应的 camera ID

为了判断应用究竟有没有机会拿到广角镜头，需要把 `dumpsys media.camera` 里的每个 ID 再拆开看。

重点关注 `android.lens.info.availableFocalLengths`。

整理后得到的后摄结论如下：

- `ID 0`：主摄，焦距约 `4.77 mm`
- `ID 20`：长焦，焦距约 `5.54 mm`
- `ID 21`：广角，焦距约 `2.04 mm`

因此：

- 这台机器的广角不是猜测存在
- 它实际上已经作为 `camera ID 21` 暴露出来了

这一步很重要，因为后面如果某个应用仍然没有“广角镜头”入口，那么问题就更可能在应用层，而不是系统层。

## 第四阶段：为什么应用里还是看不到广角

这部分是这次折腾里最容易误判的地方。

### 1. Open Camera

`Open Camera` 并不是一定会自动显示所有镜头。

实际读取它的偏好配置时，看到它当前还是：

```text
preference_camera_api_old
```

也就是说它当时仍然在用旧相机接口，而不是 `Camera2 API`。

在这种模式下：

- 很多多镜头特性本来就不会正常显示
- 即使系统底层已经放开辅助摄像头，前台 UI 也不一定给出独立入口

补充一点：

在实际日志里，第三方相机适配层已经一度枚举到了完整 ID：

```text
[0, 1, 20, 21, 60, 61, 62, 63, 100, 101, 120]
```

这说明系统侧的“看见多镜头”其实已经成立。

### 2. tinyCam Pro

这次最核心的发现之一，是 `tinyCam Pro` 本身对“手机内部相机”的建模就比较保守。

从 APK 字符串里可以直接看到：

```text
Support for internal Android cameras (front and back)
Back camera
Front camera
```

这说明它对手机内部相机的支持方式更接近：

- 前摄
- 后摄

而不是：

- `camera ID 0`
- `camera ID 20`
- `camera ID 21`

所以即使系统已经放开白名单，`tinyCam Pro` 也未必会在 UI 里多给一个“广角镜头”选项。

### 3. IP Webcam Pro

`IP Webcam Pro` 的 APK 字符串里也主要是：

- `Front camera`
- `Rear camera`

这同样更像“前后摄切换”，而不是“任意 Camera ID 选择器”。

### 4. 结论

这一步最终得到的判断是：

- 系统层：已经放开
- Camera ID：已经存在，而且能确认 `21` 是广角
- 目标应用：并不一定提供独立广角入口

所以“还是看不到广角”并不代表前面的 Magisk 模块失败了。

## 第五阶段：从“广角执念”转向“定时录像可用”

既然 `tinyCam Pro` 这类应用并不可靠地暴露独立广角入口，那么这一阶段的重点就改成：

- 先让 `tinyCam Pro` 作为稳定的 DVR/监控节点工作起来
- 广角问题留待以后再换更底层、或者自写 `cameraId=21` 的方案

当下最实用的目标变成：

- 在计划时间段内自动开始录像
- 在计划时间段结束时自动停止录像

## 第六阶段：为什么最后选 MacroDroid，而不是继续装 Tasker

手机上已经有 `MacroDroid`，所以没有必要再额外安装 `Tasker`。

关键点在于：

- `tinyCam Pro` 提供了 `Tasker/Locale` 自动化插件接口
- `MacroDroid` 能调用兼容 `Locale/Tasker` 的插件动作

在 `tinyCam Pro` 的包和字符串里，可以确认它至少有这些自动化动作：

- `Start background mode`
- `Stop background mode`
- `Start video`
- `Stop video`
- `Start live streaming`
- `Stop live streaming`

对监控用途来说，最合适的是：

- `Start background mode`
- `Stop background mode`

而不是盯着前台界面的 `Start video`

原因是 `Background mode` 本来就是 tinyCam 的 DVR 模式，更适合：

- 熄屏运行
- 长时间后台录像
- 异常后自动恢复

## 第七阶段：tinyCam Pro + MacroDroid 定时录像的实际配置

### 1. 先在 tinyCam Pro 里把录像链路配置好

先不要急着做自动化，先保证手工点击时录像就是正常的。

建议检查这些位置：

#### Camera Settings -> Recording

这里至少确认：

- 录像目标路径已经设置
- 本地存储录像是开启的
- 录像配额已经设置

#### App Settings -> Recording Settings

这里优先检查：

- 编码器设置
- 是否录音
- 分段策略

如果只是做监控，优先追求“稳定写盘”，不要一开始就把画质和码率拉满。

#### Background mode

确认：

- 需要工作的摄像头已经勾上
- 对应摄像头的录像开关是开的

### 2. MacroDroid 里做开始录像宏

如果目标是“每天晚上 22:00 自动开始录像”，可以这样做：

#### 新建宏

- 打开 `MacroDroid`
- 点击 `添加宏`

#### 触发器

选择：

- `日期/时间`
- `时间触发器`

然后设置：

- 时间：`22:00`
- 重复：每天，或自定义工作日

#### 动作

动作里选择：

- `插件`
- `Locale/Tasker 插件`
- `tinyCam Monitor Pro`

在 tinyCam 插件动作里选：

- `Start background mode`

这一步的意义是：

- 到了设定时间，直接让 tinyCam 进入后台 DVR 模式

### 3. MacroDroid 里做结束录像宏

再新建一个宏，负责停止。

#### 触发器

- 时间：例如 `06:00`
- 重复规则与开始宏一致

#### 动作

同样走：

- `插件`
- `Locale/Tasker 插件`
- `tinyCam Monitor Pro`

这次选：

- `Stop background mode`

这样就形成了完整的录像时间窗。

### 4. 如果只想在这个时间段里“移动才录”

那就不要让它一直持续录像，而是：

#### tinyCam Pro 内部设置

在：

- `Camera Settings -> Motion Detection`

里启用：

- 移动检测
- `Record to local storage on motion`

然后 MacroDroid 仍然只负责：

- 到点进入 `Background mode`
- 到点退出 `Background mode`

这样录像开关由 motion detection 决定，而不是 24 小时写盘。

## 第八阶段：MIUI 12.5 上必须补的后台保活

如果这一步不做，调度经常会“看上去配置没问题，但第二天发现根本没执行”。

至少要处理这几个点：

### 1. MacroDroid

- 允许自启动
- 电池策略设为 `无限制`
- 允许后台弹出和后台活动

### 2. tinyCam Pro

- 允许自启动
- 电池策略设为 `无限制`
- 如果用到悬浮/后台功能，相关权限要打开

### 3. 最近任务锁定

把：

- `MacroDroid`
- `tinyCam Pro`

都锁在最近任务里，尽量降低被 MIUI 杀掉的概率。

## 最终结论

这次折腾最后可以分成两个结论来看。

### 1. 关于广角镜头

结论不是“没解开”，而是：

- 系统白名单已经放开
- 广角 `camera ID 21` 已经确认存在
- 但 `tinyCam Pro`、`IP Webcam Pro` 这类应用本身并不一定提供独立广角入口

所以暂时没有在这些应用 UI 中看到广角，不代表系统层面的改动失效。

### 2. 关于监控录像

当前最实用、最稳的方案是：

- 不继续在 `tinyCam Pro` 里强求独立广角入口
- 先用 `MacroDroid + tinyCam Pro Background mode` 把定时录像跑稳

如果后面还要继续折腾广角，建议的方向就不是继续换成别的“前后摄型”监控应用，而是：

- 找明确支持 `Camera2 camera ID` 选择的应用
- 或者直接自己写一个固定调用 `cameraId=21` 的简单录像程序

## 本次记录涉及的关键命令

### 相机与系统检查

```bash
adb devices -l
adb shell getprop ro.product.device
adb shell getprop ro.build.version.release
adb shell getprop ro.miui.ui.version.name
adb shell su -c 'id'
adb shell dumpsys media.camera
adb shell su -c 'getprop | grep -i camera'
```

### 白名单验证

```bash
adb shell su -c 'getprop vendor.camera.aux.packagelist'
adb shell su -c 'getprop persist.vendor.camera.aux.packagelist'
```

### 应用层验证思路

```bash
adb shell su -c 'pm list packages | grep -Ei "camera|cam|webcam|dvr|open"'
adb shell su -c 'cmd package resolve-activity --brief com.alexvas.dvr.pro | tail -n 1'
adb shell su -c 'dumpsys package com.alexvas.dvr.pro'
adb shell su -c 'strings /path/to/base.apk | grep -Ei "front camera|back camera|recording|background mode"'
```

## 后续待办

- 如果还想继续追广角，优先测试支持 `Camera2 cameraId` 选择的应用
- 如果 tinyCam 的稳定性达到要求，再补一条“移动检测 + 定时启停”的组合配置
- 如果最终还是要广角监控，考虑直接写一个固定打开 `cameraId=21` 的轻量录像 App
