# 作业提醒（头歌 / 中国大学MOOC）

> 大三考研党专用的作业状态云端检测工具：定时抓取**头歌（educoder.net）**与**中国大学MOOC（icourse163.org）**的作业/测验状态，发现**未提交**且**临近截止**的作业时，通过 **Server酱** 推送到你的**微信**。无 UI 看板，手机只收推送。

---

## 目录

- [功能特性](#功能特性)
- [支持平台](#支持平台)
- [工作原理](#工作原理)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [Cookie 说明](#cookie-说明)
- [定时任务](#定时任务)
- [常用命令](#常用命令)
- [常见问题 FAQ](#常见问题-faq)
- [已知限制](#已知限制)
- [免责声明](#免责声明)
- [License](#license)

---

## 功能特性

- **双平台**：头歌 + 中国大学MOOC 统一检测
- **智能筛选**：只推送「**未提交** 且 **未过期**」的作业，已提交、已过期自动过滤
- **分平台分组**：推送按 `🎓 头歌` / `📚 中国大学MOOC` 两大类展示，方便定位
- **DDL 分级提醒**：提前 **3天 / 1天 / 3小时** 三档提醒
- **变化检测**：新作业上线、截止时间变化时即时推送
- **每日汇总**：每天固定时间推送未提交作业清单（按截止时间排序）
- **Cookie 自动刷新**：登录凭证失效后自动重新登录，无需手动复制
- **SQLite 状态比对**：上次 vs 本次快照比对，无变化不重复推送

---

## 支持平台

| 平台 | 说明 | 作业类型 |
|------|------|---------|
| **头歌**（educoder.net） | 高校实践教学平台 | 图文作业、分组作业、实训作业 |
| **中国大学MOOC**（icourse163.org） | 网易+高教社 | 单元测验、单元作业（含同伴互评） |

---

## 工作原理

### 头歌（educoder）

- 每个请求需携带 `X-EDU-Signature` 签名，算法为 `md5(btoa("method=GET&ak=..&sk=..&time=.."))`，密钥为前端 JS 公开硬编码（已逆向并内置）
- 登录 Cookie：`autologin_trustie`（长期）+ `_educoder_session`（会话）
- 两级抓取：课程列表 → 逐课作业（图文/分组/实训三类合并）

### 中国大学MOOC（icourse163）

- RPC 接口：`POST /web/j/{Bean}.{method}.rpc?csrfKey=...`，`csrfKey` = Cookie 里的 `NTESSTUDYSI`
- **关键坑**：课程详情接口必须携带 **HttpOnly Cookie**（`STUDY_SESS`/`STUDY_PERSIST` 等），否则返回 `{"code":0,"result":null}`（成功码但空结果，极误导）。这些 Cookie `document.cookie` 看不到，需从浏览器 DevTools 或自动登录脚本获取
- 作业时间线（同伴互评）：提交截止 / 互评开启 / 互评截止（三段时间线已抓取）

---

## 目录结构

```
作业提醒/
├── src/
│   ├── main.py                 # 主流程：抓取 → 筛选 → 比对 → 推送
│   ├── config.py               # 配置读取（config.json + 环境变量）
│   ├── pusher.py               # 推送器（Server酱 / 企业微信）
│   ├── store.py                # SQLite 状态快照
│   └── fetchers/
│       ├── base.py             # BaseFetcher + Course/Homework 数据类
│       ├── educoder.py         # 头歌抓取器（签名+解析）
│       └── mooc.py             # 中国大学MOOC抓取器
├── refresh_cookies.py          # Cookie 自动刷新（自动登录两平台）
├── check_username.py           # 头歌用户名检查/修正
├── config.json                 # 本地配置（已 gitignore，含敏感信息）
├── config.example.json         # 配置模板
├── requirements.txt            # 依赖
└── README.md
```

---

## 快速开始

### 0. 环境要求

- Python 3.9+（推荐 3.10+）
- Windows（定时任务用任务计划程序；Linux/macOS 可用 crontab）

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install playwright   # 用于 Cookie 自动刷新（使用系统 Edge，无需下载 Chromium）
```

> 如果你不想用自动刷新（手动复制 Cookie），可以不装 playwright。

### 2. 准备配置

```bash
# 复制模板
copy config.example.json config.json   # Windows
cp config.example.json config.json     # Linux/macOS
```

编辑 `config.json`，至少填：

| 字段 | 必填 | 说明 |
|------|------|------|
| `login_phone` | 是 | 你的手机号（头歌/MOOC 登录用） |
| `login_password` | 是 | 你的密码 |
| `serverchan_key` | 是 | Server酱 SendKey（见下） |
| `educoder_username` | 否 | 头歌用户名，可留空，用 check_username.py 自动探测 |

**获取 Server酱 SendKey**：打开 https://sct.ftqq.com → GitHub 登录 → 微信扫码关注「方糖」服务号 → 复制 `SCTxxxx` 开头的 SendKey。

### 3. 自动登录获取 Cookie

```bash
python refresh_cookies.py --force   # 强制登录两个平台，自动填 Cookie 到 config.json
```

> 会弹出 Edge 浏览器窗口自动登录，约 30 秒，属正常。

### 4. 检查/修正头歌用户名

```bash
python check_username.py   # 自动探测并修正 educoder_username
```

### 5. 测试推送

```bash
python -m src.main --force-summary
```

手机微信收到「方糖」服务号的汇总消息即成功。

---

## 配置说明

`config.json` 完整字段：

| 字段 | 必填 | 说明 |
|------|------|------|
| `educoder_cookie` | 否 | 头歌 Cookie，留空由 refresh_cookies.py 自动填 |
| `educoder_username` | 是 | 头歌内部用户名（不是手机号，见 check_username.py） |
| `educoder_password` | 否 | 预留（密码自动登录未启用） |
| `mooc_cookie` | 否 | 中国大学MOOC Cookie，留空自动填 |
| `login_phone` | 是 | 手机号（自动登录用） |
| `login_password` | 是 | 密码（自动登录用） |
| `serverchan_key` | 是 | Server酱 SendKey |
| `wecom_webhook` | 否 | 企业微信机器人（备选推送渠道） |
| `timezone` | 否 | 时区，默认 Asia/Shanghai |

> ⚠️ `config.json` 含敏感信息，**已被 .gitignore 排除，不要提交到公开仓库**。

---

## Cookie 说明

### 为什么要 Cookie

两个平台都需要登录后才能访问作业数据，Cookie 就是登录凭证。

### 自动刷新（推荐）

`refresh_cookies.py` 会：
1. 检测当前 Cookie 是否仍有效
2. 失效时自动登录两个平台
3. 提取 Cookie（含 HttpOnly）并写回 `config.json`

```bash
python refresh_cookies.py           # 检测过期，只在失效时重新登录
python refresh_cookies.py --force   # 强制重新登录
```

### 手动获取（备选）

**头歌**：登录 educoder.net → F12 → Network → 刷新 → 点任一 `data.educoder.net/api` 请求 → 复制请求头 `Cookie:` 整段。

**中国大学MOOC**：登录 icourse163.org → F12 → Application → Cookies → 复制 `NTESSTUDYSI`、`STUDY_SESS`、`STUDY_PERSIST`、`STUDY_INFO`、`NTES_YD_SESS`、`NTES_YD_PASSPORT` 这 6 个拼成 `name=value; ...` 串（**务必含 HttpOnly 的那几个，且值带双引号的原样保留**）。

---

## 定时任务

### Windows（任务计划程序）

本项目默认用 Windows 任务计划，三个任务：

| 任务名 | 频率 | 作用 | 错过补跑 |
|--------|------|------|---------|
| `homework-check` | 每 3 小时 | 检查，有变化/临截止才推 | 否 |
| `homework-summary` | 每天 12:30 | 推送未提交作业汇总 | 是 |
| `homework-refresh-cookie` | 每天 8:00 | 检测并刷新 Cookie | 是 |

手动注册示例：

```powershell
# 每 3 小时检查
schtasks /Create /F /TN "homework-check" /TR "路径\run.bat" /SC HOURLY /MO 3
# 每天 12:30 汇总
schtasks /Create /F /TN "homework-summary" /TR "路径\run-summary.bat" /SC DAILY /ST 12:30
# 每天 8:00 刷 Cookie
schtasks /Create /F /TN "homework-refresh-cookie" /TR "路径\refresh.bat" /SC DAILY /ST 08:00
```

> `.bat` 文件需自行创建（内容见下），或用 `schtasks` 直接指向 `python`。

`run.bat` 内容：
```bat
@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -m src.main
```

`run-summary.bat` 内容：
```bat
@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -m src.main --force-summary
```

`refresh.bat` 内容：
```bat
@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python refresh_cookies.py
```

### Linux/macOS（crontab）

```bash
# 每 3 小时检查
0 */3 * * * cd /path/to/项目 && python -m src.main
# 每天 12:30 汇总
30 12 * * * cd /path/to/项目 && python -m src.main --force-summary
# 每天 8:00 刷 Cookie
0 8 * * * cd /path/to/项目 && python refresh_cookies.py
```

---

## 常用命令

```bash
python -m src.main                 # 检查模式（有变化/临截止才推）
python -m src.main --force-summary # 强制推送汇总
python refresh_cookies.py          # 检测并刷新 Cookie（失效才重登）
python refresh_cookies.py --force  # 强制刷新 Cookie
python check_username.py           # 检查/修正头歌用户名
python check_username.py --set xxx # 手动指定用户名
```

---

## 常见问题 FAQ

**Q：为什么 GitHub Actions 用不了？**
A：educoder 会屏蔽境外 IP（GitHub Actions 跑在美国 Azure 机房），会返回 401/403。请本地运行（Windows 任务计划 / crontab）。

**Q：收到「Cookie 失效」推送怎么办？**
A：自动刷新任务会处理；也可手动 `python refresh_cookies.py --force`。

**Q：`refresh_cookies.py` 弹浏览器窗口正常吗？**
A：正常。用可见浏览器是为了绕过反爬（headless 容易被检测），失效时才弹，约 30 秒。

**Q：中途新增/更换了课程会怎样？**
A：每次运行都会重新拉课程列表，新课程自动生效，无需改动。

**Q：MOOC 的 HttpOnly Cookie 为什么手动复制不到？**
A：HttpOnly Cookie 不让 JavaScript 读取（`document.cookie` 看不到），需从浏览器 DevTools 的 Cookies 面板，或用 `refresh_cookies.py` 自动拿。

**Q：为什么只推「未提交」的作业？**
A：本项目目的是提醒你**还没做**的作业，已提交/已过期的对你无价值，已自动过滤。

---

## 已知限制

- **MOOC 同伴互评**：三段时间线（提交截止/互评开启/互评截止）已抓取，但目前只按「提交截止」提醒，互评开启/截止单独提醒待实现
- **头歌密码自动登录**：密码加密算法已逆向出 key 但解密验证差一步，暂用 `autologin_trustie` 长期令牌 + `refresh_cookies.py` 兜底
- **反爬风险**：两平台可能调整接口/签名，失效时需更新对应 fetcher

---

## 免责声明

本项目仅供个人学习自动化使用。抓取第三方平台数据可能违反其服务条款，请遵守平台规则、合理使用，使用本项目产生的一切后果由使用者自行承担。

---

## License

MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
