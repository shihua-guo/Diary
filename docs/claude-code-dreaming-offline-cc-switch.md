# 离线电脑（CC Switch + 本地模型）开启 Claude Code Dreaming

> 验证环境：Claude Code **2.1.318**、CC Switch **4.0.23**、Windows 11  
> 目标：另一台**无法访问外网**的电脑，通过 CC Switch 切到本地/第三方模型的 Claude Code，开启 Auto-dream 后台记忆整合。
>
> 这是非官方开关。Claude Code 升级后字段可能变化；升级后请重新按本文验证。
>
> 拷贝到离线机器时，请把本文和同目录的 `Enable-Dreaming.ps1` 一起拷过去。

---

## 0. 先理解：离线为什么要手动写 flag

Claude Code 的 Auto-dream 由三层条件控制：

| 层 | 条件 | 离线机器的情况 |
|---|---|---|
| 设置 | `autoMemoryEnabled` + `autoDreamEnabled` 为 `true` | 需要手动写进 `~/.claude/settings.json` |
| 功能开关 | `tengu_onyx_plover.enabled` 或 `.available` 为 `true` | **离线拿不到 Anthropic GrowthBook，必须手动写进 `~/.claude.json`** |
| 触发门槛 | 距上次整合 ≥24h，且当前项目有 ≥N 个历史会话 | 首次无整合锁，24h 自动通过；会话数见第 6 节 |

在线机器能自动下载 feature flag；离线机器不能，所以 `.claude.json` 里的缓存值是唯一来源。

---

## 1. 前置条件

1. **Claude Code 版本包含 Auto-dream**  
   在目标机执行：
   ```powershell
   claude --version
   ```
   本文在 `2.1.318` 验证。版本过旧时 `/memory` 里不会出现 Auto-dream 行，需要先离线升级 Claude Code。

2. **Claude Code 能通过 CC Switch 正常启动**  
   先用本地模型完成一轮普通对话，确认 `ANTHROPIC_BASE_URL`、模型名、API 路径都正常。

3. **本地模型支持工具调用（tool use）**  
   Dream 是后台 fork，会调用 Read / Write / Grep / Bash（只读）等工具读写记忆文件。  
   建议使用支持 tool use、上下文 ≥64K 的模型；上下文太小或工具调用不稳定时，Dream 会在日志里报 `failed`。

4. **备份**  
   操作前备份：
   ```powershell
   Copy-Item "$HOME\.claude\settings.json" "$HOME\.claude\settings.json.bak-before-dream" -Force
   Copy-Item "$HOME\.claude.json"        "$HOME\.claude.json.bak-before-dream" -Force
   ```

---

## 2. 最小改动清单

| 文件 / 位置 | 键 | 目标值 |
|---|---|---|
| `~/.claude/settings.json` | `autoMemoryEnabled` | `true` |
| `~/.claude/settings.json` | `autoDreamEnabled` | `true` |
| `~/.claude/settings.json` → `env` | `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | **删除** |
| `~/.claude.json` | `cachedGrowthBookFeatures.tengu_onyx_plover.enabled` | `true` |
| 同上 | `.available` | `true` |
| 同上 | `.minHours` | `24` |
| 同上 | `.minSessions` | `3`（首次测试可改 `1`） |
| 同上 | `.remoteEnabled` | `false` |

> 不要设置 `DISABLE_GROWTHBOOK=1`。它会让 Claude Code 连磁盘缓存都不读，Auto-dream 永远不会生效。  
> 如果离线环境设置了 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 或 `DISABLE_TELEMETRY=1`，请同时设置 `CLAUDE_CODE_GB_DISK_CACHE_WHEN_TELEMETRY_OFF=1`。

---

## 3. 操作步骤

### Step 1：在 CC Switch 里确认本地模型供应商

1. 打开 CC Switch → Claude 标签页。
2. 编辑本地模型供应商，确认 `settings_config` 的 `env` 至少包含：
   ```json
   {
     "env": {
       "ANTHROPIC_BASE_URL": "http://127.0.0.1:8000",
       "ANTHROPIC_AUTH_TOKEN": "local",
       "ANTHROPIC_DEFAULT_OPUS_MODEL": "your-local-model",
       "ANTHROPIC_DEFAULT_SONNET_MODEL": "your-local-model",
       "ANTHROPIC_DEFAULT_HAIKU_MODEL": "your-local-model",
       "CLAUDE_CODE_SUBAGENT_MODEL": "your-local-model"
     }
   }
   ```
   把 URL、token、模型名换成目标机的实际值。  
   **不要**在这个 JSON 里保留 `CLAUDE_CODE_DISABLE_AUTO_MEMORY`。

3. 切换到该供应商，确认 `C:\Users\<你>\.claude\settings.json` 已生成。

### Step 2：把两个开关写进 CC Switch 的「通用配置」

CC Switch 每次切换供应商都会重写 `~/.claude/settings.json`。  
为了避免每次切换后重新加开关，应该把开关放进 **Claude 的通用配置（Common Config）**，它会合并到每个供应商配置里。

**方式 A：用 CC Switch 界面（推荐）**

1. CC Switch → Claude 标签页 → 找到「通用配置 / Common Config」。
2. 在现有 JSON 中合并：
   ```json
   {
     "autoMemoryEnabled": true,
     "autoDreamEnabled": true
   }
   ```
   例如原本是：
   ```json
   {
     "autoUpdatesChannel": "latest",
     "skipDangerousModePermissionPrompt": true,
     "model": "sonnet[1m]"
   }
   ```
   合并后：
   ```json
   {
     "autoUpdatesChannel": "latest",
     "skipDangerousModePermissionPrompt": true,
     "model": "sonnet[1m]",
     "autoMemoryEnabled": true,
     "autoDreamEnabled": true
   }
   ```
3. 保存，并重新切换一次供应商，让它重新写入 `~/.claude/settings.json`。

**方式 B：CC Switch 没有通用配置界面时（改数据库）**

> 先完全退出 CC Switch，并备份 `%USERPROFILE%\.cc-switch\cc-switch.db`。

```python
# 需要 Python 3；在普通 PowerShell 中运行
import json, sqlite3, os

