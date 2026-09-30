# QDII Publisher V1

面向小红书/公众号的纳指100、标普500数据发布工作台。

## 已实现
- 场外额度采集：运行 `aiten2/qdii-purchase-limits` 公共开源引擎，覆盖代销/直销与公告。
- 近1年收益：尝试读取天天基金公开基金排行数据；失败时不伪造，显示 `—`。
- 场内ETF：东方财富公开行情接口获取价格、涨跌幅、成交额。
- 每日历史快照：`data/history/YYYY-MM-DD.json`。
- 昨日变化：场外额度自动标记放宽/收紧。
- 发布后台：`index.html`。
- 自动分页：每页最多10条，1080×1440，一键下载PNG。
- GitHub Actions：北京时间工作日 07:35 / 12:05 / 15:10 / 20:35 自动更新。

## 重要：场内溢价率
V1 不会用昨日净值冒充实时IOPV。当前场内价格/涨跌/成交额已自动更新；`premium_pct` 只有接入可验证的实时 IOPV/折溢价数据源后才展示，否则为 `—`。

## GitHub Pages
Settings → Pages → Build and deployment → Source 选择 Deploy from a branch，Branch 选 main / root。

## 下一步
1. 接入可验证的实时 IOPV/折溢价数据源；
2. 完善基金费率映射与收益字段校验；
3. 增加封面和“今日变化”页；
4. 增加一键下载整个发布包 ZIP。
