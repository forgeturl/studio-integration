# 调用示例

完整的 curl 与 jq 调用顺序见 [机构 API 接入说明](../docs/partner-api.md)。本目录提供 Python 标准库请求封装，运行示例无需安装 SDK。

1. 将 `.env.example` 中的变量通过运行环境注入，单独填入机构 API Key。Python 示例不会自动加载 `.env`。
2. 运行 `python examples/client.py catalog` 或 `python examples/client.py wallet`，确认身份和可用配置。
3. 复制 `input.json`，将音色占位符替换为目录中可用的音色 ID，按完整文档完成生成流程。

```python
from examples.client import StudioClient

client = StudioClient.from_env()
catalog = client.request("GET", "/catalog")
offer = client.request("POST", "/scripts/estimate", {"input": original_input})
# 由调用方审阅预估，再明确调用；保留原请求以备超时后核对。
script = client.request("POST", "/scripts", {
    "input": original_input,
    "expected_points": offer["max_points"],
    "price_version": offer["price_version"],
    "writing_template_version": offer.get("writing_template_version"),
}, idempotency_key="your-unique-business-id")
```

示例不自动购买、不自动重试创建任务。发生超时保留原请求和业务单号，用原参数确认结果；拿到 ID 后查询原任务。

`request()` 仅用于机构 API 路径，禁止用它请求下载 URL。下载时将返回的相对路径按正式站点补全，使用独立、不携带机构密钥的 HTTP 请求。

## 用现有参考重写（0.5.0，未部署前不可使用）

在估算请求的顶层增加 `reuse_script_id`，`input` 为本次写作要求；例如：

```json
{
  "input": {"input_type":"script", "script_mode":"ai", "text":"本次主题", "writing_requirements":"先说事实，再解释影响"},
  "reuse_script_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

将示例 ID 替换为本人当前机构空间里已成功、仍有参考资料的脚本 ID。提交时保留该字段，另传估算结果的 `max_points` 对应 `expected_points`、`price_version` 和 `writing_template_version`；两种重写均预占 50 点（演示 0 点）。复用不产生新搜索或读取费用，但写稿和分镜按本次真实用量结算。

重新联网重写时省略 `reuse_script_id`，在 `input` 中设置 `web_search: {"enabled": true, "max_results": 60}`。重试保留同一幂等键及完整请求体，不能因响应不明改用新键重复购买。

## 脚本计费版本标识（0.5.1，Unreleased）

新脚本预估的 `price_version` 使用 `sp5-` 加16位SHA-256摘要。同一计费策略生成稳定标识，策略变化时标识更新。该字段是不透明字符串：接入方原样回传，不截断、不解释内部格式，也不在终端页面显示。脚本提交支持1至128字符，网站与机构API一致；现有机构版本同样作为不透明标识处理。

已受理任务保留原版本、计费快照及幂等请求；50点预占和真实用量结算不变，无需删除草稿、任务或账单。已受理请求继续用原幂等键和完整原请求体核对；未受理的旧报价遇到 `script_price_changed` 时，重新预估、确认新请求后提交。
