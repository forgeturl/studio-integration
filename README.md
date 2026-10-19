# Studio 系统集成

本仓库供合作平台开发者接入 Studio。文档目标版本为 **0.2.3，待部署的联调预发布**；实际部署状态以 `deployment.json` 为准，正式验收后再发布 1.0.0。

| 内容 | 入口 |
| --- | --- |
| 浏览器单点登录 | [SSO 接入说明](docs/sso.md) |
| 服务端脚本与视频调用 | [机构 API 接入说明](docs/partner-api.md) |
| 机器可读取的接口契约 | [openapi.json](openapi.json) |
| Python 请求示例与配置 | [examples/README.md](examples/README.md) |
| 每次接口变更 | [CHANGELOG.md](CHANGELOG.md) |
| 版本与兼容规则 | [VERSIONING.md](VERSIONING.md) |
| 当前部署与版本来源 | [deployment.json](deployment.json) |

正式环境：`https://avm.brightguo.com`。机构 API 基址：`https://avm.brightguo.com/api/partner/v1`。

SSO 适合进入 Studio 页面操作；机构 API 适合接入方服务器中转。二者可以同时使用，同一用户的 `external_user_id` 须保持一致。

## 联调顺序

1. 双方确认机构编号、平台编号、用户标识及授权回调地址，通过单独渠道交接机构 API Key 和 SSO 换码凭证。
2. 使用专门开通的联调机构及独立密钥，先查询能力和余额，确认可用配置。
3. 按文档跑通脚本生成、审阅、视频提交、轮询和下载。
4. 验证重复提交、请求超时、身份隔离、凭证撤销、额度不足及链接过期。
5. 双方确认验收结果和正式切换时间，再启用正式机构凭证。

联调机构与生产机构应使用不同密钥。本文没有另设沙箱域名；使用正式环境执行真实生成时，按实际任务记录消耗。独立测试环境须由双方另行确认，不使用虚构地址。

## 版本与问题反馈

对接时记录双方确认的 Release/Tag，阅读该版本的文档。`main` 的 `deployment.json` 标明最新同步状态；`pending` 表示文档已准备、尚未确认对应部署。以成功部署后的 Release 为版本发布凭据。

通过 Issues 提交接口问题，附接口路径、版本、HTTP 状态、错误码、任务 ID 和脱敏后的请求。凭证、客户资料、原始内容和商务约定通过双方约定的渠道单独交接。

本仓库由提供方的发布流程同步维护。文档修改建议通过 Issue 提交，维护者在源文档中修改并发布，确保说明、接口契约与部署版本对应。
