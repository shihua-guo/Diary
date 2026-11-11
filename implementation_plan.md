# CloudCLI (Claude Code UI) 内网离线部署打包计划

## 背景

你的公司内网环境无法访问外网，无法直接 `npm install`。需要在当前有网络的 Windows 电脑上完成所有准备工作，打包成压缩包，拷贝到内网后直接运行。

## 需要你确认的关键问题

> [!IMPORTANT]
> **Q1: 内网目标机器是什么操作系统？**
> - Windows？Linux？Mac？
> - 这非常重要，因为项目依赖 `node-pty`、`better-sqlite3`、`bcrypt` 等**原生 C++ 模块**（native addons）。这些模块在 `npm install` 时会针对当前操作系统编译二进制文件。**Windows 上编译的 .node 文件无法在 Linux 上运行**，反之亦然。
> - 如果内网是 Linux，需要在 Linux 环境下做 `npm install`（或交叉编译），不能直接用 Windows 打包的 node_modules。

> [!IMPORTANT]
> **Q2: 内网机器是否已经安装了 Node.js？版本是多少？**
> - 此项目要求 **Node.js v22+**
> - 你当前 Windows 电脑的 Node.js 版本是 v24.14.0（满足要求）
> - 如果内网机器没有 Node.js，也需要一并打包 Node.js 安装包

> [!WARNING]
> **Q3: 内网机器是否有 Python 和 C++ 编译工具链？**
> - `node-pty`、`better-sqlite3`、`bcrypt` 等原生模块需要 `node-gyp` 编译
> - 如果目标也是 Windows，且 Node.js 版本一致，可以直接拷贝 node_modules（已编译好的 .node 文件）
> - 如果目标 Node.js 大版本不同，可能需要重新编译

> [!IMPORTANT]
> **Q4: 你想用哪种方式运行？**
> - **方式A：开发模式** (`npm run dev`) — 适合调试，修改代码后自动刷新
> - **方式B：生产模式** (`npm run build && npm run server`) — 性能更好，适合长期使用
> - 建议使用**方式B（生产模式）**，我会在打包前先 build 好

---

## 项目分析

| 项目 | 详情 |
|------|------|
| 项目名 | CloudCLI (原名 Claude Code UI) |
| 版本 | v1.30.0 |
| 技术栈 | React + Vite (前端) + Express (后端) + TypeScript |
| Node.js 要求 | v22+ |
| 包管理器 | npm |
| 原生 C++ 模块 | `node-pty`, `better-sqlite3`, `bcrypt` |
| npm 包名 | `@cloudcli-ai/cloudcli` |

### 原生模块风险说明

此项目包含 3 个需要编译的原生模块：

| 模块 | 用途 | 平台敏感性 |
|------|------|-----------|
| `node-pty` | 终端模拟器（shell 功能） | ⚠️ 高 - OS + Node 版本强绑定 |
| `better-sqlite3` | SQLite 数据库 | ⚠️ 高 - OS + Node 版本强绑定 |
| `bcrypt` | 密码加密 | ⚠️ 高 - OS + Node 版本强绑定 |

---

## 执行计划（假设内网也是 Windows + 相同 Node.js 版本）

### Phase 1: 在当前 Windows 电脑上准备

#### Step 1: 克隆项目
```powershell
cd C:\Users\shihu\Documents\workspace
git clone https://github.com/siteboon/claudecodeui.git
cd claudecodeui
```

#### Step 2: 安装所有依赖
```powershell
npm install
```
这一步会：
- 下载所有 npm 包到 `node_modules/`
- 编译原生 C++ 模块（node-pty, better-sqlite3, bcrypt）
- 运行 postinstall 脚本

#### Step 3: 构建生产版本
```powershell
npm run build
```
这一步会：
- `vite build` → 生成前端静态文件到 `dist/`
- `tsc` → 编译服务端 TypeScript 到 `dist-server/`

#### Step 4: 验证本地运行
```powershell
npm run server
```
打开 `http://localhost:3001` 确认能正常访问。

### Phase 2: 打包

#### Step 5: 打包为 zip
将整个 `claudecodeui` 目录（包含 `node_modules/`、`dist/`、`dist-server/`）打包为 zip：

```powershell
Compress-Archive -Path C:\Users\shihu\Documents\workspace\claudecodeui -DestinationPath C:\Users\shihu\Documents\workspace\claudecodeui-offline.zip
```

> [!NOTE]
> `node_modules` 目录通常较大（可能 500MB+），压缩后预计 150-300MB。

### Phase 3: 内网部署

#### Step 6: 拷贝到内网机器
通过 U 盘或其他方式将 `claudecodeui-offline.zip` 拷贝到内网 Windows 机器。

#### Step 7: 解压并运行
```powershell
# 解压
Expand-Archive -Path claudecodeui-offline.zip -DestinationPath C:\cloudcli

# 进入目录
cd C:\cloudcli\claudecodeui

# 直接启动（生产模式，因为已经 build 好了）
node dist-server/server/index.js
```

#### Step 8: 访问
浏览器打开 `http://localhost:3001`

---

## 如果内网是 Linux

如果目标是 Linux 机器，需要调整方案：

1. **不能直接用 Windows 的 node_modules**
2. 需要在一台有网络的 Linux 机器上做 `npm install` 和 `npm run build`
3. 或者使用 Docker 在 Windows 上构建 Linux 版本
4. 然后再打包 Linux 版本的产物

---

## 额外需要打包的文件（如果内网没有 Node.js）

如果内网机器没装 Node.js，还需要一并拷贝：
- Node.js v22+ 安装包（Windows: `.msi` 文件，约 30MB）
- 下载地址: https://nodejs.org/dist/v22.16.0/node-v22.16.0-x64.msi

---

## 验证清单

- [ ] 确认内网操作系统类型
- [ ] 确认内网 Node.js 版本
- [ ] 在当前电脑 clone + install + build 成功
- [ ] 本地验证 `npm run server` 能正常访问 `:3001`
- [ ] 打包 zip
- [ ] 内网解压后 `node dist-server/server/index.js` 运行成功
- [ ] 浏览器能访问 `http://localhost:3001`
