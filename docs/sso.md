# Studio SSO 接入说明

本文约定接入方平台与 Studio 之间的单点登录流程。用户在接入方完成身份认证后，通过一次性授权码进入对应机构的 Studio 工作区。

协议标识为 `partner-code-v1`，使用下述授权码交换格式。若需采用 OIDC 或 SAML，应另行确认协议与字段映射。

本文中的 Studio 地址使用正式环境域名。`{platform_code}` 是待分配的平台编号占位符；接入方域名 `partner.example.com` 仅作示例，须替换为接入方提供的真实地址。凭证通过安全渠道单独交接。

## 一、正式环境地址

| 用途 | 正式地址 |
| --- | --- |
| Studio 访问域名（`studio_origin`） | `https://avm.brightguo.com` |
| Studio 工作区 | `https://avm.brightguo.com/studio` |
| API 根地址 | `https://avm.brightguo.com/api` |
| SSO 登录入口 | `https://avm.brightguo.com/api/integrations/{platform_code}/sso/start` |
| SSO 回调地址 | `https://avm.brightguo.com/api/integrations/{platform_code}/sso/callback` |

正式联调前，Studio 提供已开通的 `platform_code` 和替换后的完整登录链接、回调地址；接入方提供授权入口、换码接口及机构编号。登录入口和回调地址统一使用上述域名，`origin` 固定为 `https://avm.brightguo.com`，不包含 `/studio` 或末尾斜杠。

## 二、接入前需要确认的信息

| 参数 | 提供方 | 说明 |
| --- | --- | --- |
| `studio_origin` | Studio | 正式环境固定为 `https://avm.brightguo.com`，不包含路径 |
| `platform_code` | Studio | 接入平台编号；替换本文路径中的 `{platform_code}` 后使用 |
| `authorize_url` | 接入方 | 浏览器授权入口，例如 `https://partner.example.com/sso/authorize` |
| `exchange_url` | 接入方 | 授权码交换接口，例如 `https://partner.example.com/sso/exchange` |
| `shared_secret` | 双方约定 | 换码请求的身份校验凭证，通过安全渠道单独交接 |
| `external_org_id` | 接入方 | 稳定的机构编号，须提前完成开通与对应关系确认 |

双方使用 HTTPS。授权入口和换码接口应提供完整地址，不附带查询参数或 URL 片段。接入方将 Studio 回调地址加入允许列表：

```text
https://avm.brightguo.com/api/integrations/{platform_code}/sso/callback
```

如需独立测试环境，另行确认测试地址、回调地址及凭证；本文列出的地址均为正式环境地址。

## 三、登录流程

1. 用户在接入方点击「进入 Studio」，浏览器跳转到 Studio 登录入口。
2. Studio 将浏览器跳转到接入方的 `authorize_url`，携带 `state` 和 `redirect_uri`。
3. 接入方验证用户登录状态及所属机构，签发一次性 `auth_code`，将浏览器跳回原 `redirect_uri`。
4. Studio 向接入方的 `exchange_url` 发起换码请求，获取可信的用户与机构身份。
5. 身份验证通过后，浏览器进入对应机构的 Studio 工作区。

登录必须由同一浏览器通过顶层页面跳转完成；不要用服务端请求、Ajax 或 iframe 替代浏览器登录流程。流程应在 5 分钟内完成，超时后从登录入口重新发起。

## 四、Studio 登录入口

接入方在页面中提供以下链接：

```http
GET https://avm.brightguo.com/api/integrations/{platform_code}/sso/start?origin=https%3A%2F%2Favm.brightguo.com
```

| 参数 | 说明 |
| --- | --- |
| 路径中的 `{platform_code}` | 替换为 Studio 分配的实际平台编号，不保留花括号 |
| `origin` | 正式环境固定为 `https://avm.brightguo.com`，URL 编码后为 `https%3A%2F%2Favm.brightguo.com` |

用户每次登录都从此入口发起，不直接拼接或复用回调链接。

## 五、接入方授权入口

Studio 向 `authorize_url` 发起浏览器跳转：

```http
GET https://partner.example.com/sso/authorize?state=<state>&redirect_uri=<URL编码后的回调地址>
```

| 参数 | 接入方处理要求 |
| --- | --- |
| `state` | 不解析、不修改，回跳时原样返回 |
| `redirect_uri` | 与预先确认的回调地址匹配；校验通过后用于回跳和授权码绑定 |

