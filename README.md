# 山岚 · 内容订阅行为分群

将会员阅读档案转为可解释的行为群组，再制定带冻结成员清单的站内触达方案。

## 真实业务场景

模拟客户山岚内容社有会员运营组4人、编辑6人，试点240位订阅会员。原流程是运营人员导出 `山岚_会员周阅读_20261109.xlsx`，按阅读次数手工分组，再把名单和选题建议发给编辑。三个痛点是篇数与比例量纲混用、分群名单随工作簿修订漂移、内容建议无法追溯到当时的行为画像。本项目承接上游最近完整自然周的行为聚合，替代手工分组与名单归档，下游由编辑和运营负责人审阅内容主题、渠道假设及频次。

业务模块：周阅读档案（按会员×自然周×来源录入/补报）、四周窗口画像（按周明细、缺口清单、加权汇总与发布冻结）、特征选择（2–3维、k=2–6，仅引用已发布窗口）、分群图谱（标准化散点、轮廓系数、原始单位画像、群成员）、触达方案（冻结名单、站内起草、负责人签核与导出）。核心实体为 Reader、WeeklyRecord、Window、WindowProfile、Segment、Outreach；另有用户与审计记录。不连接真实会员系统或外发服务。

|角色|权限和页面|典型动作|
|---|---|---|
|admin|全部页面、审计和独占签核|核对内容主题和频次后签核|
|analyst|档案读写、分群任务、起草与导出|选择行为维度，形成群组内容草案|
|viewer|业务只读与导出，后端拒绝写操作|核对画像和冻结成员|

## 一天的工作剧本

1. 08:50 viewer查看SL-001至SL-240的周阅读篇数、完读率、夜读占比。
2. 09:00 analyst核对输入来自同一完整自然周，修订说明保留在note。
3. 09:10 新增 `SL-241`，周阅读15篇、完读率0.8、夜读占比0.2。
4. 09:20 在特征选择创建“11月会员阅读分群”，勾选全部3个维度、k=3。
5. 09:30 worker执行标准化KMeans，点击刷新查看轮廓系数和原始单位画像。
6. 09:40 点击群组切换成员表，核对人数与阅读习惯，不把群号当作价值排名。
7. 10:00 起草“低频读者轻阅读试点”，绑定成功版本和群1，说明每周一次短篇精选。
8. 10:10 admin签核，10:20 viewer下载 `reader-outreach-<id>.json`，获得固定成员清单。

## 计算口径和失败态

输入为会员唯一编号和最近完整自然周的3个聚合指标：周阅读篇数0–1000、完读率0–1、夜读占比0–1。夜读口径22:00–06:00由上游聚合保证，本应用不重新采集阅读事件。选择2–3个不同特征，k限定2–6。

Python先用StandardScaler的总体均值和总体标准差生成z=(x−mean)/std，再运行KMeans欧氏距离，`n_init=20, random_state=3107, algorithm=lloyd`。所有会员共同用于无监督聚类，不宣称预测评估。轮廓系数s=(b−a)/max(a,b)，a为同群平均距离，b为最近其他群平均距离，范围−1至1；较高表示当前标准化空间中分离更清晰，不表示业务价值。

中心用scaler.inverse_transform还原为原始单位；画像另统计群内三个原始维度的均值（即使某维未选入聚类也展示其描述均值）。群号按逆变换中心排序，仅保证同一输入和seed可复核，不跨版本等价。散点图展示前两个所选标准化维度，聚类仍用所有选择维度，二维重叠不代表同群。

样本数≤k、所选常量列、唯一特征点少于k、实际群数不足、缺失/非有限值均明确失败；不静默补值、降k或删除样本。输入验证422，重复会员编号409，队列故障503。任务失败保存failed和错误原因，修订后新建版本。创建时冻结输入，worker保存成员、中心、画像、轮廓系数、scaler参数、seed和checksum。触达草案保存版本成员副本，不随后续档案修改漂移。分群只描述行为相似性，不判断会员价值或因果关系。

## 四周窗口画像（周明细 → 窗口 → 发布）

单周汇总看不出短期波动与持续偏好，因此在 Reader 主档之外新增 `weekly_records`，按“会员 × ISO自然周（YYYY-Www，周一开始）× 来源”保存阅读篇数、完读率、夜读占比与 `updated_at`。自然键 `(reader_id, week, source)` 保证重复执行只更新不新增；同一会员同一周允许不同来源并存，窗口内按周号取 `updated_at` 最新（再按记录 id 决胜）的一条，模拟乱序补报。

窗口版本 `windows` 以一个已结束自然周为锚点，向前连续四个自然周（含锚点周）。每个窗口对每个会员保存 `window_profiles` 周明细与汇总：

- **总阅读**：四周阅读篇数合计。
- **加权完读率 / 加权夜读占比**：按各周阅读篇数加权（零阅读周权重为0，不产生除零），即 Σ(篇数×比例)/Σ篇数。
- **缺口清单（不补零）**：窗口内有效周不足四周记 `INSUFFICIENT_WEEKS`；四周齐全但篇数合计为0记 `ZERO_READING`。缺口会员保留周明细与缺失周号，不参与聚类，绝不补零。
- **汇总对账**：合格数+缺口数=会员数；周明细篇数求和等于窗口总阅读；附输入 checksum，重复计算得到同一结果。

