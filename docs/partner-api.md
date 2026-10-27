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

### 机构写作模板（0.3.0，Unreleased）

管理员可分别配置单人讲述和双人对话模板。在当前机构空间内，按「已开通的机构模板 → 该用户个人模板 → 通用模板」选择；该机构所有有效成员及后续新加入的成员自动继承，无需逐人开通。个人空间不使用机构模板，多个机构之间互不继承。成员或机构停用后不能继续使用该机构能力。

`GET /catalog` 的 `writing_templates.single/dialogue`、脚本估算的 `writing_template` 和脚本任务的 `writing_template` 只返回名称、模式、版本等元数据。机构模板保持 `kind=custom`，另有可选 `scope=organization`；不返回模板提示词、购买/交付记录或其他机构数据。

仅 AI 写稿应用模板，已有文案和录音流程不变。估算后继续原样提交 `writing_template_version`；模板更新或停用导致版本不符时返回 `writing_template_changed`，应重新估算并由用户确认。已受理任务继续使用受理时的模板快照，同幂等键重放返回原任务。启用机构模板前须完成业务 MySQL 迁移 `022_organization_writing_templates` 并部署服务，模板默认关闭。

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
  "web_search": {"enabled": false, "max_results": 60},
  "scene_strategy": {"mode": "auto", "min": 12, "max": 20},
  "cover_ratios": ["16:9"]
}
```

```bash
jq '{input: .}' input.json > estimate-request.json
curl --fail-with-body -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
  --data-binary @estimate-request.json "$API/scripts/estimate" > estimate.json
