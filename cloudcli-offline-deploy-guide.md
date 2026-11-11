# CloudCLI 内网离线部署指南

## 📦 压缩包内容

文件：`cloudcli-offline.zip`（约 213MB）

包含以下完整内容：
- 源代码
- `node_modules/`（所有依赖，含已编译的原生模块）
- `dist/`（前端生产构建产物）
- `dist-server/`（后端生产构建产物）

## ⚠️ 前提条件

### 必须

1. **Node.js v22 或更高版本**
   - 当前打包环境使用的是 Node.js **v24.14.0**
   - 内网机器建议安装相同版本，以确保原生模块兼容
   - 如果内网没有 Node.js，请一并拷贝安装包：
     - Windows x64: `node-v24.14.0-x64.msi`
     - 下载地址（外网下载后拷贝）: https://nodejs.org/dist/v24.14.0/

2. **Windows 操作系统**
   - 本压缩包中的原生模块（node-pty, better-sqlite3, bcrypt）是在 Windows 上编译的
   - **不能直接用于 Linux/Mac**，如需部署到其他系统请联系打包者

### 可选

- **Claude Code CLI** — 如果你要连接 Claude Code Agent
- **Cursor CLI** — 如果你要连接 Cursor Agent
- **Codex CLI** — 如果你要连接 OpenAI Codex Agent
- **Gemini CLI** — 如果你要连接 Google Gemini Agent

## 🚀 部署步骤

### 1. 解压

将 `cloudcli-offline.zip` 解压到你想要的目录，例如：

```
C:\cloudcli\
```

解压后目录结构为：
```
C:\cloudcli\
  └── claudecodeui\
      ├── dist\           ← 前端构建产物
      ├── dist-server\    ← 后端构建产物
      ├── node_modules\   ← 所有依赖
      ├── server\         ← 服务端源码
      ├── src\            ← 前端源码
      ├── package.json
      └── ...
```

### 2. 启动服务

打开命令提示符（CMD）或 PowerShell，执行：

```bash
cd C:\cloudcli\claudecodeui
node dist-server/server/index.js
```

你会看到类似输出：
```
═══════════════════════════════════════════════════════════════
  CloudCLI Server - Ready
═══════════════════════════════════════════════════════════════

[INFO] Server URL:  http://localhost:3001
```

### 3. 访问

打开浏览器访问：

```
http://localhost:3001
```

### 4.（可选）配置环境变量

在 `claudecodeui` 目录下创建 `.env` 文件可自定义配置：

```env
# 修改监听端口（默认 3001）
PORT=3001

# 修改监听地址（默认 localhost，设为 0.0.0.0 可让其他电脑访问）
HOST=0.0.0.0
```

### 5.（可选）开机自启

创建一个批处理文件 `start-cloudcli.bat`：

```bat
@echo off
cd /d C:\cloudcli\claudecodeui
node dist-server/server/index.js
```

将此文件放到 Windows 启动文件夹即可：
```
Win+R → shell:startup → 将 bat 文件拖入
```

## 🔧 常见问题

### Q: 启动报错 "Cannot find module"
- 确保解压完整，`node_modules` 目录存在
- 确保使用 Node.js v22+ 版本

### Q: 原生模块报错（node-pty / better-sqlite3 / bcrypt）
- 这些模块对 Node.js 版本敏感
- 确保内网机器安装的 Node.js 版本与打包时一致（v24.14.0）
- 如果版本不同，可能需要在有网环境重新打包

### Q: 想让其他电脑也能访问
- 创建 `.env` 文件，设置 `HOST=0.0.0.0`
- 然后从其他电脑用 `http://<本机IP>:3001` 访问
- 确保防火墙允许 3001 端口

### Q: 数据存储在哪里？
- 数据库文件默认存储在 `~/.cloudcli/` 目录下
- Windows 上即 `C:\Users\<用户名>\.cloudcli\`

## 📋 打包信息

| 项目 | 值 |
|------|-----|
| 打包日期 | 2026-04-29 |
| 项目版本 | v1.30.0 |
| Node.js 版本 | v24.14.0 |
| npm 版本 | 11.9.0 |
| 打包平台 | Windows x64 |
| 压缩包大小 | ~213 MB |
