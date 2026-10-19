# Studio 接入文档维护

- 修改接入契约、示例或版本说明前，读取 `VERSIONING.md`，按其中规则分类、记录并发布。
- 本仓库是对外发布副本。将修改提交到提供方的源文档，再通过部署后的同步流程更新；直接修补副本须同步回源，否则后续发布会覆盖。
- 对外内容限定为接入协议、参数、行为、示例、兼容与变更记录；使用正式地址及明确占位符。凭证、机构资料、价格表和内部部署实现通过其他渠道交接。
- 每次接口变化同步更新 OpenAPI、相关说明、示例、版本号与 CHANGELOG；纯内部变化须有明确的无影响分类依据。
- 发布前运行 `python scripts/validate.py` 和 `python -m unittest discover -s tests`；检查覆盖当前契约与变更范围。
- 仅在 `deployment.json` 确认成功部署且版本、契约摘要匹配时发布 Release。保持历史 Tag 和 Release 不变，联调版本保持 Pre-release。