db = os.path.join(os.path.expanduser("~"), ".cc-switch", "cc-switch.db")
con = sqlite3.connect(db)
row = con.execute("select value from settings where key='common_config_claude'").fetchone()
cfg = json.loads(row[0]) if row and row[0] else {}
cfg["autoMemoryEnabled"] = True
cfg["autoDreamEnabled"] = True
val = json.dumps(cfg, ensure_ascii=False)
if row:
    con.execute("update settings set value=? where key='common_config_claude'", (val,))
else:
    con.execute("insert into settings(key,value) values('common_config_claude',?)", (val,))
con.commit()
con.close()
print("updated:", cfg)
```

保存后重新打开 CC Switch，切换一次供应商。

### Step 3：先启动一次 Claude Code

离线机器如果从未启动过 Claude Code，`~/.claude.json` 可能不存在。  
先在任意目录运行一次：

```powershell
claude
```

看到欢迎界面后直接 `/exit`。这一步只是让它生成默认的 `~/.claude.json`。

### Step 4：注入 `tengu_onyx_plover` 功能开关

把本文同目录的 `Enable-Dreaming.ps1` 拷到目标机。**先完全退出 Claude Code**（如果 CC Switch 正在运行，也建议先退出），再执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable-Dreaming.ps1
```

首次测试想更快触发，可以用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable-Dreaming.ps1 -MinSessions 1 -ResetLock
```

脚本会：

- 备份 `settings.json` 和 `.claude.json`
- 删除 `env.CLAUDE_CODE_DISABLE_AUTO_MEMORY`
- 写入 `autoMemoryEnabled` / `autoDreamEnabled`
- 写入 `cachedGrowthBookFeatures.tengu_onyx_plover`
- `-ResetLock` 时删除各项目的 `memory\.consolidate-lock`
- 打印最终状态

脚本会重新序列化这两个 JSON 文件，键顺序和缩进可能变化，这不影响 Claude Code 读取。

输出示例：

```
==> settings: C:\Users\you\.claude\settings.json
  backup: C:\Users\you\.claude\settings.json.bak-dream-20261111-210413
  removed env.CLAUDE_CODE_DISABLE_AUTO_MEMORY
==> global config: C:\Users\you\.claude.json
  backup: C:\Users\you\.claude.json.bak-dream-20261111-210414

==> current state
  autoMemoryEnabled : True
  autoDreamEnabled  : True
  disable env key   : False
  onyx flag         : enabled=True available=True minHours=24 minSessions=3
