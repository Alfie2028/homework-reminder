# 作业提醒（头歌 / MOOC）

大三考研党专用：云端定时检测头歌(educoder.net)与中国大学MOOC的作业状态，有变化/临近截止时通过 **Server酱** 推送到**微信**（方糖服务号）。无UI看板，手机只收推送。

## 原理

- **两级抓取**：课程列表 → 逐课作业（头歌作业分三类：图文作业/分组作业/实训作业，逐类合并）
- **签名自动计算**：头歌接口要求每个请求带 `X-EDU-Signature` 签名（否则返回 `-102`），签名算法已逆向，代码自动生成，**无需手动抓包**
- **Cookie 鉴权**：登录后拿 `autologin_trustie`（长期「自动登录」令牌）+ `_educoder_session`（会话）
- **状态比对**：SQLite 保存上次快照，本次 vs 上次做变化检测，无变化不重复推送

## 目录结构

```
作业提醒/
├── .github/workflows/
│   ├── homework-check.yml          # 每3小时: 只推变化+紧急
│   └── homework-daily-summary.yml  # 每天早8点: 推汇总清单
├── src/
│   ├── config.py                   # 配置读取(文件+环境变量)
│   ├── pusher.py                   # 推送器(Server酱/企业微信)
│   ├── store.py                    # SQLite状态快照
│   ├── main.py                     # 主流程编排
│   └── fetchers/
│       ├── base.py                 # BaseFetcher + Course/Homework
│       └── educoder.py             # 头歌抓取器(签名+解析已实现)
├── config.json                     # 本地配置(已gitignore)
├── config.example.json
└── requirements.txt                # 仅 requests
```

## 功能

- 作业状态检测：未写 / 已提交 / 已批改
- DDL 分级推送：提前 **3天 / 1天 / 3小时** 三档
- 变化即时推送：新作业上线、状态更新
- 每日汇总推送：早8点浓缩清单
- Cookie 失效自动提醒（401/403 时推"请更新Cookie"）
- MOOC 互评提醒（二期）

## 部署步骤

### 1. Server酱（推送到微信）
1. 打开 https://sct.ftqq.com → 用 **GitHub 账号登录**
2. 微信扫码关注「方糖」服务号
3. 复制页面上的 **SendKey**（形如 `SCTxxxx`）

> 备选：也可用企业微信群机器人（群 → 群机器人 → 复制 Webhook），把 `wecom_webhook` 填进配置。

### 2. 获取头歌 Cookie
1. Chrome/Edge 登录 https://www.educoder.net
2. `F12` → **Network** → 刷新页面 → 点任一 `data.educoder.net/api` 请求
3. 复制请求头里的 `Cookie:` 整段（含 `autologin_trustie=...; _educoder_session=...`）

> 安全：这是账号登录凭证，只放进自己的私有仓库 Secret，不外传。

### 3. 部署到 GitHub Actions
1. 推到一个**私有仓库**
2. **Settings → Secrets and variables → Actions** 新建：
   - `EDUCODER_COOKIE` = 头歌完整 Cookie
   - `EDUCODER_USERNAME` = `pn3kvxzay`
   - `SERVERCHAN_KEY` = Server酱 SendKey
   - `EDUCODER_PASSWORD` = （可选，自动登录暂未启用）
3. **Actions → homework-check → Run workflow** 手动触发一次
4. 手机微信收到推送即成功

### 4. Cookie 过期维护
- 收到"⚠️ Cookie 失效"推送后，重新抓 Cookie → 更新 Secret → 重新 Run
- `autologin_trustie` 是长期令牌，通常可维持较久；`_educoder_session` 过期后会触发提醒

## 本地运行（调试用）

```bash
cd 作业提醒
pip install -r requirements.txt
# 方式A: 填 config.json（已填好 cookie，复制自 config.example.json 补全）
python -m src.main --force-summary
# 方式B: 环境变量
$env:EDUCODER_COOKIE="xxx"; $env:EDUCODER_USERNAME="pn3kvxzay"; $env:SERVERCHAN_KEY="SCTxxxx"; python -m src.main
```

> Windows 调试若中文乱码，先 `$env:PYTHONIOENCODING="utf-8"`

## 已知限制

- **MOOC 二期**：中国大学MOOC 按课程分入口、有同伴互评（提交截止/互评开启/互评截止三段时间线），本期未实现
- **密码自动登录**：登录密码加密算法已逆向出 key，但尚有一处细节未确认，暂以 `autologin_trustie` Cookie 作为长期登录方式
- 已结束的课程作业会显示为"已过期X天"，属正常（当前无活跃学期）

## 时间说明

- 截止时间解析支持多种格式，解析失败显示"无DDL"
- GitHub Actions 的 cron 为 UTC，北京时间 +8（workflow 已换算）
