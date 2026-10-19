# Studio 机构 API 接入说明

本文用于接入方服务器调用 Studio 的脚本与视频生成接口。用户请求接入方服务器，由接入方校验登录身份、转换参数、提交任务并查询结果。

正式环境基址：`https://avm.brightguo.com/api/partner/v1`。

浏览器单点登录参见 [Studio SSO 接入说明](sso.md)。API 调用使用机构密钥，可独立于浏览器 SSO 使用。

## 一、接入准备与身份认证

Studio 为已开通的机构分配 API Key，通过安全渠道单独交接。每个请求均携带：

```http
X-API-Key: <该机构的 API Key>
X-External-User-ID: user-123
Content-Type: application/json
```

| 参数 | 要求 |
| --- | --- |
| `X-API-Key` | 仅保存在接入方服务器；使用对应机构的有效凭证 |
| `X-External-User-ID` | 必填字符串，1～255 字符，不含首尾空白或控制字符；由接入方服务器根据已验证的登录态确定 |
| `Idempotency-Key` | 创建脚本和提交视频任务时必填，1～64 位英文字母、数字、下划线或横线 |

机构由 API Key 确定，请求体无需传机构编号。同一合作平台内，用户标识须稳定、唯一，并与 SSO 返回的 `external_user_id` 完全一致。首次可信调用会建立用户对应关系；停用成员不能通过再次调用恢复权限。

所有操作使用同一机构和用户身份。脚本、报价、任务及下载授权均校验归属。姓名、手机号、邮箱和头像不是 API 必填参数。

密钥不放入浏览器、移动端安装包或 URL。SSO 的 `auth_code`、换码凭证及浏览器登录令牌不作为机构 API Key 使用。

## 二、接口一览

以下路径均相对于正式环境基址。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/catalog` | 获取当前能力、可用音色、风格、模型和输入限制 |
| GET | `/wallet` | 查询机构可用与预占额度 |
| GET | `/ledger` | 查询最近 100 笔机构额度流水 |
| POST | `/scripts/estimate` | 预估本次脚本请求，取得提交所需版本信息 |
| POST | `/scripts` | 创建脚本任务，携带 `Idempotency-Key` |
| GET | `/scripts/{script_id}` | 查询脚本状态及结果 |
| PUT | `/scripts/{script_id}` | 保存已完成脚本的人工修改 |
| POST | `/quotes` | 根据已完成脚本获取视频预估与提交凭据 |
| POST | `/tasks` | 提交视频任务，携带 `Idempotency-Key` |
| GET | `/tasks` | 查询当前用户在该机构下的视频任务 |
| GET | `/tasks/{task_id}` | 查询指定视频任务 |
| POST | `/tasks/{task_id}/cancel` | 取消尚在排队的视频任务 |
| POST | `/assets/{asset_id}/access` | 取得短期有效的文件下载地址 |

任务结果通过轮询获取。调用方可每 3～5 秒查询一次，网络异常时适当延长间隔。本文流程使用文字输入；录音上传及完成通知回调需另行确认接入协议。

## 三、完整调用流程

下列示例使用 Bash、curl 和 jq，密钥通过环境变量注入。所有命令由接入方服务器执行。`request-20261019-001` 仅为业务单号示例，生产环境须为每次新业务生成不同单号。

### 1. 获取可用配置

```bash
API='https://avm.brightguo.com/api/partner/v1'
USER_ID='user-123'
REQUEST_ID='request-20261019-001'
# 调用前通过运行环境设置 STUDIO_API_KEY，不将真实密钥写入本文或前端。
: "${STUDIO_API_KEY:?请先设置机构 API Key}"
AUTH=(-H "X-API-Key: $STUDIO_API_KEY" -H "X-External-User-ID: $USER_ID")

curl --fail-with-body -sS "${AUTH[@]}" "$API/catalog" > catalog.json
```

检查 `enabled`、`available`、`script_generation.available` 及相关配置项的 `available`。音色、模型及风格 ID 从返回的可用列表选择；输入长度、时长及选项范围遵循返回限制。

### 2. 准备输入并获取脚本预估

建立 `input.json`，将音色占位符替换为 `/catalog` 返回的可用音色 ID：

```json
{
  "input_type": "script",
  "script_mode": "ai",
  "text": "介绍人工智能如何帮助日常学习。",
  "mode": "single",
  "aspect_ratio": "9:16",
  "style_id": "clean",
  "voice_ids": ["<可用音色ID>"],
  "web_search": {"enabled": false},
  "scene_strategy": {"mode": "auto", "min": 12, "max": 20},
  "cover_ratios": ["16:9"]
}
```

```bash
jq '{input: .}' input.json > estimate-request.json
curl --fail-with-body -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
  --data-binary @estimate-request.json "$API/scripts/estimate" > estimate.json
