# 作业提醒

一个我自己在用的作业提醒脚本。定时抓取**头歌（educoder.net）**和**中国大学MOOC（icourse163.org）**上的作业，发现有**没提交**或者**快截止**的，就通过 Server酱 推到微信。手机只收推送，没有别的花哨界面。

写它纯粹是为了解决我自己的问题——考研复习，平时顾不上天天盯着两个平台看作业，一不留神就错过截止时间。如果你也有同样的烦恼，拿去用就行。

## 快速开始

### 1. 装依赖

```bash
pip install -r requirements.txt
pip install playwright   # 自动刷新 Cookie 用，会调系统 Edge 浏览器
```

不想用自动刷新（愿意手动复制 Cookie）的话，playwright 可以不装。

### 2. 准备配置

复制一份配置：

```bash
cp config.example.json config.json
```

改 `config.json`，最少填这几项：

- `login_phone`：你的手机号（头歌和MOOC登录都用它）
- `login_password`：密码
- `serverchan_key`：Server酱 的 SendKey
- `educoder_username`：头歌用户名，可以留空，用 `check_username.py` 自动探测

Server酱 的 SendKey 去 https://sct.ftqq.com 登录（GitHub 登录）→ 微信扫码关注「方糖」→ 复制 `SCT` 开头那串。

> 注意：`config.json` 里有你的登录信息，已经被 .gitignore 排除了，别手滑传上去。

### 3. 自动登录拿 Cookie

```bash
python refresh_cookies.py --force
```

会弹出一个 Edge 窗口自动登录两个平台，大约半分钟，别慌，是正常的。跑完 Cookie 就自动写进 `config.json` 了。

### 4. 检查头歌用户名

```bash
python check_username.py
```

头歌 API 用的是内部用户名（类似 `pn3kvxzay` 这种），不是手机号。这个脚本会自动登录、从你的账号里探测出正确用户名，跟配置里比对，不对就自动改。

### 5. 测试

```bash
python -m src.main --force-summary
```

微信收到「方糖」的汇总消息就说明通了。

## 它做了什么

- 同时盯头歌和中国大学MOOC两个平台
- 只关心「没提交」且「没过期」的作业，交过的、过期了的自动过滤掉
- 推送按平台分成「头歌」和「中国大学MOOC」两组，一眼能看出是哪边的
- 截止前 3 天 / 1 天 / 3 小时各提醒一次
- 有新作业上线、截止时间变动也会推
- 每天固定时间推一次未提交清单
- 登录 Cookie 失效了会自己重新登录，不用手动折腾

## 支持什么

| 平台 | 作业类型 |
|------|---------|
| 头歌（educoder.net） | 图文作业、分组作业、实训作业 |
| 中国大学MOOC（icourse163.org） | 单元测验、单元作业（含同伴互评） |

## 原理（写给想折腾的人）

这两个平台都没有公开 API，我是逆向前端 JS 抓出来的接口，简单说下：

**头歌**每个请求都要带一个 `X-EDU-Signature` 签名，算法是 `md5(btoa("method=GET&ak=..&sk=..&time=.."))`，密钥是前端 JS 里写死的（已经内置到代码里了）。登录用 `autologin_trustie`（长期）+ `_educoder_session`（会话）两个 Cookie。

**中国大学MOOC**用的是 RPC 接口，`csrfKey` 就是 Cookie 里的 `NTESSTUDYSI`。这里有个很坑的点：课程详情接口必须带上 **HttpOnly Cookie**（`STUDY_SESS`/`STUDY_PERSIST` 那几个），否则接口返回 `{"code":0,"result":null}`——看着像成功，其实数据是空的，特别误导人。这些 HttpOnly Cookie 用 `document.cookie` 是拿不到的，得从浏览器 DevTools 的 Cookie 面板，或者干脆用我写的自动登录脚本。

## 目录结构

```
作业提醒/
├── README.md                # 项目说明（就是你现在看的这个）
├── LICENSE                  # MIT 协议
├── requirements.txt         # Python 依赖清单
├── .gitignore               # git 忽略规则（排除 config.json、.bat、data 等）
├── config.example.json      # 配置模板，复制一份改名 config.json 使用
├── config.json              # 本地配置，含登录信息（已 gitignore，不提交）
├── refresh_cookies.py       # 自动登录刷新 Cookie（含 HttpOnly 那几个）
├── check_username.py        # 检查/修正头歌用户名
├── run.bat                  # 双击跑「检查」模式（本地文件，未提交）
├── run-summary.bat          # 双击跑「汇总」模式（本地文件，未提交）
├── refresh.bat              # 双击刷新 Cookie（本地文件，未提交）
├── data/                    # 运行后自动生成，存 SQLite 状态快照（已 gitignore）
│   └── state.sqlite3
└── src/
    ├── __init__.py          # 包标记
    ├── main.py              # 主流程：抓取 → 过滤 → 比对 → 推送
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

我这边用 Windows 任务计划，挂了三个任务：

| 任务 | 频率 | 干什么 |
|------|------|--------|
| 检查 | 每 3 小时 | 有变化 / 临截止才推 |
| 汇总 | 每天 12:30 | 推未提交清单 |
| 刷 Cookie | 每天 8:00 | 检测失效自动重登 |

Windows 下用 `schtasks` 注册，Linux/macOS 用 crontab 也行，命令自己套一下。

## 踩过的坑

- **GitHub Actions 用不了**：头歌会封境外 IP（GitHub Actions 跑在美国 Azure 机房），返回 401/403。所以这项目只能本地跑。
- **HttpOnly Cookie**：MOOC 那几个关键 Cookie 是 HttpOnly，`document.cookie` 拿不到，别在那上面浪费时间。
- **headless 浏览器容易被反爬**：所以自动登录用的是可见浏览器窗口。
- **中途换课程/换学期**：不用管，每次运行都会重新拉课程列表，新课程自动生效。

## 已知的问题

- MOOC 的同伴互评只按「提交截止」提醒，互评开启/截止的两段提醒还没做（数据已经抓到了，后面补）
- 头歌的密码自动登录还没做成纯 requests 的（加密差最后一步），暂时靠 `autologin_trustie` 长期令牌 + 自动登录脚本兜底
- 平台改了接口/签名就得更新对应的 fetcher，没人能保证一直稳定

## 免责声明

这脚本是我自己学习用着方便的，抓取第三方平台数据可能违反它们的服务条款。用之前自己掂量，出了啥问题自己担着。

## License

MIT
