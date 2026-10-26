# 04 API 接口契约

## 1. 通用协议

- 前缀 `/api/v1`，JSON UTF-8；字段 snake_case；UUID 用字符串；时间用带时区 ISO 8601。
- Cookie Session 鉴权；前端请求 `credentials: include`。所有 POST/PUT/PATCH/DELETE 携带 `X-CSRF-Token`，登录与注册也需要先请求 session。
- 日期参数 `YYYY-MM-DD`，起止包含；带时区 occurred_at 必填。服务端不接受客户端 user_id。
- 成功直接返回资源对象；列表 `{items,page,page_size,total}`，page 默认 1，page_size 默认 20、最大 100。删除成功 204 无响应体。
- 所有私密响应 `Cache-Control: no-store`。错误响应统一；FastAPI 默认参数错误也转换到统一结构。

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请检查输入内容",
    "fields": [{"path": "mood_score", "message": "必须为 1～5 的整数"}],
    "request_id": "req_example"
  }
}
```

| HTTP | 错误码 | 语义 |
|---|---|---|
| 401 | AUTH_REQUIRED / SESSION_EXPIRED | 未登录或过期 |
| 403 | CSRF_INVALID / AI_CONSENT_REQUIRED | CSRF 不通过或未授权 |
| 404 | RESOURCE_NOT_FOUND | 不存在或非本人资源，响应一致 |
| 409 | VERSION_CONFLICT / REQUEST_ID_REUSED / INVALID_TRANSITION | 编辑冲突、去重键冲突、非法状态 |
| 422 | VALIDATION_ERROR / EMPTY_BODY_FOR_ANALYSIS | 输入不合规则 |
| 429 | RATE_LIMITED | 请求或费用限额，附 Retry-After |
| 503 | AI_UNAVAILABLE / SERVICE_UNAVAILABLE | 服务暂不可用 |

## 2. 账号与设置

| 方法与路径 | 请求 | 成功响应 |
|---|---|---|
| GET `/auth/session` | 无；可创建匿名会话 | 200 `{user:null或User,csrf_token}` |
| POST `/auth/register` | `{email,password,nickname?,adult_confirmed:true,terms_version,privacy_version}` | 201 新 User、csrf_token；旋转并设置已登录 Cookie |
| POST `/auth/login` | `{email,password}` | 200 `{user,csrf_token}`；旋转会话 |
| POST `/auth/logout` | `{}` | 204 撤销并清 Cookie |
| GET `/me` | 无 | 200 User |
| PATCH `/me` | `{nickname?,timezone?}`，至少一个 | 200 User；时区改变使回顾失效 |
| GET `/me/consents` | 无 | 200 `{ai_enabled,consent_version,events:[]}` |
| PUT `/me/consents/ai` | `{enabled,policy_version}` | 200 `{ai_enabled,consent_version}` |
| GET `/me/export` | 无 | 200 附件 JSON，Content-Disposition，含 schema_version |
| DELETE `/me` | `{password,confirmation:"DELETE_MY_ACCOUNT"}` | 204 注销并清 Cookie |
| GET `/metadata` | 公开 | 200 枚举、评分文案、当前条款与 AI 处理说明版本 |
| GET `/support-resources?region=CN` | 公开，地区可变 | 200 `{items:[],generic_support_text}` |

User 字段：`id,email,nickname,timezone,ai_enabled,adult_confirmed_at,created_at`。不返回 password_hash、data_version 或内部会话 token。

AI 授权已处于请求状态时不递增版本或重复写事件。撤回前端需展示影响说明；API 返回成功说明主库撤回事务已提交。启用的 policy_version 必须是当前版本。

导出含用户资料、授权历史、日记、分析与用户修正、活动记录、有效周回顾，排除密码哈希、session、CSRF、原始模型请求。导出时记录一次数据库一致性快照，且不写访问日志正文。MVP 限制导出最多 10000 条日记，超限返回 422 `EXPORT_LIMIT_EXCEEDED`，不截断后冒充完整导出。

## 3. 日记

| 方法与路径 | 请求 | 响应 |
|---|---|---|
| POST `/journals` | JournalCreate | 201 Journal；同请求重试 200 原资源 |
| GET `/journals` | page/page_size、start_date?、end_date?、emotion_code?、tag_code?、tag_label? | 200 分页 JournalSummary |
| GET `/journals/{id}` | 本人资源 | 200 Journal |
| PATCH `/journals/{id}` | `{version,...可修改字段}` | 200 Journal，version 增加 |
| DELETE `/journals/{id}?version=2` | 当前 version 必填 | 204；版本不一致 409 |

筛选日期参数必须成对出现，跨度最多 31 天；不传时分页查询全部记录。多个筛选 AND 组合；custom 标签必须附 tag_label。无效枚举、时间、字段返回 422，PATCH 的未知字段拒绝。

JournalCreate 示例：

```json
{
  "client_request_id": "1d843674-b5c3-4b39-923e-3b41bb8a2a10",
  "mood_score": 2,
  "emotions": [{"code":"sad","label":"低落"},{"code":"anxious","label":"紧张"}],
  "body": "今天汇报被打断，担心自己表现不好。",
  "event_tags": [{"code":"work","label":"工作"}],
  "occurred_at": "2026-10-25T19:30:00+08:00"
}
```

Journal 在以上字段之外增加 `id,version,created_at,updated_at`；不返回 user_id、request_fingerprint。JournalSummary 包含 `id,mood_score,emotions,event_tags,occurred_at,version,body_preview`，preview 最多 80 字。`client_request_id` 创建后不可修改。

## 4. 分析与任务

| 方法与路径 | 请求 | 响应 |
|---|---|---|
| POST `/journals/{id}/analysis-jobs` | `{journal_version}` | 202 JobReceipt；存在有效结果则 200 `{analysis_id,reused:true}` |
| GET `/jobs/{id}` | 无 | 200 Job |
| POST `/jobs/{id}/cancel` | `{}` | 200 Job；终态保持不变 |
| GET `/journals/{id}/analysis` | 无 | 200 Analysis；未生成 404 |
| PATCH `/analyses/{id}/factors/{factor_id}` | `{review_status,user_text?}` | 200 Factor；必须通过 analysis owner 关联查询 |

JobReceipt：`{job_id,status,poll_after_ms:2000}`。

Job：`{id,kind,status,attempt,error_code,result}`，result 在成功时为 `{type:"analysis"|"weekly_review",id}`，其它为 null。不得返回 input_meta、租约、供应商输入输出。取消、失败和任务丢失不是成功。

关联结果因修改、删除或撤权而失效时，同时删除对应的终态任务记录，后续查询返回 404；在途任务改为 cancelled。前端将此类 404 显示为输入已变化或结果已失效，不能继续显示旧结果。

Analysis：`{id,journal_id,journal_version,summary,reflection_question,factors,created_at}`；Factor：`{id,label,hypothesis,evidence_quote,review_status,user_text}`。客户端不能编辑模型原文；用户纠正写入 user_text，`rejected` 排除出已确认线索。

若任务命中支持保护流程，状态 `failed` 且 `error_code=SAFETY_REDIRECT`，前端展示审核后的支持卡片，不展示被拦截的分析；不对用户标注疾病或风险等级。

## 5. 关怀活动与反馈

| 方法与路径 | 请求 | 响应 |
|---|---|---|
| GET `/activities` | type?、scene?、max_minutes?、page、page_size | 200 分页公开活动摘要 |
| GET `/activities/{id}` | 无 | 200 公开活动；未发布或已归档不能新访问执行页 |
| POST `/care/recommendations` | `{available_minutes,scene,excluded_types:[],journal_id?}` | 200 `{items:[{activity,reason}],reason_source:"rules",empty_reason:null或文案}` |
| POST `/care/sessions` | `{client_request_id,activity_id,journal_id?,before_score?}` | 201 CareSession；重试返回 200 原会话 |
| GET `/care/sessions` | page、page_size、status? | 200 分页本人会话 |
| GET `/care/sessions/{id}` | 无 | 200 CareSession |
| PATCH `/care/sessions/{id}/state` | `{version,status,elapsed_seconds}` | 200 CareSession |
| PUT `/care/sessions/{id}/feedback` | `{version,before_score?,after_score?,helpfulness?,feedback_note?}` | 200 CareSession；只允许终态 |

推荐端点为规则计算，不调用模型、不要求 AI 授权。理由示例：“符合你选择的在家场景，约 5 分钟可完成。”因此即使无模型仍可获得 P0 推荐。

ActivitySummary：`id,title,type,duration_minutes,scenes,suitability_note`；详情增加 `version,steps:[{order,text}],audio_url?,source_name,source_url?,license_note`，仅返回已审核的公开元数据。

CareSession：`id,activity_id,activity_snapshot,journal_id,status,version,elapsed_seconds,started_at,ended_at,before_score,after_score,helpfulness,feedback_note`。有效状态转换见 01；反馈修改也递增 version。

## 6. 统计与周回顾

### GET `/insights?start_date=2026-10-19&end_date=2026-10-25`

响应示例（days 实际包含区间全部日期）：

```json
{
  "timezone":"Asia/Shanghai",
  "start_date":"2026-10-19",
  "end_date":"2026-10-25",
  "entry_count":3,
  "recorded_days":2,
  "mean_score":3.0,
  "days":[
    {"date":"2026-10-19","entry_count":0,"mean_score":null},
    {"date":"2026-10-20","entry_count":2,"mean_score":2.5}
  ],
  "emotion_distribution":[{"code":"sad","label":"低落","entry_count":2,"ratio":0.6667}],
  "tag_distribution":[{"code":"work","label":"工作","entry_count":2}],
  "care_summary":{"completed_count":1,"feedback_count":1,"helpful_count":1}
}
```

ratio 返回 0～1 的数，小数 4 位；总记录为零时 distributions 返回空数组。前端转换为百分比，不自行补齐缺失分数。

| 方法与路径 | 请求 | 响应 |
|---|---|---|
| POST `/reviews` | `{start_date,end_date}`，连续 7 天 | 202 JobReceipt；命中有效缓存 200 `{review_id,reused:true}` |
| GET `/reviews` | page、page_size | 200 有效回顾分页，按 created_at 倒序 |
| GET `/reviews/{id}` | 无 | 200 WeeklyReview；已失效或非本人 404 |

WeeklyReview：`id,start_date,end_date,timezone,statistics,insight_eligible,narrative,observations,ai_status,created_at`。statistics 与 insights 同口径。observations 为 `{text,evidence:[{journal_id?,quote?,stat_path?}]}` 数组，证据至少包含一个真实日记精确引用或合法统计路径。

模型失败也可以成功完成纯统计回顾：Job 为 succeeded，回顾 `ai_status=failed,narrative=null,observations=[]`。不足样本 `insufficient`，未授权 `disabled`，安全拦截 `safety_blocked`。

## 7. 并发、重复与限额

- 请求 ID 首版用于日记及活动会话创建；同 ID 不同内容 409，相同内容且资源仍存在返回原资源。分析与回顾按来源版本去重。
- 任务未成功前不返回分析成功提示；读取失效资源不回旧内容。
- 登录失败统一文案，不区分邮箱不存在或密码错误；默认每 IP 每 15 分钟最多 10 次失败，需可配置。
- AI 创建默认每用户每小时 10 次、每天 30 次；已有有效结果或已有任务复用不计新调用。最终调用前再次检查全局日预算。
- CSRF 接口支持匿名会话；无有效 session 的 logout 可直接 204 清 Cookie，存在 session 时仍须 CSRF。
- PATCH factor 首版不提供跨设备版本合并，采用后提交生效；API 明确返回当前值，页面保存期间禁用重复按钮。日记和活动会话必须校验 version。

## 8. 契约落地

实现每个端点的 Pydantic 请求和响应模型，生成 OpenAPI；覆盖字段、状态码和示例。前端从该 OpenAPI 生成类型并检查差异，不能使用 `any` 绕过不一致。