接入方完成以下处理：

1. 检查用户登录状态；未登录时先完成认证，保留本次 `state` 和 `redirect_uri`。
2. 根据可信身份确定用户编号及机构编号，并校验用户有权进入该机构。
3. 生成短期有效、不可预测、只能使用一次的 `auth_code`，绑定本次用户、机构及完整的 `redirect_uri`。建议授权码有效期不超过 60 秒。
4. 浏览器回跳到原 `redirect_uri`，携带 `state` 和 `auth_code`；参数值均进行 URL 编码。

回跳示例：

```http
GET https://avm.brightguo.com/api/integrations/{platform_code}/sso/callback?state=<原state>&auth_code=<一次性授权码>
```

授权码参数名为 `auth_code`。不要通过回跳 URL 直接传递用户身份、机构身份、密码或长期令牌。
`auth_code` 使用非空字符串，长度不超过 2048 字符。

## 六、授权码交换接口

Studio 向接入方提供的 `exchange_url` 发送请求：

```http
POST /sso/exchange HTTP/1.1
Host: partner.example.com
Authorization: Bearer <shared_secret>
Content-Type: application/json

{
  "auth_code": "one-time-code",
  "redirect_uri": "https://avm.brightguo.com/api/integrations/{platform_code}/sso/callback"
}
```

接入方先校验 `Authorization`，再核验授权码是否有效、是否已使用、绑定的 `redirect_uri` 是否与请求完全一致。核验成功后原子性地消费授权码，确保并发换码只能成功一次。

成功时直接返回 HTTP 200 和以下 JSON 对象，不包装额外的 `data` 层，不返回网页或重定向：

```json
{
  "external_user_id": "user-123",
  "external_org_id": "school-a",
  "display_name": "成员姓名"
}
```

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `external_user_id` | string | 是 | 非空，最长 255 字符；在接入平台内稳定、唯一，不使用昵称代替 |
| `external_org_id` | string | 是 | 非空，最长 128 字符；须与已开通的机构编号一致 |
| `display_name` | string | 否 | 最长 128 字符，仅用于显示，缺省为空字符串 |

返回对象仅包含上述字段。编号使用字符串，不使用数字或 `null`，不带首尾空白。同一用户进入不同机构时保持相同的 `external_user_id`，通过 `external_org_id` 区分机构。

凭证错误、授权码无效、过期、已使用或回调地址不匹配时，返回非成功状态，不返回可被接受的身份数据。

`shared_secret` 仅由双方服务端持有，不放入网页、浏览器跳转 URL 或前端代码。

## 七、错误处理

Studio 接口错误的 `detail.code` 可用于定位问题，例如：

```json
{
  "detail": {
    "code": "invalid_sso_state"
  }
}
```

| 错误码 | 排查方向 | 处理方式 |
| --- | --- | --- |
| `sso_origin_forbidden` | Studio 访问域名未确认或不匹配 | 检查入口 URL 中的 `origin` |
| `invalid_sso_state` | 流程过期、`state` 被修改，或未使用发起登录的浏览器 | 从登录入口重新发起，不复用旧回调 |
| `partner_sso_exchange_failed` | 换码失败、凭证或授权码无效、响应格式不符 | 检查换码请求、接入方日志和响应字段，再重新登录 |
| `organization_not_found` | 返回的机构编号尚未开通或不匹配 | 核对 `external_org_id` 及机构对应关系 |
| `partner_not_found` | 平台编号错误或接入未启用 | 核对 `platform_code` 并确认接入状态 |

换码失败后重新发起完整登录流程，不反复提交同一个授权码。日志中避免记录完整授权码及认证凭证。

## 八、联调验收

- 已登录用户可以从接入方进入指定机构的 Studio 工作区。
- 未登录用户完成认证后，可以继续原登录流程。
- 不同用户、不同机构的身份对应准确，未授权的机构身份不能通过。
- 授权码过期、重复使用、凭证错误、回调地址不匹配时均被拒绝。
- `state` 被修改、跨浏览器复用回调或流程超时时均不能登录。
- 换码响应字段名、类型、长度及 JSON 结构符合本协议。

SSO 用于建立浏览器登录身份。接入方如需调用视频生成接口，参见 [Studio 机构 API 接入说明](partner-api.md)，使用另行分配的接口凭证；不要将 SSO 授权码或换码凭证作为视频接口调用凭证。
