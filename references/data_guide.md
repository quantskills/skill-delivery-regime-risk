# 数据源与字段说明

## 数据来源

本研究使用 Panda data SDK（QuantStudio 平台入口）拉取上期所 RB（螺纹钢）/ HC（热轧卷板）期货的合约生命周期与日线行情。

**正式研究必须使用 PandaAI data 数据拉取库或项目明确指定的数据源。**
不得使用来源不明、字段不稳定、个人临时整理的数据文件作为正式输入。

如不确定数据源、字段口径或权限配置，必须咨询项目工作人员后再开发。

## Panda data SDK 接口

本研究实际调用 597+3 次，全部留痕于 `platform_logs/`（pull_log.jsonl + output_samples.json 含完整返回样本）。

### 1. `get_future_contract_pool` — 历史活跃合约池

按时间窗遍历得到品种全历史合约清单。

- 参数：
  - `underlying_symbol`：品种列表（如 `["RB", "HC"]`，**不带交易所后缀**）
  - `start_date` / `end_date`：窗口（YYYYMMDD），按半年窗遍历
- 返回：合约行（symbol / underlying_symbol 等），经去重得 187 个合约

### 2. `get_future_detail` — 合约生命周期

逐合约查询上市/退市/到期/交割起止与保证金率。

- 参数：`symbol`：合约代码（带后缀，如 `"RB2510.SHF"`）
- 返回关键字段：
  - `listed_date` / `de_listed_date`：上市/退市日期（**YYYY-MM-DD 带横线**）
  - `maturity_date`：到期日（YYYY-MM-DD，转 YYYYMMDD 后用于反推 T-1/T0）
  - `start_delivery_date` / `end_delivery_date`：交割起止
  - `margin_rate`：挂牌基准保证金率

### 3. `get_market_data` — 期货日线（唯一正路）

- 参数：
  - `symbol`：合约代码（如 `"RB2510.SHF"`）
  - `start_date` / `end_date`：YYYYMMDD（超 5 年需分段拉取）
  - **`type='future'`**：必传——默认 `type='stock'` 只认股票代码，返回空
- 返回字段（`data/daily/*.csv` 落盘列）：

| 字段 | 口径 |
|---|---|
| `date` | 交易日期（**YYYYMMDD 无横线**，与 future_detail 日期格式不同） |
| `symbol` | 合约代码（RB2510.SHF） |
| `open/high/low/close` | 开/高/低/收 |
| `settlement` | **结算价**（保证金占用与梯度实验的计价基准） |
| `pre_settlement` | 前结算价（`limit_up/pre_settlement-1` 反推当日停板幅度） |
| `volume` / `amount` | 成交量 / 成交额 |
| `open_interest` | **持仓量**（流动性衰减与漏报B 分析依据） |
| `limit_up` / `limit_down` | 涨/跌停价 |
| `dominant_id` / `underlying_symbol` / `trading_code` / `exchange` | 主力标记 / 品种 / 交易代码 / 交易所 |
| `day_session_open` | 日盘开盘时间 |

### 4. `get_future_dominant` — 主力合约映射（环境验证用）

- 参数：**`underlying_symbol`**（非 symbol，如 `["RB"]`）+ 日期窗

## 接口踩坑（防再踩，详见 notes.md）

| 现象 | 原因与正路 |
|---|---|
| `get_future_daily` 报 module 无此属性 | 文档与 SDK 版本不一致，接口未注册 |
| `get_future_daily_post` 返回空 DataFrame | 单合约与主力连续均空，不可用（187 次调用留痕在案） |
| `get_market_data` 返回空 | 未传 `type='future'`，默认查股票 |
| `get_future_symbol_oi_value` 等未在顶层注册 | 需 `from panda_data.readers import future_reader` 直调 |

## 本地数据文件（data/）

| 文件 | 主键 | 说明 |
|---|---|---|
| `contracts.csv` | symbol | 187 合约清单（symbol, underlying_symbol） |
| `future_detail.csv` | symbol | 生命周期（日期 YYYY-MM-DD） |
| `daily/<SYMBOL>.csv` | date | 187 个合约完整日线（字段见上表，日期 YYYYMMDD） |
| `event_calendar.csv` | symbol | 事件日历 181 条：t_prevmonth/t_delimonth（YYYYMMDD）、margin_rate_base、prev_/deli_ 前缀的 band/oi/ret 对照列 |
| `experiment_result.csv` | symbol | 对照实验：sample（current/early）、A_/B_ 前缀的 margin_int/vol_exposure/worst_day/n_days_exposed |
| `case_analysis.csv` | symbol | 漏报A 明细：worst_date、worst_ret、before_Tprev（bool） |

**日期格式约定**：平台入参与 daily 均为 YYYYMMDD；`future_detail.csv` 原始输出为 YYYY-MM-DD，`build_calendar.py` 读入时统一去横线。

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `PANDA_DATA_USERNAME` | 是 | Panda data 账号 |
| `PANDA_DATA_PASSWORD` | 是 | Panda data 密码 |

## 默认配置（analysis/pull_data.py）

- **品种**：RB + HC；**窗口**：2009-01-01 至今（RB 上市年，HC 2014 上市，多余窗口无害）
- **限速**：0.15 秒/次；**分段**：日线按 5 年窗切分
- **幂等**：已有产出文件自动跳过，断点标记 `.done` 支持续传