```

验证：

```powershell
$g = Get-Content "$HOME\.claude.json" -Raw | ConvertFrom-Json
$g.cachedGrowthBookFeatures.tengu_onyx_plover | Format-List
```

应看到 `enabled : True`、`available : True`。

> 如果 CC Switch 之后又重写了 `settings.json`，重新运行一次脚本即可。  
> 如果 CC Switch 会重写 `.claude.json`（通常不会），也在切换后重新运行。

### Step 5：离线网络的推荐环境变量

如果目标机完全离线，Claude Code 启动时仍可能尝试访问 Anthropic 拉取配置。建议在 CC Switch 的通用配置或本地供应商 `env` 中加：

```json
{
  "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
  "CLAUDE_CODE_GB_DISK_CACHE_WHEN_TELEMETRY_OFF": "1"
}
```

**不要加**：

```json
"DISABLE_GROWTHBOOK": "1"
```

原因：Claude Code 判断「GrowthBook 被关闭」时，只有在 `CLAUDE_CODE_GB_DISK_CACHE_WHEN_TELEMETRY_OFF=1` 且没有 `DISABLE_GROWTHBOOK` 的情况下才允许读磁盘缓存。  
本地/第三方 `ANTHROPIC_BASE_URL` 属于 non-default host，不会把远程 flag 写回磁盘，所以磁盘里的 `tengu_onyx_plover` 不会被覆盖。

### Step 6：触发 Dream

Dream 没有「立即运行」按钮，也没有 `/dream` 命令。它在**每次主对话回合结束后**检查条件：

1. `autoMemoryEnabled` 和 `autoDreamEnabled` 都为 true。
2. 距上次整合 ≥ `minHours`（24 小时）。  
   上次整合时间 = 当前项目 `memory\.consolidate-lock` 的 mtime；文件不存在视为 0，直接通过。
3. 当前项目里**除当前会话外**至少有 `minSessions`（默认 3）个历史会话。

**首次验证（推荐）**

```powershell
# 1. 用脚本把门槛降到 1，并清掉整合锁
powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable-Dreaming.ps1 -MinSessions 1 -ResetLock

# 2. 在目标项目里制造 1 个历史会话
cd C:\work\demo
claude -p "seed session for dream"

# 3. 重新启动交互式 Claude Code，发任意一条消息
claude --debug
```

> `claude -p` 这类 headless 会话本身不会触发 Dream，它只是用来制造历史会话。  
> Dream 在交互式会话的回合结束时触发。

回合结束后，日志里应出现：

```
[autoDream] firing — ...h since last, 1 sessions to review
```

**正式使用**

验证通过后，把门槛恢复为 3：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable-Dreaming.ps1
```

之后每个项目只要攒够 3 个历史会话、且距上次整合超过 24 小时，就会自动触发。

**想再次测试**

Dream 完成后，`memory\.consolidate-lock` 的 mtime 会成为新的「上次整合时间」，24 小时内不会再触发。  
关闭 Claude Code，删除该项目的锁文件：

```powershell
Get-ChildItem "$HOME\.claude\projects" -Directory | ForEach-Object {
    $lock = Join-Path $_.FullName "memory\.consolidate-lock"
    if (Test-Path $lock) { Remove-Item $lock -Force; "removed $lock" }
}
```

或直接运行脚本加 `-ResetLock`。**确认没有 Dream 正在运行**再删。

### Step 7：查看日志与结果

**日志位置**

默认：

```
C:\Users\<你>\.claude\debug\<sessionId>.txt
```

三种打开方式：

1. 会话内输入 `/debug`，它会启用日志并打印准确路径。
2. 启动时加参数：
   ```powershell
   claude --debug
   ```
   想直接看 stderr：
   ```powershell
   claude --debug --debug-to-stderr
   ```
3. 指定固定日志目录：
   ```powershell
   $env:CLAUDE_CODE_DEBUG_LOGS_DIR = "C:\claude-debug"
   $env:CLAUDE_CODE_DEBUG_LOG_LEVEL = "debug"
   claude --debug
   ```

**实时过滤 Dream 日志**

```powershell
$f = Get-ChildItem "$HOME\.claude\debug\*.txt" |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
"log: $($f.FullName)"
Get-Content $f.FullName -Wait -Tail 200 | Select-String '\[autoDream\]'
```

关键日志：

| 日志 | 含义 |
|---|---|
| `[autoDream] skip — N sessions since last consolidation, need 3` | 历史会话不够 |
| `[autoDream] skip — ... would refuse memory writes` | 权限模式拒绝写记忆 |
| `[autoDream] firing — ...h since last, N sessions to review` | 开始整合 |
| `[autoDream] completed — cache: ...` | 完成 |
| `[autoDream] ... failed` | 失败，看后面的异常信息 |

