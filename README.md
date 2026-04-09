# Diary

这是一个用来记录日常事项、技术折腾、阶段性总结与临时备忘的仓库。

## 目录结构

```text
daily/
  2026/
    2026-04-05-K20-Pro-Gemma4-部署记录.md
    2026-04-06-K20-Pro-Gemma4-部署与-OneAPI-多模态接入/
      README.md
      code/
        k20-mm-bridge/
          server.py
          bridge.env.example
          k20-mm-bridge.service
          README.md
```

## 命名规则

默认情况下，日记文件统一使用下面的格式：

```text
YYYY-MM-DD-事件名称.md
```

例如：

```text
2026-04-05-K20-Pro-Gemma4-部署记录.md
```

这样做的好处是：

- 按文件名即可直接按时间排序
- 一眼就能知道当天记录的主题
- 后续按年份扩展也比较自然

如果某条记录除了文字，还需要附带源码、配置文件或截图，也可以使用同样以日期开头的目录，并把正文放到目录下的 `README.md` 中。

## 当前记录

- [2026-04-05 K20 Pro 安装 Gemma 4 部署记录](./daily/2026/2026-04-05-K20-Pro-Gemma4-%E9%83%A8%E7%BD%B2%E8%AE%B0%E5%BD%95.md)
- [2026-04-06 K20 Pro Gemma 4 部署与 OneAPI 多模态接入](./daily/2026/2026-04-06-K20-Pro-Gemma4-%E9%83%A8%E7%BD%B2%E4%B8%8E-OneAPI-%E5%A4%9A%E6%A8%A1%E6%80%81%E6%8E%A5%E5%85%A5/README.md)

## 说明

这个仓库偏向个人记录，不追求统一模板，但默认会保留这些信息：

- 事情背景
- 操作过程
- 关键命令
- 结果验证
- 遇到的问题和后续待办
