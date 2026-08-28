# clean-clash

面向 macOS Clash Verge Rev / Mihomo 的 Claude Code skill，用于分层诊断代理无流量、TUN 状态异常、fake-IP 导致的节点超时，以及 provider DNS 合并配置问题。

> **安全定位：** 本项目是诊断与最小恢复工具，不是订阅破解器，也不会绕过服务商的封禁、白名单或账户策略。

## 能解决什么

| 症状 | 检查或修复 |
| --- | --- |
| TUN 开关、Mihomo 进程、`utun` 设备或路由状态不一致 | `diagnose.sh` 输出分层状态 |
| 节点连接目标变成 `198.18.x.x` 并超时 | 检查 provider fake-IP 排除项与 proxy DNS |
| provider 节点域名被 fake-IP 解析 | `fix-provider-dns.sh` 生成最小 merge 修复 |
| 当前 selector 节点是否能做延迟测试 | 通过 Mihomo Unix API 检查活动节点 |
| 订阅 endpoint 返回 2xx、403 或连接失败 | 只读检查 HTTP 状态，不打印 URL |
| macOS DNS 缓存可能陈旧 | `flush-dns.sh --apply` 显式刷新 |

## 不能解决什么

- 服务商账户失效、IP 白名单、服务端封禁或订阅 token 失效；
- 恢复或猜测订阅 URL、token、UUID、密码；
- 任意设计代理规则、修改生成的 `clash-verge.yaml`；
- 自动启用需要特权的 TUN；请在 Clash Verge UI 中开启并确认；
- 无确认地停止进程、删除缓存、删除日志或“完整清理”。

订阅 HTTP `403` 只表示远程 endpoint 拒绝当前请求，不能证明缓存中的节点全部失效；工具不会因为 403 删除本地 profile。

## 前置条件

- macOS（DNS 刷新脚本仅支持 Darwin）；
- Clash Verge Rev / Mihomo 已安装并运行；
- Python 3.10+ 与 PyYAML；
- 诊断 TUN 需要 `pgrep`、`ifconfig`、`route`；
- 节点检查需要 Mihomo Unix socket（默认 `/tmp/verge/verge-mihomo.sock`）；
- 订阅检查需要网络，但不会把 URL 输出到终端。

安装依赖：

```sh
python3 -m pip install -r requirements.txt
```

## 安装为 Claude Code skill

将仓库目录复制到 Claude Code skills 目录（或使用你自己的 skill 管理方式）：

```sh
mkdir -p ~/.claude/skills/clean-clash
cp SKILL.md ~/.claude/skills/clean-clash/
cp -R scripts ~/.claude/skills/clean-clash/
```

脚本也可以直接从 checkout 目录运行。

## 渐进式诊断

工作流状态机为：

```text
IDLE → DIAG → FIX → RELOAD → VERIFY → DONE / ERROR
```

先只读诊断：

```sh
scripts/diagnose.sh --dry-run
```

指定本地 provider 规则（配置文件必须放在仓库外）：

```sh
export CLEAN_CLASH_PROVIDER_CONFIG="$HOME/.config/clean-clash/providers.yaml"
scripts/diagnose.sh --dry-run --provider-config "$CLEAN_CLASH_PROVIDER_CONFIG"
```

诊断输出重点关注：

1. `tun` 与 UI 持久化开关是否一致；
2. `verge-mihomo`、`utun1024`、fake-IP 路由和 Unix socket 是否存在；
3. 当前配置是否为 fake-IP，以及 provider 节点域名是否已排除；
4. 订阅 HTTP 状态与活动节点延迟是否独立正常。

默认诊断快照写入用户目录下的 `~/Library/Application Support/clean-clash/state`；使用 `--dry-run` 不写状态。可通过 `CLEAN_CLASH_STATE_DIR` 改到其他位置。

## Provider DNS 修复

复制示例到仓库外并编辑：

```sh
mkdir -p ~/.config/clean-clash
cp config/providers.example.yaml ~/.config/clean-clash/providers.yaml
```

配置只应包含你愿意在本机使用的 provider 域名后缀和 resolver。不要将真实文件放入此仓库。

先预览，预览不会备份或写入：

```sh
scripts/fix-provider-dns.sh \
  --provider-config "$HOME/.config/clean-clash/providers.yaml" \
  --provider example-provider
```

确认目标和变更后才应用：

```sh
scripts/fix-provider-dns.sh \
  --provider-config "$HOME/.config/clean-clash/providers.yaml" \
  --provider example-provider \
  --apply
```

修复行为：

- 只匹配 `profiles.yaml` 中唯一的、名称完全相同的 remote profile；
- 只修改对应 `profiles/<merge-id>.yaml` 的 DNS merge 配置；
- 添加缺少的 fake-IP filter；
- 移除 proxy server DNS 中的 loopback resolver，再追加配置的外部 resolver；
- 应用前创建权限为用户私有的备份，并使用原子替换写入；
- 不重启 Clash，不修改生成配置，不打印订阅 URL。

应用后重新加载 profile，再验证：

```sh
scripts/diagnose.sh --dry-run --provider-config "$HOME/.config/clean-clash/providers.yaml"
scripts/check-nodes.sh
```

如需回滚，先停止 Clash Verge，再将备份文件复制回同一个 merge 文件，并让应用重新加载；备份目录由 `CLEAN_CLASH_BACKUP_DIR` 或默认应用支持目录下的 `backups` 决定。

## 其他检查

检查订阅状态（只读）：

```sh
scripts/check-subscription.sh --app-support "$HOME/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
```

检查活动节点（可自定义测试 URL；不要把含秘密的 URL 传给命令行）：

```sh
scripts/check-nodes.sh --socket /tmp/verge/verge-mihomo.sock
```

刷新 macOS DNS（需要系统交互式 sudo；不接受密码参数）：

```sh
scripts/flush-dns.sh --apply
```

## 安全边界

请阅读 [SECURITY.md](SECURITY.md)。尤其不要提交：

- `profiles.yaml`、`profiles/`、provider 缓存、日志和备份；
- 完整订阅 URL、query token、UUID、密码、API secret；
- 真实 provider 域名或能识别账户的节点名称；
- `~/Library/Application Support` 下的运行态文件。

Mihomo API secret 通过 `CLEAN_CLASH_API_SECRET` 环境变量读取，不会写入配置或输出。

订阅检查只允许 HTTPS endpoint，拒绝解析到 loopback、私有、保留或未指定地址，并把首次解析到的
公网 IP 固定到 TLS 连接（不跟随自动重定向）。节点检查连接前会验证 Unix socket 的父目录、文件
类型和所有权；标准 Clash Verge root service 的 setgid 共享目录可用，普通 world-writable 目录会被拒绝。

## 开发与验证

```sh
python3 -m pytest -q
bash tests/test_scripts.sh
bash -n scripts/*.sh
python3 -m json.tool eval/eval-set.json >/dev/null
```

贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