**结果文件**

Dream 只写记忆目录，不改项目代码：

```
C:\Users\<你>\.claude\projects\<项目键>\memory\
```

项目键是当前工作目录的转写，例如：

| 工作目录 | 项目键 |
|---|---|
| `C:\work\demo` | `C--work-demo` |
| `C:\Users\you\Documents\workspace\Diary` | `C--Users-you-Documents-workspace-Diary` |

找最近被写过的项目：

```powershell
Get-ChildItem "$HOME\.claude\projects" -Directory |
  Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

目录里通常会有 `MEMORY.md` 和若干主题文件；`.consolidate-lock` 是内部锁，不要手改内容。

**后台任务**

Dream 运行时状态栏会显示运行中的后台任务（标签 `dreaming`）。  
如果当前版本启用了 Background 详情屏，可按 `Ctrl+B` 两次进入后台任务视图，查看/停止该任务。

---

## 4. 验证清单

- [ ] `claude --version` 为包含 Auto-dream 的版本（2.1.318 已验证）
- [ ] CC Switch 通用配置里含 `autoMemoryEnabled: true`、`autoDreamEnabled: true`
- [ ] `~/.claude/settings.json` 里没有 `CLAUDE_CODE_DISABLE_AUTO_MEMORY`
- [ ] `~/.claude.json` 的 `tengu_onyx_plover` 为 `enabled=true, available=true`
- [ ] `/memory` 里能看到 **Auto-dream** 行，且为开启状态
- [ ] 当前项目有足够历史会话（或 `minSessions=1`）
- [ ] 日志出现 `[autoDream] firing`
- [ ] `memory\MEMORY.md` 已生成或更新

---

## 5. 常见问题

### `/memory` 里没有 Auto-dream 行

按顺序排查：

1. **没有重启 Claude Code**：设置和 feature flag 都在启动时读取，必须完全退出再启动。
2. **feature flag 没写进去或写错**：重新运行 `Enable-Dreaming.ps1`，用第 3 节的 `Format-List` 验证。
3. **还有禁用变量**：
   ```powershell
   [Environment]::GetEnvironmentVariable('CLAUDE_CODE_DISABLE_AUTO_MEMORY','User')
   [Environment]::GetEnvironmentVariable('CLAUDE_CODE_DISABLE_AUTO_MEMORY','Machine')
   ```
   有值就删掉（系统属性 → 环境变量），然后重开终端。
4. **设置了 `DISABLE_GROWTHBOOK=1`**：删掉它，并加 `CLAUDE_CODE_GB_DISK_CACHE_WHEN_TELEMETRY_OFF=1`。
5. **CC Switch 切换后又把开关覆盖了**：把开关放进 CC Switch 通用配置，或切换后重跑脚本。
6. **版本太旧**：`/memory` 没有这一行就是版本不含该功能，需要离线升级。

### 日志显示 `skip — N sessions ... need 3`

历史会话不够。  
`N` 不含当前会话。处理方式：

- 在当前项目多跑几个 `claude -p "..."`，或
- 用脚本把 `minSessions` 设为 1，并先制造 1 个历史会话。

### 日志显示 `would refuse memory writes`

当前权限模式拒绝写记忆目录。处理方式（任选）：

- 测试时在 `settings.json` 设置：
  ```json
  "permissions": { "defaultMode": "acceptEdits" }
  ```
  或
  ```json
  "permissions": { "defaultMode": "bypassPermissions" }
  ```
- 或为记忆目录加允许规则（按你的 Claude Code 版本支持的路径写法）。

> `bypassPermissions` 会放宽所有权限，仅建议在隔离的离线测试机上使用。

### `[autoDream] ... failed`

先看异常信息，常见原因：

- 本地模型不支持工具调用，或工具调用格式不稳定；
- 上下文太小，装不下多个会话的 transcript；
- 本地推理服务超时或断流。

处理方式：

1. 把 `minSessions` 设为 1，只审阅 1 个会话。
2. 换支持 tool use、上下文更大的本地模型。
3. 确认 `ANTHROPIC_BASE_URL` 指向的服务支持 Anthropic `/v1/messages` 和流式输出。
4. 把 `CLAUDE_CODE_SUBAGENT_MODEL` 设为同一个能力较强的模型。

### Dream 完成但记忆目录没变化

模型可能判断「没有需要整合的内容」，或生成的写入被安全策略拒绝。  
查看完整日志中 `[autoDream] completed` 前后的输出；也可以手动查看 `memory\MEMORY.md` 的修改时间。

### CC Switch 每次切换后都要重新配置

说明开关没有放进通用配置，只在某个供应商的 `settings_config` 里。  
把 `autoMemoryEnabled` / `autoDreamEnabled` 移到 Common Config；并确认供应商配置里没有 `CLAUDE_CODE_DISABLE_AUTO_MEMORY`。

---

## 6. 回滚

1. 恢复最近的备份：
   ```powershell
   $s = Get-ChildItem "$HOME\.claude\settings.json.bak-dream-*" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
   $g = Get-ChildItem "$HOME\.claude.json.bak-dream-*" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
   Copy-Item $s.FullName "$HOME\.claude\settings.json" -Force
   Copy-Item $g.FullName "$HOME\.claude.json" -Force
   ```
2. 或在设置里改回：
   ```json
   {
     "autoDreamEnabled": false
   }
   ```
3. 从 CC Switch 通用配置中删除 `autoMemoryEnabled` / `autoDreamEnabled`。
4. 删除 `~/.claude.json` 里的 `tengu_onyx_plover` 条目（可选）。

---

## 附录 A：手动编辑 JSON

不想用脚本时，按下面改。

**`~/.claude/settings.json`**

删除 `env` 里的：

```json
"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"
```

在顶层加入：

```json
"autoMemoryEnabled": true,
"autoDreamEnabled": true
```

注意 JSON 逗号：如果加在最后一个键之后，前一个键要补逗号。

**`~/.claude.json`**

找到 `cachedGrowthBookFeatures`，把 `tengu_onyx_plover` 改成：

```json
"tengu_onyx_plover": {
  "enabled": true,
  "available": true,
  "minHours": 24,
  "minSessions": 3,
  "remoteEnabled": false
}
```

如果整个文件里没有 `cachedGrowthBookFeatures`，在顶层加入：

```json
"cachedGrowthBookFeatures": {
  "tengu_onyx_plover": {
    "enabled": true,
    "available": true,
    "minHours": 24,
    "minSessions": 3,
    "remoteEnabled": false
  }
}
```

保存时用 **UTF-8 无 BOM**。Windows 记事本旧版本可能写入 BOM，建议用 VS Code 或 PowerShell 脚本。

---

## 附录 B：Linux / macOS 等价操作

路径相同：

- `~/.claude/settings.json`
- `~/.claude.json`

没有 PowerShell 时，用 Python 3：

```python
import json, os, shutil, time