```

预估结果中的 `estimated_points`、`max_points`、`price_version` 和 `writing_template_version` 用于本次提交。提交时 `expected_points` 原样使用 `max_points`，版本字段也原样回传，不自行计算或填写固定值。

### 3. 创建脚本任务并轮询

```bash
jq --slurpfile offer estimate.json \
  '{input: ., expected_points: $offer[0].max_points,
    price_version: $offer[0].price_version,
    writing_template_version: $offer[0].writing_template_version}' \
  input.json > script-request.json

curl --fail-with-body -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $REQUEST_ID" --data-binary @script-request.json \
  "$API/scripts" > script-created.json

SCRIPT_ID=$(jq -er '.id' script-created.json)
curl --fail-with-body -sS "${AUTH[@]}" "$API/scripts/$SCRIPT_ID" > script.json
```

重复查询同一个 `SCRIPT_ID`，直到 `status` 为 `succeeded`。成功后读取 `result.title`、`result.text`、`result.revision`、`result.scene_prompts` 和 `result.cover_prompts`；没有 `revision` 字段时按 `1` 处理。

在 `queued`、`running` 或 `recovery_required` 状态下保留原任务，不通过换业务单号重复生成。其他状态参见下文。

### 4. 审阅脚本并获取视频预估

在脚本成功且审阅完成后执行。保留原 `input.json` 的输入参数，仅添加脚本 ID 与当前版本；**不要将 `text` 换成生成后的台词**，接口会使用已保存、已审阅的脚本结果。

```bash
jq --slurpfile script script.json \
  '. + {script_id: $script[0].id,
        script_revision: ($script[0].result.revision // 1)}' \
  input.json > quote-request.json

curl --fail-with-body -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
  --data-binary @quote-request.json "$API/quotes" > quote.json
```

返回的 `id` 是视频提交凭据 `quote_id`，`expires_at` 是 Unix 秒时间戳。须在过期前提交；脚本或相关配置变更后重新获取预估。

### 5. 提交视频并查询进度

```bash
jq '{quote_id: .id}' quote.json > task-request.json
curl --fail-with-body -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $REQUEST_ID" --data-binary @task-request.json \
  "$API/tasks" > task-created.json

TASK_ID=$(jq -er '.id' task-created.json)
curl --fail-with-body -sS "${AUTH[@]}" "$API/tasks/$TASK_ID" > task.json
```

重复查询同一个 `TASK_ID`。主要响应字段：

| 字段 | 含义 |
| --- | --- |
| `id`、`status` | 任务编号及状态 |
| `progress`、`message`、`error_code` | 当前进度、提示及错误码 |
| `billing_mode` | 新任务按实际用量结算时为 `actual_usage_v1` |
| `estimated_points` | 提交时的原预估额度 |
| `points` | 当前累计预占额度 |
| `charged_points`、`refunded_points` | 已结算消费及已释放差额，结算完成前可能为空 |
| `result.funding_required` | 需要补充余额或调整额度时的提示 |
| `result.artifacts` | 成功交付文件列表，使用各项的 `id`、`kind`、`expires_at` |
| `development_only` | 为 `true` 时仅为演示结果，不能作为真实视频交付 |

额度不足时展示 `result.funding_required` 中的说明，联系对应管理员处理，并继续查询原任务。补足后原任务自动继续；不重新生成脚本或创建新视频任务。

### 6. 获取交付文件

视频 `status=succeeded` 后，从 `result.artifacts` 选择 `kind=video` 的文件：

```bash
ASSET_ID=$(jq -er '.result.artifacts[] | select(.kind == "video") | .id' task.json | head -n 1)
curl --fail-with-body -sS "${AUTH[@]}" -X POST \
  "$API/assets/$ASSET_ID/access" > download.json
```

返回 `url`、`expires_at` 和 `filename`。`url` 可能是完整 HTTPS 地址，也可能是以 `/` 开头的路径；相对路径按 `https://avm.brightguo.com` 补全。按原样使用下载地址，允许跟随重定向，不向下载地址附加或转发机构 API Key。

下载链接是短期授权，应仅交给有权查看该作品的用户。链接失效而文件仍在保留期时重新申请；以任务、文件及下载响应中的 `expires_at` 为准。

## 四、人工修改脚本

对已完成脚本调用 `PUT /scripts/{script_id}`，请求体必须包含全部下列字段：

| 字段 | 类型与要求 |
| --- | --- |
| `expected_revision` | 当前 `result.revision`，缺省版本按 `1` 处理 |
| `title` | 非空字符串，最长 60 字符 |
| `text` | 非空字符串，最长 10000 字符，仍须符合当前用户输入限制；双人模式保留角色格式 |
| `scene_prompts` | 分镜数组，最多 60 项；每项含 `scene_index`（从 1 开始）、非空 `prompt`，可带 `visual_summary` |
| `cover_prompts` | 封面数组，最多 3 项；每项含 `ratio`（`16:9`、`4:3`、`3:4`）和非空 `prompt` |

保留返回的分镜与封面结构，仅修改需要调整的字段。成功返回更新后的脚本对象，使用新 `result.revision` 重新获取视频预估。发生版本冲突时先重新读取脚本，不覆盖其他操作已保存的内容。

## 五、状态、重试与幂等

| 状态 | 接入方处理 |
| --- | --- |
| `queued` | 已受理，等待执行，继续查询 |
| `running` | 正在执行或等待必要条件，继续查询并展示提示 |
| `succeeded` | 阶段完成；脚本可审阅，视频可申请文件下载 |
| `recovery_required` | 执行或结算需要处理，保留原任务；有 `funding_required` 时补足额度，否则联系 Studio 核查 |
| `failed` | 本次失败，展示错误；确认需要重新执行后，按新业务重新发起 |
| `cancelled` | 已取消，不再等待交付 |
| `expired` | 任务或内容已过期，展示过期状态 |
| `simulated` | 仅演示完成，不提供真实视频交付 |

同一机构、同一阶段的业务单号用于去重；脚本阶段与视频阶段可以使用同一个单号。相同单号重试必须携带原用户、原请求体和原提交凭据。修改参数或更换操作者时不能复用原单号。

网络超时或连接断开时，保留原请求，用同一个 `Idempotency-Key` 重试以确认结果。已经拿到任务 ID 后优先查询原任务。读取超时不代表生成失败，不应换新单号重新购买。

## 六、错误响应

业务错误通常通过 HTTP 状态码和 `detail.code` 返回；字段校验失败时，HTTP 422 的 `detail` 可能为错误数组，应保留字段位置和提示。

```json
{"detail": {"code": "invalid_organization_key"}}
```

| 错误码 | 处理方式 |
| --- | --- |
| `invalid_organization_key` | 核对机构密钥是否正确、有效且已启用 |
| `external_user_id_invalid` | 修正用户 ID 格式，保持稳定身份 |
| `organization_forbidden` | 核对机构及成员状态与权限 |
| `organization_insufficient_points` | 补充机构余额；已存在任务继续查询原 ID |
| `organization_daily_points_exceeded`、`user_daily_points_exceeded` | 联系管理员核对消费额度 |
| `idempotency_conflict` | 同一业务单号的用户或参数不一致；核对原请求，不盲目换号重试 |
| `script_price_changed`、`writing_template_changed` | 重新获取脚本预估，使用返回值重新确认提交 |
| `script_input_changed` | 核对原脚本输入，避免把生成后的台词当作原请求重新提交 |
| `script_revision_changed`、`script_revision_conflict` | 重新读取脚本，审阅当前版本后重新获取视频预估 |
| `quote_expired` | 原请求未受理时重新获取视频预估；提交结果不明时先用原单号和原凭据确认 |
| `script_not_found`、`task_not_found`、`quote_not_found` | 核对资源 ID、机构密钥及用户 ID 是否匹配 |
| `script_generation_busy` | 暂缓创建新脚本，继续查询已有任务 |
| `video_admission_paused`、`cloud_video_disabled` | 接入暂不可用，联系 Studio 确认开放状态 |
| `video_asset_expired` | 文件已过期，不能继续复用下载链接 |

## 七、联调验收

- 同一用户通过 SSO 和 API 对应到同一身份，机构归属正确。
- 完成脚本预估、生成、审阅、视频预估、提交、查询及下载的完整流程。
- 重复提交、网络超时重试均返回原任务，不重复执行。
- 不同用户与不同机构的脚本、任务及文件无法交叉访问。
- 脚本修改后的版本冲突、过期提交凭据与下载链接失效均有正确提示。
- 余额或额度不足时保留原任务，处理后可继续完成交付。
