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
