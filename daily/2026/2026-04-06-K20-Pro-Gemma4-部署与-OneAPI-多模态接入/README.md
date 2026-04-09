# 2026-04-06 K20 Pro Gemma 4 部署与 OneAPI 多模态接入

## 背景

这次记录的是一整套从手机侧本地部署，到局域网服务化，再到接入 `one-api` 的过程。

涉及的主要设备如下：

- 手机：Redmi K20 Pro，Snapdragon 855，12 GB RAM
- 手机系统环境：Android + 原生 Termux
- 手机 SSH：`u0_a247@192.168.2.202:8022`
- 中转服务器：Debian 服务器 `192.168.2.200`
- `one-api` 部署位置：`192.168.2.200`

目标不是只把模型“跑起来”，而是把它整理成一条可复用的调用链：

1. 手机上本地运行 Gemma 4
2. 文本能力通过 Ollama 暴露服务
3. 多模态能力通过自定义 bridge 转成 OpenAI 兼容接口
4. 最终接到 `one-api`

## 总体结论

截至 2026-04-09，这套链路已经可以工作：

- K20 Pro 上的 Gemma 4 文本推理可用
- K20 Pro 上的 Gemma 4 多模态推理可用
- `one-api` 已可以通过 Ollama 渠道调用文本模型
- `one-api` 也可以通过自建 bridge 调用多模态模型

当前多模态模型名为：

- `gemma4-vl`

当前多模态 bridge 地址为：

- `http://192.168.2.200:18080/v1`

## 第一阶段：在 K20 Pro 上部署 Gemma 4

### 1. 基础环境

Termux 中准备了以下基础工具：

- `termux-wake-lock`
- `clang`
- `cmake`
- `git`
- `wget`

这样做的主要目的是避免长时间编译和模型加载过程中被系统休眠打断。

### 2. 编译 llama.cpp

最初在手机上编译的是：

- `llama-llava-cli`

后来在验证过程中发现它已经被废弃，当前真正可用的是：

- `llama-mtmd-cli`

因此后续又补编了：

- `~/llama.cpp/build/bin/llama-mtmd-cli`

多模态链路最终依赖的就是这个可执行文件。

### 3. 模型文件

这次实际使用的是 Gemma 4 E4B 的量化模型和配套视觉投影文件。

手机上的最终整理路径如下：

- 主模型：`~/models/gemma-4-main.gguf`
- 视觉投影：`~/models/mmproj-vision.gguf`

文件大小大致为：

- 主模型约 `5.3 GB`
- `mmproj` 约 `946 MB`

从 `llama.cpp` 输出看，模型元数据里显示的参数量大约是：

- `7.52B`

也就是说，这并不是一个特别轻的小模型。

## 第二阶段：文本服务改用 Ollama

### 1. 为什么没有直接用 llama-server

最开始尝试过 `llama-server`，但在 Android / Termux 环境里兼容性不理想。

核心原因是：

- `llama-server` 依赖的一部分实现会用到 `posix_spawn`
- Android 的 Bionic libc 对这一点兼容不好

因此最终改为：

- `Ollama 0.20.0`

### 2. 文本模型服务方式

在 Termux 中安装并启动 Ollama 后，文本链路变成：

```bash
termux-wake-lock
ollama serve > ~/ollama.log 2>&1 &
ollama run gemma4
```

对外服务地址为：

- Termux 本机：`http://localhost:11434`
- 局域网访问：`http://192.168.2.202:11434`

### 3. 文本验证

最直接的测试方式是：

```bash
ollama run gemma4 "ping"
```

文本推理验证通过，说明手机侧的 Ollama 服务可用。

## 第三阶段：打通多模态推理

### 1. 关键命令参数

Gemma 4 多模态在 `llama.cpp` 里有两个非常关键的条件：

- 要使用 `llama-mtmd-cli`
- 要带 `--jinja`

实际测试命令的思路如下：

```bash
~/llama.cpp/build/bin/llama-mtmd-cli \
  --jinja \
  --no-warmup \
  -m ~/models/gemma-4-main.gguf \
  --mmproj ~/models/mmproj-vision.gguf \
  --image /path/to/image.png \
  -p "请描述这张图片中的主要内容。" \
  -c 2048 \
  -n 96 \
  -t 8
```

### 2. 实测现象

多模态推理是能跑通的，但并不轻松。

观察到的典型情况：

- CPU 基本接近吃满 8 核
- 多模态请求经常要 2 分钟以上
- 图像编码和解码都很重
- 会明显消耗内存，并可能开始动用 swap

因此这套方案更像是“可验证、可调用、可长期折腾”的方案，而不是低延迟在线推理方案。

## 第四阶段：接入 one-api 文本渠道

### 1. 直接接 Ollama

在 `one-api` 侧，文本链路优先选用了 Ollama。

调用关系如下：

```text
one-api -> Ollama -> K20 Pro Gemma 4
```

### 2. 遇到的问题

`one-api` 现有前端里，Ollama 渠道只显示模型名，不显示 `base_url` 输入项。

这会导致：

- 不能直接在界面里把 `192.168.2.202:11434` 作为 Ollama 上游地址填进去

### 3. 处理方式

因此对 `one-api` 前端做了一个小补丁：

- 让 Ollama 渠道也显示 `base_url`

部署时没有覆盖原有镜像，而是保留了回滚方案：

- 运行中的自定义镜像：`one-api:ollama-baseurl-warm-20260408`
- 保留的官方回滚容器：`one-api-rollback-20260408-221943`
- 回滚镜像来源：`justsong/one-api`

