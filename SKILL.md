---
name: clean-clash
description: 分层诊断 macOS Clash Verge Rev/Mihomo 的 TUN、fake-IP DNS、系统 DNS 污染（curl 通但浏览器挂）、provider 节点超时、活动节点延迟与订阅 HTTP 状态；只读优先，配置修复须显式确认。
---

# clean-clash

用于 macOS Clash Verge Rev / Mihomo 的安全诊断和最小恢复流程。

## 触发范围

当用户描述以下问题时使用：

- Clash TUN/虚拟网卡已开启但没有流量或持续 timeout；
- curl 能通但浏览器/系统应用打不开（或站点时好时坏）——先怀疑系统解析路径，不是 curl 的问题；
- 节点拨号目标为 `198.18.x.x`、fake-IP 或 provider 节点 DNS 异常；
- 当前节点延迟测试失败；
- 需要检查订阅 HTTP 状态或刷新 macOS DNS 缓存；
- 开关 DNS 覆写、重启内核或重载 TUN 后翻墙突然变坏、怀疑系统 DNS 被冲回 `114.114.114.114`。

不要将本 skill 用于恢复订阅 token、绕过服务商限制、自动猜测配置或无确认删除文件。

## 状态机

```text
IDLE → DIAG → FIX → RELOAD → VERIFY → DONE / ERROR
```

每次执行按以下顺序推进：

1. **DIAG**：先运行 `scripts/diagnose.sh --dry-run`，记录 TUN、core、设备、路由、socket、fake-IP、系统解析路径（`sysdns`/`probe`/`aaaa`/`excluded`：Wi-Fi DNS 是否落在 `route-exclude-address`、系统 dig 是否返回 fake-ip）和 provider DNS 事实。**curl 通 ≠ 浏览器通**：curl 可能命中 mDNSResponder 旧缓存，判定可用性必须走系统解析路径并用真实浏览器抽查。
2. **FIX**：只有用户明确同意且预览结果正确时，才运行带 `--apply` 的最小修复。
3. **RELOAD**：由用户在 Clash Verge UI 中重新加载 profile；不要直接编辑生成的 `clash-verge.yaml`。
4. **VERIFY**：再次运行诊断与活动节点延迟检查，区分订阅 HTTP 状态和缓存节点健康；`dscacheutil -q host -a name <站点>`（应用真正走的路径）须返回 `198.18.x`，并用真实浏览器抽查——只有 curl 通过不算通过。
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

DIAG 输出两行事实：基础栈（TUN/core/route/socket/…）与系统解析路径（`probe` 走 `dig` 绕开缓存、`aaaa`、`cache`、`excluded`、`sniffer`）；有失败项时追加 `issues=` 一行。

### 第二层：按证据深入

- TUN/core/路由异常：先确认 Clash Verge UI 的 TUN 开关、Mihomo 进程、`utun` 和路由；特权 TUN 不由脚本自动启用。
- `198.18.x.x` 拨号超时：检查对应 provider 的 `fake_ip_filters` 与 `proxy_server_nameservers`。
- 当前节点失败：运行 `scripts/check-nodes.sh`，只测试活动 selector 或可识别的代理节点。
- 订阅异常：运行 `scripts/check-subscription.sh`；403 只表示服务端拒绝，不删除缓存、不把它等同于节点全部失效。
- 系统解析异常（DIAG 报 `sysdns-*`，或 curl 通但浏览器挂）：判别链——
  1. `networksetup -getdnsservers Wi-Fi`：若含 `tun.route-exclude-address` 里的地址（如 `114.114.114.114`），查询绕过 TUN → 拿到污染答案（A 假 IP、AAAA 假地址如 `2001::1`），Chrome IPv6 竞速连假地址 → ERR_CONNECTION_CLOSED。
  2. `dig +short www.gstatic.com`（绕开缓存）：fake-ip 模式下必须返回 `198.18.x`；返回真实 IP = fake-ip 管道被绕过。
  3. `dscacheutil -q host -a name www.gstatic.com`（应用可见路径）：`ip_address:` 应为 `198.18.x`，`ipv6_address:` 应落在 `fake-ip-range6`（当前 `2001:2::0/64`，即 `2001:2::x` 是健康假地址；`2001::1` 不在该段 = 上游污染）。
  4. 两路结论不一致时，以系统解析路径 + 真实浏览器为准（curl 结果可能是旧缓存的时序假差异）。修复步骤见第三层「系统 DNS 指向修复」。
- 验证 mihomo DNS listener：**先读合并产物 `dns.listen` 再探对应端口**（实测会变动：2026-09-29 为 `:53`、2026-09-30 为 `127.0.0.1:7874`），`dig +short @127.0.0.1 -p <port> www.gstatic.com` 应返回 `198.18.x`；**特权服务模式下 `lsof -i :53` 为空是误报**（root socket 用户态不可见），改用 dig 或 `netstat -an -p udp | awk '$4 ~ /\.53$/'`。
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

#### 系统 DNS 指向修复（fake-IP 管道）

属系统级修改，**必须用户明确同意后执行**；只改 Wi-Fi，绝不动 Tailscale 服务（会断 100.x MagicDNS）。

1. **前提检查**：合并产物 `clash-verge.yaml` 满足 `tun.enable: true` + `dns.enhanced-mode: fake-ip`，且按其 `dns.listen` 端口探测（`dig +short @127.0.0.1 -p <port> www.gstatic.com`）返回 `198.18.x`。**`:53` 无响应时禁止把系统 DNS 指向 `127.0.0.1`**（系统解析只走 53，无 listener = 黑洞），走下面的公共 DNS 分支。
2. **备份**：
   ```sh
   mkdir -p ~/.claude/.backup/clash
   networksetup -getdnsservers Wi-Fi > ~/.claude/.backup/clash/dns-backup-$(date +%Y%m%d-%H%M%S).txt
   ```