窗口状态机为 `building → ready → published`（异常为 `failed`）。创建窗口入 Redis 队列，worker 消费计算；中断后重启，worker 启动恢复会把 `building/failed` 窗口与 `queued/running` 分群重新入队，重算为确定性 upsert（画像按自然键更新、不新增记录），恢复到同一窗口结果。窗口幂等：同一锚点周重复创建返回同一窗口，重复计算 checksum 不变、画像不重复。

**发布语义**：仅 admin 可发布，同一时刻只允许一个 `published` 窗口（数据库行锁 + 状态校验，并发发布第二个返回409）；重复发布同一窗口幂等。发布即冻结窗口内各周——这些周的补报/修订被拒绝（409，旧周补报不能改写已更新周）。窗口**发布前**新建分群只能引用上一版已发布完整窗口，引用未发布窗口返回409；**发布后**新分群、群成员快照与触达草案共同指向新窗口。分群快照仅取窗口合格会员（缺口会员排除），并随 Segment/Outreach 冻结，不随后续补报漂移。

页面在“周阅读”录入/补报，在“四周窗口”查看周明细矩阵、缺口原因与汇总对账，并执行重算/发布/导出；前端按角色隐藏写操作，viewer 只读。后端测试（`backend/tests`，pytest）覆盖周边界与跨年周、乱序/多来源取最新、重复计算幂等、中断恢复、发布竞争与冻结补报。

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

前端 [localhost:18206](http://localhost:18206)，后端 [localhost:19206/docs](http://localhost:19206/docs)，PostgreSQL映射17706。演示账号 `admin@demo.local`、`analyst@demo.local`、`viewer@demo.local`，密码均 `Demo123!`。seed=3107，240会员；自然键只插入缺失账号、周记录和窗口，重复执行不覆盖人工修改。seed 生成最近六个自然周的 `weekly_records`（其中 SL-239/SL-240 仅两周，用于演示四周缺口），并计算、发布一个四周窗口。`SEED_DEMO=true`时启动自动执行一次，失败记录日志但不阻塞服务。

五服务frontend/backend/worker/db/redis均有健康检查。backend等待数据库/Redis，worker还等待backend，frontend等待backend。worker真实消费Redis任务，心跳 `/tmp/heartbeat`；单worker启动恢复queued/running。数据库、Redis和产物用命名卷，产物位于共享 `/artifacts`。Nginx将 `/api/`转发到后端根路由。显式子网10.253.107.0/24规避当前机器默认地址池耗尽，可通过NETWORK_SUBNET调整。结束用 `docker compose down -v --remove-orphans` 清理本项目数据。

## 技术、目录与本地开发

|层|实现|
|---|---|
|前端|原生HTML/CSS/ES modules，Nginx1.27|
|后端|Python3.11、FastAPI、SQLAlchemy、PyJWT|
|计算|scikit-learn1.6、NumPy2.2、SciPy1.14|
|数据与队列|PostgreSQL16、Redis7|

`frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}` 分离网络、状态、契约、共用表格/字段/状态标签、表单工具、页面和枚举。`backend/src/{routes,controllers,services,models,schemas,middlewares,utils,constants,config}` 分离HTTP、查询、算法、持久化、校验、鉴权和配置。RequestId与SecurityHeaders为两个中间件，全局错误可恢复，业务写入有审计。ORM建初表，migrations/001_initial.sql保留实际DDL，没有在线版本迁移执行器。

本地开发先启动db/redis，在backend安装requirements，设置DATABASE_URL/REDIS_URL/JWT_SECRET后运行 `uvicorn src.main:app --reload`。前端静态文件通过Nginx同源代理，也可配置本地开发代理。环境变量见.env.example：COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、DB_PASSWORD、JWT_SECRET、SEED_DEMO、NETWORK_SUBNET。部署时替换演示凭据与密钥。

共享枚举ROLES、STATES、FEATURES、OUTREACH_STATES、WINDOW_STATES与缺口原因在后端src/constants/enums.py和前端src/constants/enums.js；字段约束在schemas/business.py，持久化列在models/entities.py。窗口算法为纯函数 src/services/windows.py（加权、缺口、对账、checksum），周号工具在 src/services/weeks.py，编排与发布在 src/services/window_ops.py。后端测试 `cd backend && python -m pytest tests/`，无需外部数据库或 Redis（SQLite + 内存假队列）。前端共用table/fields/status，表单hooks和HTML转义utils至少两个工具。

## 范围与证据

逐条表单/API录入及完整字段修订，无CSV/Excel导入、删除、分页、在线新会员预测或自动跨版本群组对齐。触达仅站内方案与签核，不发送邮件或消息。单worker；不宣称多worker exactly-once或大规模性能。Google Fonts需联网，离线使用serif/sans-serif回退。已知差异、真实测试和截图位于源码外 `../../test-artifacts/gb-3107/`。许可证MIT，见LICENSE。
