# Requirements

## Goal

提供一个 provider-neutral 的 macOS Clash Verge Rev / Mihomo 诊断 skill，帮助用户
区分 TUN、内核、路由、fake-IP DNS、活动节点和远程订阅状态，而不泄露本地账户数据。

## Functional requirements

- REQ-001：诊断必须报告 TUN 配置、UI 开关、Mihomo 进程、`utun1024`、fake-IP 路由和 Unix socket 状态。
- REQ-002：诊断必须能基于外部 provider 规则识别节点域名和 fake-IP filter 缺失。
- REQ-003：节点检查必须通过 Mihomo Unix API 只测试活动 selector 或可识别代理节点。
- REQ-004：订阅检查必须区分 2xx、403、其他 HTTP 状态和连接失败，不修改本地 profile。
- REQ-005：provider DNS 修复默认为预览，只有 `--apply` 才允许写入。
- REQ-006：修复必须匹配唯一 remote profile，限制目标路径，先私有备份后原子写入，并可重复执行。
- REQ-007：macOS DNS 刷新必须仅在 `--apply` 且通过交互式 sudo 验证后执行。
- REQ-008：任何输出不得包含订阅 URL、query token、UUID、密码或 API secret。
- REQ-009：测试不得访问真实 provider、真实订阅 endpoint 或用户运行态目录。

## Non-goals

- 不恢复订阅凭据；
- 不绕过服务商封禁、IP 白名单或账户策略；
- 不自动启用特权 TUN；
- 不提供无确认的缓存/日志删除或进程终止；
- 不修改 Clash Verge 生成配置。

## Acceptance criteria

- AC-001：fixture 诊断能检测 missing fake-IP filter 与 loopback proxy resolver。
- AC-002：dry-run 前后目标文件字节内容、备份目录和状态目录均不变。
- AC-003：apply 第一次写入会创建私有备份，第二次 apply 结果与第一次相同。
- AC-004：profile 匹配非唯一、merge UID 非法、路径穿越和错误 YAML 均返回非零状态。
- AC-005：订阅测试输出只含安全标签与状态，不含 fixture URL 的 query 部分。
- AC-006：所有 Python、shell、JSON/YAML 检查在 CI 中通过。