home = os.path.expanduser("~")
sp = os.path.join(home, ".claude", "settings.json")
gp = os.path.join(home, ".claude.json")

def backup(p):
    if os.path.exists(p):
        shutil.copy2(p, p + ".bak-dream-" + time.strftime("%Y%m%d-%H%M%S"))

backup(sp)
backup(gp)

s = json.load(open(sp, encoding="utf-8-sig")) if os.path.exists(sp) else {}
s.setdefault("env", {}).pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)
s["autoMemoryEnabled"] = True
s["autoDreamEnabled"] = True
os.makedirs(os.path.dirname(sp), exist_ok=True)
with open(sp, "w", encoding="utf-8") as f:
    json.dump(s, f, ensure_ascii=False, indent=2)

g = json.load(open(gp, encoding="utf-8-sig")) if os.path.exists(gp) else {}
g.setdefault("cachedGrowthBookFeatures", {})["tengu_onyx_plover"] = {
    "enabled": True,
    "available": True,
    "minHours": 24,
    "minSessions": 3,
    "remoteEnabled": False,
}
with open(gp, "w", encoding="utf-8") as f:
    json.dump(g, f, ensure_ascii=False, indent=2)

print("done")
```

Linux/macOS 的日志目录同样是 `~/.claude/debug/<sessionId>.txt`。

---

## 附录 C：同目录脚本

`Enable-Dreaming.ps1` 是本文第 3 节使用的幂等脚本，支持：

```text
-MinSessions <int>   触发所需历史会话数，默认 3
-ResetLock           删除所有 memory/.consolidate-lock
-ConfigDir <path>    默认 $HOME\.claude
-GlobalConfig <path> 默认 $HOME\.claude.json
```

脚本只修改配置，不修改任何项目代码。



