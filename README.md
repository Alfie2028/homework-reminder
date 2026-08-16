# 作业提醒

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/Alfie2028/homework-reminder?style=flat-square)](https://github.com/Alfie2028/homework-reminder/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Alfie2028/homework-reminder?style=social)](https://github.com/Alfie2028/homework-reminder)

某些神人老师布置作业一声不吭，好多次都因为没有及时发现布置的作业而错过提交时间。平时顾不上天天盯着两个平台看作业，一不留神就错过截止时间。如果你也有同样的困惑，那么这个开源项目很适合你：无需打开网页，就能在后台定时抓取**头歌（educoder.net）**和**中国大学MOOC（icourse163.org）**上的作业，发现有**没提交**或**快截止**的，就通过 **Server酱（微信服务号）** 或 **企业微信群机器人 webhook** 推给你。

## 安装包（给不懂技术的同学）

不想折腾代码的同学，直接去 [Releases](https://github.com/Alfie2028/homework-reminder/releases) 下载 `作业提醒安装包.zip`，解压后双击「安装.bat」即可，全程不需要手动装 Python。装完会主动问你要不要现在发一条测试推送，当场验证微信能不能收到，不用等下一次定时。

> **注意**：从网上下载的 `.bat` 文件会被 Windows 标记为「来自网络」，双击时可能被阻止。请先右键「安装.bat」→「属性」→ 勾选「解除锁定」→「确定」，再双击。或者在该文件夹里按住 Shift 右键空白处 →「在此处打开 PowerShell 窗口」→ 输入 `Get-ChildItem -Recurse | Unblock-File` 回车，一次性解除整个文件夹的锁定。

---

## 快速开始（源码方式）

### 1. 装依赖

```bash
pip install -r requirements.txt      # 只依赖 requests
pip install playwright               # 自动登录/刷新 Cookie 用，会调系统 Edge 浏览器
```

不想用自动登录（愿意手动复制 Cookie）的话，playwright 可以不装。

### 2. 准备配置

```bash
cp config.example.json config.json
```

改 `config.json`。字段一览：

| 字段 | 说明 |
|------|------|
| `educoder_cookie` | 头歌 Cookie（`autologin_trustie` + `_educoder_session`） |
| `educoder_username` | 头歌内部用户名（形如 `pn3kvxzay`，不是手机号） |
| `educoder_phone` / `educoder_password` | 头歌账密，自动登录时用 |
| `mooc_cookie` | MOOC 完整 Cookie（含 HttpOnly 的 `STUDY_SESS` 等） |
| `mooc_phone` / `mooc_password` | MOOC 账密，自动登录时用 |
| `serverchan_key` | Server酱 SendKey（`SCT` 开头） |
| `wecom_webhook` | 企业微信群机器人 webhook（备选推送渠道） |
| `educoder_enabled` / `mooc_enabled` | 平台开关，默认都是 `true` |
| `timezone` | 预留字段，当前未生效（时间按系统本地时区处理） |

最少需要填：两个平台的 Cookie（或账密，配合自动登录）+ 一个推送渠道。`serverchan_key` 和 `wecom_webhook` 二选一，都填的话优先用 Server酱。此外**头歌还需要 `educoder_username`**（内部用户名），见下方「检查头歌用户名」。

Server酱 的 SendKey 去 https://sct.ftqq.com 登录 → 微信扫码关注「方糖」→ 复制 `SCT` 开头那串。

> 注意：`config.json` 里有你的账密和 Cookie，已经被 .gitignore 排除了，别手滑传上去。

### 3. 自动登录拿 Cookie

```bash
python refresh_cookies.py --force
```

会弹出一个 Edge 窗口自动登录两个平台，大约半分钟，别慌，是正常的。跑完 Cookie 就自动写进 `config.json` 了。不加 `--force` 则是「检测失效才重登」，适合挂在定时任务里。

### 4. 检查头歌用户名

```bash
python check_username.py
```

头歌 API 用的是内部用户名（类似 `pn3kvxzay` 这种），不是手机号。这个脚本会自动登录、从你的账号里探测出正确用户名，跟配置里比对，不对就自动改。

### 5. 测试

```bash
python -m src.main --force-summary
```

微信收到「方糖」的汇总消息（或企业微信机器人消息）就说明通了。

> 也可以跑 `python -m src.main --inspect`（巡检模式）：无论有没有待办作业都推一条当前状态，适合手动确认链路。

## 它做了什么

- 同时盯头歌和中国大学MOOC两个平台
- 只关心「未提交」且「有截止时间且未过期」的作业，交过的、过期了的自动过滤掉
- 推送按平台分成「头歌」和「中国大学MOOC」两组，分组标题和课程名都可点击跳平台首页
- **检查模式**（定时自动运行）：有新作业上线，或截止前 8 小时 / 4 小时各催一次，就推送完整未提交清单
- **汇总模式**（每天固定时间）：无论有没有变化都推一份未提交清单
- 未提交条数为 1 / 3 / 5+ / 8+ 四档时，消息里各附一句越来越「凶」的调侃话
- 登录 Cookie 失效时推送告警，另有独立定时任务每天自动重登兜底

## 支持什么

| 平台 | 作业类型 |
|------|---------|
| 头歌（educoder.net） | 图文作业、测验、分组作业、实训作业 |
| 中国大学MOOC（icourse163.org） | 单元测验、单元作业 |

## 只监测某个平台

`config.json` 里有两个开关，默认都是 `true`（两个平台都盯）：

```json
"educoder_enabled": true,
"mooc_enabled": true
```

**只想监测 MOOC、不管头歌**，把 `educoder_enabled` 改成 `false`：

```json
"educoder_enabled": false,
"mooc_enabled": true
```

改完就生效，检测（`main.py`）和刷新（`refresh_cookies.py`）都会跳过头歌，只盯 MOOC。反过来只想监测头歌，就把 `mooc_enabled` 改成 `false`。

> 不用去删 Cookie 字段——开关设成 `false` 之后，就算 Cookie 还留在 `config.json` 里也会被无视。

## 原理（写给想折腾的人）

这两个平台都没有公开 API，我是逆向前端 JS 抓出来的接口，简单说下：

**头歌**每个请求都要带一个 `X-EDU-Signature` 签名，算法是 `md5(btoa("method=GET&ak=..&sk=..&time=.."))`，密钥是前端 JS 里写死的（已经内置到代码里了）。登录用 `autologin_trustie`（长期）+ `_educoder_session`（会话）两个 Cookie。

**中国大学MOOC**用的是 RPC 接口，`csrfKey` 就是 Cookie 里的 `NTESSTUDYSI`。这里有个很坑的点：课程详情接口必须带上 **HttpOnly Cookie**（`STUDY_SESS`/`STUDY_PERSIST` 那几个），否则接口返回 `{"code":0,"result":null}`——看着像成功，其实数据是空的，特别误导人。这些 HttpOnly Cookie 用 `document.cookie` 是拿不到的，得从浏览器 DevTools 的 Cookie 面板，或者干脆用我写的自动登录脚本。

## 目录结构

```
作业提醒/
├── README.md                # 项目说明（就是你现在看的这个）
├── LICENSE                  # MIT 协议
├── requirements.txt         # Python 依赖清单（仅 requests）
├── .gitignore               # 排除 config.json、data/、生成的 .bat 等
├── .gitattributes           # 标记 .bat 为二进制，避免 GitHub 按 UTF-8 转码成乱码
├── .github/ISSUE_TEMPLATE/  # Issues 反馈模板（带上平台/系统/报错，方便排查）
├── config.example.json      # 配置模板，复制一份改名 config.json 使用
├── config.json              # 本地配置，含账密/Cookie（已 gitignore，不提交）
├── install.py               # 安装向导：选平台 → 账密 → 密钥 → 频率 → 自动登录 → 注册计划任务 → 测试推送
├── refresh_cookies.py       # 自动登录刷新 Cookie（含 HttpOnly 那几个）
├── check_username.py        # 检查/修正头歌用户名
├── 安装.bat                 # 一键安装入口：装 Python + 依赖，再调 install.py
├── 卸载.bat                 # 删除三个 Windows 计划任务
├── 使用说明.txt             # 给不懂代码同学的图文说明
├── run.bat                  # 双击跑「检查」模式（install.py 生成，未提交）
├── run-summary.bat          # 双击跑「汇总」模式（install.py 生成，未提交）
├── refresh.bat              # 双击刷新 Cookie（install.py 生成，未提交）
├── 巡检.bat                 # 双击跑「巡检」模式（install.py 生成，未提交）
├── data/                    # 运行后自动生成，存 SQLite 状态快照（已 gitignore）
│   └── state.sqlite3
└── src/
    ├── __init__.py          # 包标记
    ├── main.py              # 主流程：抓取 → 过滤 → 比对 → 分级推送
    ├── config.py            # 读取 config.json + 环境变量
    ├── pusher.py            # 推送器（Server酱 / 企业微信 webhook）
    ├── store.py             # SQLite 状态快照读写，做「上次 vs 这次」比对
    └── fetchers/
        ├── __init__.py      # 包标记
        ├── base.py          # BaseFetcher 基类 + Course/Homework 数据模型
        ├── educoder.py      # 头歌抓取器（签名逆向 + 课程/作业解析）
        └── mooc.py          # 中国大学MOOC抓取器（HttpOnly Cookie + 测验/作业解析）
```

## 定时跑

用 Windows 任务计划，`install.py` 会注册三个任务（用 `schtasks`）：

| 任务名 | 频率 | 干什么 |
|--------|------|--------|
| `homework-check` | 每 3 小时（安装时可改 1/2/3/6 小时） | 有新作业 / 临截止才推 |
| `homework-summary` | 每天 12:30（安装时可改） | 推未提交清单 |
| `homework-refresh-cookie` | 每天 8:00 | 检测失效自动重登 |

> 每日任务（`homework-summary`、`homework-refresh-cookie`）都开了「错过补跑」：如果计划时间点电脑关机/睡眠错过了，会在开机后补跑一次。

不想要这些定时任务的话，`双击「卸载.bat」` 即可全部删除。核心脚本（`src/`）是跨平台的，Linux/macOS 可用 crontab 直接跑 `python -m src.main`，但安装向导和 `.bat` 仅适用于 Windows。

## 踩过的坑

- **GitHub Actions 用不了**：头歌会封境外 IP（GitHub Actions 跑在美国 Azure 机房），返回 401/403。所以这项目只能本地跑。
- **HttpOnly Cookie**：MOOC 那几个关键 Cookie 是 HttpOnly，`document.cookie` 拿不到，别在那上面浪费时间。
- **headless 浏览器容易被反爬**：所以自动登录用的是可见浏览器窗口。
- **中途换课程/换学期**：不用管，每次运行都会重新拉课程列表，新课程自动生效。

## 已知的问题

- MOOC 的同伴互评只按「提交截止」提醒，互评开启/截止（`evaluateStart` / `evaluateEnd`）的两段提醒还没做（数据已经抓到了，后面补）
- 头歌的密码自动登录还没做成纯 requests 的（加密差最后一步），暂时靠 `autologin_trustie` 长期令牌 + Playwright 自动登录脚本兜底
- 平台改了接口/签名就得更新对应的 fetcher，没人能保证一直稳定

## 免责声明

这脚本是我自己学习用着方便的，抓取第三方平台数据可能违反它们的服务条款。用之前自己掂量，出了啥问题自己担着。

## License

MIT
