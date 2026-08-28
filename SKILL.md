---
name: clean-clash
description: 分层诊断 macOS Clash Verge Rev/Mihomo 的 TUN、fake-IP DNS、provider 节点超时、活动节点延迟与订阅 HTTP 状态；只读优先，配置修复须显式确认。
---

# clean-clash

用于 macOS Clash Verge Rev / Mihomo 的安全诊断和最小恢复流程。

## 触发范围

当用户描述以下问题时使用：

- Clash TUN/虚拟网卡已开启但没有流量或持续 timeout；
- 节点拨号目标为 `198.18.x.x`、fake-IP 或 provider 节点 DNS 异常；
- 当前节点延迟测试失败；
- 需要检查订阅 HTTP 状态或刷新 macOS DNS 缓存。

不要将本 skill 用于恢复订阅 token、绕过服务商限制、自动猜测配置或无确认删除文件。

## 状态机

```text
IDLE → DIAG → FIX → RELOAD → VERIFY → DONE / ERROR
```

每次执行按以下顺序推进：

1. **DIAG**：先运行 `scripts/diagnose.sh --dry-run`，记录 TUN、core、设备、路由、socket、fake-IP 和 provider DNS 事实。
2. **FIX**：只有用户明确同意且预览结果正确时，才运行带 `--apply` 的最小修复。
3. **RELOAD**：由用户在 Clash Verge UI 中重新加载 profile；不要直接编辑生成的 `clash-verge.yaml`。
4. **VERIFY**：再次运行诊断与活动节点延迟检查，区分订阅 HTTP 状态和缓存节点健康。
5. **DONE/ERROR**：只根据命令的真实退出码和输出报告结果。

## 渐进式披露

### 第一层：快速入口

```sh
scripts/diagnose.sh --dry-run
```

若 provider 规则在仓库外：

```sh
scripts/diagnose.sh --dry-run \
  --provider-config "$HOME/.config/clean-clash/providers.yaml"
```

### 第二层：按证据深入

- TUN/core/路由异常：先确认 Clash Verge UI 的 TUN 开关、Mihomo 进程、`utun` 和路由；特权 TUN 不由脚本自动启用。
- `198.18.x.x` 拨号超时：检查对应 provider 的 `fake_ip_filters` 与 `proxy_server_nameservers`。
- 当前节点失败：运行 `scripts/check-nodes.sh`，只测试活动 selector 或可识别的代理节点。
- 订阅异常：运行 `scripts/check-subscription.sh`；403 只表示服务端拒绝，不删除缓存、不把它等同于节点全部失效。
- DNS 缓存问题：在 macOS 上由用户明确确认后运行 `scripts/flush-dns.sh --apply`。

### 第三层：显式配置修复

预览 provider DNS merge 变更：

```sh
scripts/fix-provider-dns.sh \
  --provider-config "$HOME/.config/clean-clash/providers.yaml" \
  --provider example-provider
```

确认后应用：

```sh
scripts/fix-provider-dns.sh \
  --provider-config "$HOME/.config/clean-clash/providers.yaml" \
  --provider example-provider --apply
```

该命令只修改唯一匹配的 merge 文件，应用前备份并原子写入；不会重启进程、修改生成配置或输出订阅 URL。

## 输入与隐私

- 真实 provider 配置必须位于 checkout 外；公开示例只使用 `example.invalid`。
- 不要将完整订阅 URL、token、UUID、密码或 API secret 作为命令行参数传递。
- Mihomo API secret 通过 `CLEAN_CLASH_API_SECRET` 环境变量读取。
- 脚本输出只使用安全标签、状态码和延迟；不要复制用户日志、profile 或备份到仓库。

## 限制

本 skill 不能修复服务商账户、IP 白名单、服务端封禁、失效 token、任意代理规则设计，也不能替代 Clash Verge UI 对特权 TUN 的持久化控制。
