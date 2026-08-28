# Contributing

感谢贡献。请保持本项目 provider-neutral、macOS-focused 和只读优先。

## 开发要求

- 不提交真实订阅 URL、token、UUID、密码、API secret、profile、日志或节点配置；
- 示例域名使用 `example.invalid`，示例 provider 名称保持虚构；
- 新的写操作必须有显式确认、路径约束、私有备份和原子写入；
- 不添加自动停止进程、删除缓存/日志或直接编辑生成配置的行为；
- 生产代码和测试都不得使用真实网络、真实 Clash socket 或真实用户目录。

## 本地检查

```sh
python3 -m pytest -q
bash tests/test_scripts.sh
bash -n scripts/*.sh
git diff --check
```

如果本地没有 ShellCheck，可在 CI 中验证；不要用跳过测试代替修复。

## Pull request

请说明：

1. 为什么需要变化；
2. 影响了哪些诊断或修复路径；
3. 如何验证；
4. 是否涉及文件写入、权限或隐私边界。

保持提交小而完整。维护者会在合并前检查 staged diff、测试和敏感信息扫描。