```

0.4.1 待上线规则：联网参考数量默认从 40 条调整为 60 条。启用时传 `"web_search": {"enabled": true, "max_results": 60}`；已传 `web_search` 但省略数量时采用 60 条。整项省略仍保持旧接口不联网行为，显式数量及已提交任务保持原值。数量是上限，实际可能较少；需要维持 40 条的接入方请显式传 `max_results: 40`。

预估结果中的 `estimated_points`、`max_points`、`price_version` 和 `writing_template_version` 用于本次提交。提交时 `expected_points` 原样使用 `max_points`，版本字段也原样回传，不自行计算或填写固定值。

0.2.4 待上线规则：新脚本固定预占 50 点，个人与机构相同，机构倍率只作用于预计费用和实际结算；开发演示仍为 0 点。`estimated_points` 表示预计实际费用，`max_points` 表示本次确认的预占额度，接入方继续原样回传。费用按保存的费率和真实用量计算，成功后退回未用额度；若实际费用超过 50 点，原任务进入 `recovery_required`，错误为 `script_budget_exceeded`，保留原预占等待核对，不自动追加扣款。已受理任务保持原预占、费率和幂等请求；未提交的旧报价遇到 `script_price_changed` 时重新获取并确认，不硬编码 50。

0.4.0 待上线规则：新受理任务在 AI 写稿和脚本阶段的语义分镜设计中使用高强度深度思考；制作阶段按实际语音对齐时间轴仍不开启。生成可能更久，请持续轮询原任务，勿因等待较长更换幂等键。推理与正文共用模型输出预算，其真实输出用量计入原计费流程，固定预占仍为 50 点；预计费用含推理估量，不是最终扣费承诺。请求及返回结构、原稿直用语义不变，无需传入新的开关；已受理任务沿用保存的配置、预算、费率和幂等记录。价格版本变更后，尚未提交的旧报价重新获取并确认。

0.4.0 待上线规则：开启联网的新 AI 写稿任务使用多轮研究，模型按返回资料继续搜索并读取原网页，优先处理输入资料中的公开链接；不读取本地文件或服务器文件。次数与时间有上限，参考条数仍为上限，不保证搜满。`web_search` 小计包含搜索与网页读取费用，已包含在总预估中，不要再次相加；可返回 `max_fetch_calls`。搜索和读取按供应商成功结果计费，模型各轮按回执 token 计费；固定预占仍为 50 点，多退、不自动补扣，超过预占仍进入原任务待核对。

脚本结果可返回 `research.workflow=adaptive-v1`，保留 `version=1`，增加可选的 `fetch_calls`（尝试读取数）、`rounds`（研究模型轮数）、`read_failures`（未取得可用正文的链接）和 `limitations`（仍缺证据的事项）。来源中的可选 `read_status` 为 `search`（检索资料）、`fetched`（实际读取的原文摘录）或 `unavailable`（原网页未读到可用正文，保留检索资料）。读取原文不代表事实已独立核验。空结果如实返回，不虚构来源；旧格式及未提供这些字段的结果仍须兼容。

旧任务继续原流程、供应商与账务快照；未受理的旧价格版本重新预估并确认。已受理任务持续查询原 ID；网页或模型响应不明时不自动重购。无请求结构变化、无需新增参数或数据库迁移。

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

服务端开启 OSS 中转时，历史文件也可返回本站相对路径，经原授权交付；调用方无需访问 OSS 白名单或取得 OSS 凭据。继续按原样使用 `url`，支持 HEAD 和单区间 Range；中转不延长文件或下载链接的有效期。

0.7.0 的新建文字任务在原文直出与 AI 写稿中统一支持 20000 字符、最长 5400 秒，普通账号、VIP 与机构空间使用相同文字上限。`catalog.limits` 返回当前限制，客户端不提交执行上限。录音上传仍最多 300 秒、100 MiB。旧任务及旧报价沿用原快照，升级不会自动扩大其受理范围；长稿需要重新估算并确认价格版本与当前金额。计价费率、固定写稿预占、实际结算和幂等规则不变，无数据库迁移。

## 四、人工修改脚本

对已完成脚本调用 `PUT /scripts/{script_id}`，请求体必须包含全部下列字段：

| 字段 | 类型与要求 |
| --- | --- |
| `expected_revision` | 当前 `result.revision`，缺省版本按 `1` 处理 |
| `title` | 非空字符串，最长 60 字符 |
| `text` | 非空字符串，最长 20000 字符，仍须符合该脚本受理时保存的输入限制；双人模式保留角色格式 |
| `scene_prompts` | 分镜数组，最多 60 项；每项含 `scene_index`（从 1 开始）、非空 `prompt`，可带 `visual_summary` |
| `cover_prompts` | 封面数组，最多 3 项；每项含 `ratio`（`16:9`、`4:3`、`3:4`）和非空 `prompt` |

保留返回的分镜与封面结构，仅修改需要调整的字段。成功返回更新后的脚本对象，使用新 `result.revision` 重新获取视频预估。发生版本冲突时先重新读取脚本，不覆盖其他操作已保存的内容。

## 五、状态、重试与幂等

0.3.0 待上线恢复行为：Studio 用户或管理员可显式确认换备用线路，只补做原任务中缺少查询结果的图片。复用原任务及已完成素材，每张图片最多购买一次替换，原请求保留核对。普通重试不授予替换权限；备用结果仍未知时停止进一步切换。固定报价不追加真气，旧合同保留原有差价确认或额度补足流程。机构 API 结构不变，接入方继续查询原任务，不新建业务单号。

0.2.5 待上线调度行为：仅视频合成共享全站最多三个执行名额；脚本、配音、识别、生图以及待恢复任务不占用这些名额，取消每账号三个活跃任务与全站十个排队任务的隐式限制。机构配置 `max_active_tasks` 仅限制该机构同时合成的数量，并受全站三个名额约束。等待合成继续返回原任务 `running`，接入方持续查询即可；预算、余额、供应商容量与幂等保护继续有效。

HUI 标准生图使用异步请求保留原任务号；旧的封面画幅不符结果可通过保留完整内容补边恢复。缺少可查询编号的历史请求仍需核对服务商记录，不会因继续制作自动重新购买。上述行为均须 API 与 Worker 部署同一版本后生效，无数据库迁移。

| 状态 | 接入方处理 |
| --- | --- |
| `queued` | 已受理，等待执行，继续查询 |
| `running` | 正在执行或等待必要条件，继续查询并展示提示 |
| `succeeded` | 阶段完成；脚本可审阅，视频可申请文件下载 |
| `recovery_required` | 执行或结算需要处理，保留原任务；有 `funding_required` 时补足额度，否则联系 Studio 核查 |
| `failed` | 展示错误；`composition_*` 失败按下述原任务继续规则处理，其余失败确认后可按新业务重新发起 |
| `cancelled` | 已取消，不再等待交付 |
| `expired` | 任务或内容已过期，展示过期状态 |
| `simulated` | 仅演示完成，不提供真实视频交付 |

0.2.0 待上线合成行为（仅服务端显式启用后生效）：领取后 5 分钟无进展或 1 小时未完成会返回 `composition_heartbeat_expired` / `composition_deadline_exceeded`；执行失败为 `composition_worker_failed`，结果核验失败为 `composition_validation_failed`。这些失败保留素材与未结算预占 7 天，联系 Studio 在原任务继续并持续查询，不直接换业务单号重复购买。原尝试的迟到成功可能使 `failed` 恢复为 `running` / `succeeded`；显式重试后旧尝试不能覆盖新结果。保留期结束，未结算预占退回，错误为 `composition_materials_expired`。输入、鉴权与幂等约定不变。

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

## 图片结果未知时的人工确认（0.6.0，Unreleased）

任务响应可附带 `regeneration_confirmation`，供 Studio 网页及网站管理后台在本地执行器已停止、素材检查点有效时展示「已核对，重新生成」。机构 API 本轮无新增重生成操作，接入方可以忽略此可选元数据，不应自行用新幂等键重提整支视频。

原「继续制作」优先恢复原请求，不授权重新购买结果未知的图片。用户核对原服务商任务及计费，并确认可能再次计费后，网页携带当前恢复版本提交确认；旧确认重放不会再次重生成。Worker 先持久化归档原始请求及来源哈希，再处理未获任何结果的图片请求。已有图片或任务号仍优先恢复原结果，配音、字幕和完成图片不重新生成。后续仍使用原兜底顺序与价格确认；重生成可能再次遇到 503，不保证备用线路必定成功。

同次请求不能同时授权重新生成和换备用线路。已经授权备用线路的任务不再提供重新生成入口，备用线路结果未知时继续保留原请求核对，不能通过另一入口绕过一次替换限制。

新生成采用不同的成本请求 ID，计入 AI 日预算；不创建新视频任务，不直接追加钱包扣款，最终交付按原任务计价规则结算。原服务商的未知费用不能擅自判定为已消费。归档保存在原任务目录的 `image-regeneration-history`，作为对账证据保留，不随单次执行目录清理删除。本轮无需数据库迁移，须同步部署 API、Worker、引擎和前端；不会自动恢复或重试历史任务。


### 参考资料重写（0.5.0，Unreleased）

AI 写稿完成后，可在脚本预估和提交的 JSON 顶层传入 `reuse_script_id`，引用同一用户、同一机构空间内已成功且未过保留期的脚本。`input` 仍为本次写作要求和搭配；仅复用原参考资料，不使用旧脚本正文替代新写稿。省略该字段时按 `input.web_search` 执行原生成流程；需要重新联网时传 `web_search.enabled=true`，不传 `reuse_script_id`。

```json
{"input": {"text": "本次主题", "script_mode": "ai", "writing_requirements": "本次要求"}, "reuse_script_id": "<32位原脚本ID>"}
```

先用同一 `reuse_script_id` 请求预估，再在提交时原样回传该 ID、`max_points` 对应的 `expected_points`、价格版本和模板版本。两种重写均固定预占 50 点（开发演示 0 点），成功后按本次真实用量结算并退回差额。复用路径没有新的搜索或网页读取费，写稿和分镜仍计费；旧任务与旧费用保留。

复用任务返回可选 `reuse_script_id`，`result.research` 为原资料快照，`searched_at`、`search_calls`、`fetch_calls` 是原研究的历史记录，不代表本次调用或收费。资料可能已经过时，涉及最新事实时选择重新联网。不存在或跨空间的来源返回 `script_not_found`；未完成、已过保留期或无资料返回 `script_references_unavailable`，不会自动转成联网付费。重试保留原幂等键与完整请求体，服务端返回已受理任务，不再购买。

## 脚本计费版本标识（0.5.1，Unreleased）

新脚本预估的 `price_version` 使用 `sp5-` 加16位SHA-256摘要。同一计费策略生成稳定标识，策略变化时标识更新。该字段是不透明字符串：接入方原样回传，不截断、不解释内部格式，也不在终端页面显示。脚本提交支持1至128字符，网站与机构API一致；现有机构版本同样作为不透明标识处理。

已受理任务保留原版本、计费快照及幂等请求；50点预占和真实用量结算不变，无需删除草稿、任务或账单。已受理请求继续用原幂等键和完整原请求体核对；未受理的旧报价遇到 `script_price_changed` 时，重新预估、确认新请求后提交。