3. **应用**（listener 存活时）：
   ```sh
   networksetup -setdnsservers Wi-Fi 127.0.0.1 1.1.1.1
   ```
   `127.0.0.1` = mihomo fake-IP listener；`1.1.1.1` = 兜底，且不在 `route-exclude-address`，仍会被 TUN dns-hijack 接管。
   **若 listener 不存在**（DNS 覆写关闭、`dns.listen` 缺失）：**禁止指向 `127.0.0.1`**（无监听 = 黑洞），改用不在排除列表的公共 DNS：`networksetup -setdnsservers Wi-Fi 1.1.1.1 223.5.5.5`。
4. **验证**：mDNSResponder 立即拾取，**无需 flush**；`dig +short www.gstatic.com` → `198.18.x`，`dscacheutil` 与浏览器抽查同步通过。
5. **回滚**：
   ```sh
   networksetup -setdnsservers Wi-Fi 114.114.114.114   # 或 Empty 恢复 DHCP
   ```
6. **复发必查**：开关 DNS 覆写、重启内核、重载 TUN 都可能触发 TUN 启停流程把 Wi-Fi DNS 冲回 `114.114.114.114` → 重查 `networksetup -getdnsservers Wi-Fi`（DIAG 的 `sysdns=`/`excluded=` 会自动抓到）并重打第 3 步。

## 已知陷阱（DIAG 误报与复发，先读）

1. **curl 通 ≠ 浏览器通**：curl 常命中 mDNSResponder 旧缓存（时序假差异）。可用性以系统解析路径（`dig`/`dscacheutil` 返回 `198.18.x`）+ 真实浏览器为准；DIAG 的 `probe=` 走 dig 就是为了绕开缓存。
2. **`lsof -i :53` 为空是误报**：特权服务模式下 mihomo 以 root 监听，用户态看不到。用 `dig @127.0.0.1 -p 53` 或 `netstat -an -p udp` 判定。
3. **dig 测试端口以合并产物 `dns.listen` 为准，别硬编码**（实测 2026-09-29 为 `:53`、2026-09-30 变回 `127.0.0.1:7874`；测错端口会把正常栈误判为 DNS 故障——反过来，探错端口也会把死栈误判为活着，**每次先读配置**）。
4. **`socket=False` 可能是路径误报**：service 模式真实 socket 在 `/var/run/clash-verge-service/users/<uid>/verge-mihomo.sock`；脚本 `detect_socket()` 按 pgrep → 候选列表探测，别改回硬编码。
5. **utun/路由判定不能硬编码接口名**：macOS 每次分配的 utun 号不同，脚本用 `route -n get 198.18.0.1` 动态反查（硬编码 `utun1024` 之类必误报）。
6. **切具体节点前先 `scripts/check-nodes.sh`**：向已死 leaf PUT selector 会 HTTP 503 断掉整条代理链；优先切 group 让内部自选。
7. **「只有直连能上网、切节点毫无反应」先查运行时 mode**：`curl --unix-socket <sock> http://localhost/configs` 看是否 `direct`（direct 模式完全忽略选择器，与节点死活无关）；运行时修正须用户同意，持久化由用户在 UI 完成。**DIAG 的 `mode` issue 读的是合并产物文件，可能与 runtime 分歧**（实测 2026-09-30：文件 `direct`、runtime `global`，当前行为正常）——runtime 才是行为真相；文件为 `direct` 意味着**内核重启后会以 direct 启动**，此时应提醒用户在 UI 确认模式以持久化，而不是自行改 mode。
8. **`verge.yaml` 的 `enable_dns_settings` 布尔键不可信**：判断 DNS 覆写是否生效，看合并产物 `clash-verge.yaml` 的 `dns` 块（`listen`/`nameserver`），别信布尔键（实测开完仍显示 `false`）。
9. **UI「扩展配置写入的 dns.* 已被丢弃」警告 = 覆写生效的正常表现**（App 设置接管 mode/fake-ip-filter/nameserver/proxy-server-nameserver），不是故障。
10. **系统 DNS 会被 Verge 冲回 `114.114.114.114`**：开关 DNS 覆写、重启内核、重载 TUN 都可能触发 TUN 启停流程重置系统 DNS → 必须重查 `networksetup -getdnsservers Wi-Fi`（DIAG 的 `sysdns=`/`excluded=` 已自动查）。
11. **sniffer 未启用 = 无第二道防线**：当前 `sniffer` 缺失（`sniffHost=""`），污染 IP 不会被 domain sniffing 挽救；启用属配置变更，须用户同意。
12. **临时排查可 `PATCH /configs` 把 `log-level` 调成 `debug`（仅运行时生效），查完必须改回 `info`**；同理排查用的 mode 改动也不许留在运行时。

## 输入与隐私

- 真实 provider 配置必须位于 checkout 外；公开示例只使用 `example.invalid`。
- 不要将完整订阅 URL、token、UUID、密码或 API secret 作为命令行参数传递。
- Mihomo API secret 通过 `CLEAN_CLASH_API_SECRET` 环境变量读取。
- 脚本输出只使用安全标签、状态码和延迟；不要复制用户日志、profile 或备份到仓库。
- 系统 DNS 备份写入 `~/.claude/.backup/clash/`（checkout 外），不进仓库。

## 限制

本 skill 不能修复服务商账户、IP 白名单、服务端封禁、失效 token、任意代理规则设计，也不能替代 Clash Verge UI 对特权 TUN 的持久化控制。
本 skill 不关闭 TUN、不修改 Global 模式、不动 Tailscale DNS；系统 DNS 修复仅允许在用户明确同意后改 Wi-Fi 并先备份。