这样即使自定义镜像有问题，也可以无损切回原方案。

## 第五阶段：给 one-api 增加多模态 OpenAI 兼容入口

### 1. 为什么不能直接让 one-api 调手机上的 llama-mtmd-cli

原因很简单：

- `llama-mtmd-cli` 不是 OpenAI 风格 HTTP 服务
- 它本身是 CLI 工具
- `one-api` 需要的是标准接口，例如 `/v1/chat/completions`

所以需要一个中间层来做协议转换。

### 2. 最终架构

最终采用的是一条三段式链路：

```text
one-api -> OpenAI-compatible bridge -> SSH -> K20 Pro llama-mtmd-cli
```

其中文本探活和图片推理分别走不同路径：

```text
文本探活/普通文本:
one-api -> bridge -> Ollama -> K20 Pro

图片请求:
one-api -> bridge -> SSH/SCP -> llama-mtmd-cli -> K20 Pro
```

## 第六阶段：bridge 的部署方式

### 1. 部署位置

bridge 没有做成 Docker 容器，而是直接部署在 Debian 服务器 `192.168.2.200` 上。

部署目录：

- `/root/projects/k20-mm-bridge`

运行方式：

- `systemd` 常驻服务

服务名：

- `k20-mm-bridge`

监听地址：

- `0.0.0.0:18080`

### 2. bridge 提供的接口

当前 bridge 支持：

- `GET /healthz`
- `GET /v1/models`
- `POST /v1/chat/completions`

当前限制：

- 仅支持 `stream=false`
- 单次只处理一个请求
- 当前实现按单图输入处理

### 3. bridge 的工作机制

#### 文本请求

- 如果请求不带图片，bridge 会把它转发到手机上的 Ollama
- 如果手机上的 Ollama 没有运行，bridge 会通过 SSH 自动尝试拉起 `ollama serve`

#### 多模态请求

- bridge 先接收 OpenAI 风格请求
- 提取文本和图片 URL
- 把图片下载到 `192.168.2.200`
- 再通过 `scp` 把图片传到手机的临时目录
- 然后通过 `ssh` 在手机上调用 `llama-mtmd-cli`
- 对输出进行清洗，只保留最终答案
- 最后再封装回 OpenAI 风格响应

## 第七阶段：bridge 调试过程中的关键问题

### 1. one-api 渠道测试超时

`one-api` 的渠道测试提示词并不是随便一句对话，而是固定的：

```text
Output only your specific model name with no additional text.
```

如果让这类测试请求真的去走一次完整的手机文本推理，就会慢，而且容易超时。

因此 bridge 额外做了一个“短路探活”逻辑：

- 如果识别到这是 `one-api` 的测试提示词
- 且请求里没有图片
- 就直接返回模型名 `gemma4-vl`

这样：

- `one-api` 渠道测试会秒过
- 不影响真实多模态推理路径

### 2. llama-mtmd-cli 输出不干净

`llama-mtmd-cli` 的输出并不是一个天然干净的 JSON 或单行文本，调试时遇到了几类问题：

- 有时会输出 `thought`
- 有时前后带很多 `llama.cpp` 日志
- 某些测试图过小，例如 `1x1` 图片，会直接触发断言失败

后来做了几件事来稳定输出：

- 去掉会吞掉正常回答的 `--log-disable`
- 补一个 system prompt，要求“只输出最终答案”
- 增加输出清洗逻辑，过滤 `llama.cpp` 日志行
- 用正常尺寸图片验证，而不是超小图片

最终多模态返回已经能稳定得到可用正文。

## 第八阶段：最终验证结果

### 1. bridge 自检接口

```bash
curl http://127.0.0.1:18080/healthz
curl http://127.0.0.1:18080/v1/models
```

结果正常。

### 2. one-api 渠道测试

文本探活已经可以秒回：

```text
gemma4-vl
```

### 3. 多模态真实测试

实际测试图片使用了一个正常尺寸的示例图，bridge 最终返回：

```text
图片中显示的是单词“HELLO”的黑色无衬线大写字母。
```

这说明从 `one-api` 视角看：

- bridge 已经是一个可调用的 OpenAI 兼容多模态后端

## one-api 中的配置方式

如果要把这套多模态链路接入 `one-api`，可以按下面方式配置：

- 渠道类型：`OpenAI`
- Base URL：`http://192.168.2.200:18080/v1`
- 模型名：`gemma4-vl`

而文本模型仍然建议继续走已经可用的 Ollama 渠道。

## 目录说明

当前目录除了这篇记录，还附带了 bridge 的相关代码：

- `code/k20-mm-bridge/server.py`
- `code/k20-mm-bridge/bridge.env.example`
- `code/k20-mm-bridge/k20-mm-bridge.service`
- `code/k20-mm-bridge/README.md`

这些文件就是当前多模态 OpenAI 兼容桥接方案的核心实现。

## 最终结论

这次折腾最终完成了三件事：

1. 在 K20 Pro 上把 Gemma 4 文本和多模态都跑通了
2. 把文本能力接进了 `one-api`
3. 额外实现了一个 bridge，把手机上的多模态 CLI 包成了 OpenAI 兼容接口，再接入 `one-api`

对这台 K20 Pro 来说，这不是一套高吞吐、低延迟的生产方案，但已经是一套完整、可复用、可继续扩展的局域网本地 AI 方案。
