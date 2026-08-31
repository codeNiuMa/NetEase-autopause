# NetPause

一个轻量级的 Windows 音频自动暂停工具。

当你正在使用网易云音乐听歌时，如果打开 Chrome、Edge、PotPlayer、哔哩哔哩等白名单中的视频/播放器，并开始播放声音，NetPause 会自动暂停网易云音乐；当这些程序停止播放后，NetPause 会自动恢复网易云音乐。

适合一边听音乐、一边浏览网页和观看视频的使用场景。

---

## 功能特点

- 🎵 自动检测网易云音乐播放状态
- ▶ 自动检测视频/播放器是否正在发声
- ⏸ 检测到视频声音后自动暂停网易云
- ▶ 视频停止后自动恢复网易云
- ✅ 应用白名单机制
- 🔊 托盘菜单实时查看当前正在发声的程序
- 🟢 启用/禁用状态使用不同托盘图标
- ⚡ 自适应音频检测频率，降低后台 CPU 占用
- 📝 日志按天自动切割
- 🗑 自动清理旧日志
- 🔒 单实例运行，防止重复启动多个后台进程
- 🖥 完全本地运行，不需要网络服务
- 📦 无需修改网易云音乐客户端

---

# 工作原理

NetPause 基于 Windows Core Audio API 获取当前系统中的音频 Session，并通过 `IAudioMeterInformation` 判断各个程序当前是否真的正在输出声音。

基本流程：

```text
网易云音乐正在播放
        │
        ▼
监测 Windows 音频 Session
        │
        ▼
发现白名单程序开始发声
        │
        ▼
持续确认一段时间
        │
        ▼
暂停网易云音乐
        │
        ▼
持续监听白名单程序
        │
        ▼
白名单程序停止发声
        │
        ▼
等待静音确认时间
        │
        ▼
恢复网易云音乐
```

NetPause 不会因为所有系统声音都暂停音乐。

只有配置在白名单中的程序才会触发自动暂停，例如：

```python
TRIGGER_APPS = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",

    "potplayermini64.exe",
    "potplayermini.exe",
    "potplayer64.exe",
    "potplayer.exe",

    "vlc.exe",
    "mpv.exe",

    "bilibili.exe",
}
```

因此微信、QQ、钉钉、游戏和 Windows 系统提示音默认不会影响网易云音乐。

---

# 系统要求

推荐环境：

```text
Windows 10 / Windows 11
Python 3.10+
Python 3.11 推荐
```

项目目前仅针对 Windows。

因为音频检测依赖 Windows Core Audio API，所以不支持 Linux / macOS。

---

# 安装

## 1. 克隆项目

```bash
git clone https://github.com/codeNiuMa/NetPause.git

cd NetPause
```

如果直接下载 ZIP，也可以解压后运行。

---

## 2. 创建 Python 环境

推荐使用 Conda：

```bash
conda create -n netpause python=3.11

conda activate netpause
```

---

## 3. 安装依赖

```bash
pip install pycaw comtypes keyboard pystray pillow
```

也可以使用：

```bash
pip install -r requirements.txt
```

推荐项目中创建：

```text
requirements.txt
```

内容：

```txt
pycaw
comtypes
keyboard
pystray
Pillow
```

---

# 网易云音乐设置

NetPause 使用网易云音乐的 **全局播放/暂停快捷键** 控制音乐。

默认配置：

```python
MUSIC_HOTKEY = "ctrl+alt+["
```

因此需要在网易云音乐中设置对应的全局快捷键。

进入：

```text
网易云音乐
→ 设置
→ 快捷键
→ 播放 / 暂停
```

设置为：

```text
Ctrl + Alt + [
```

如果你使用其他快捷键，只需要修改：

```python
MUSIC_HOTKEY = "ctrl+alt+["
```

即可。

---

# 运行

调试运行：

```bash
python netpause.py
```

程序启动后，会在 Windows 系统托盘出现 NetPause 图标。

右键托盘图标：

```text
☑ 启用自动暂停
────────────────
当前正在发声
    ├─ ♫ cloudmusic.exe
    ├─ ▶ chrome.exe [触发]
    └─ wechat.exe
────────────────
查看今日日志
打开日志目录
────────────────
退出
```

其中：

```text
♫ cloudmusic.exe
```

表示网易云音乐正在发声。

```text
▶ chrome.exe [触发]
```

表示 Chrome 正在发声，并且属于自动暂停白名单。

普通的：

```text
wechat.exe
```

表示该程序虽然正在发声，但不会触发网易云暂停。

---

# 后台静默运行

正式使用时推荐通过 `pythonw.exe` 启动，这样不会显示 CMD 窗口。

例如创建：

```text
start_netpause.bat
```

内容：

```bat
@echo off
start "" "C:\Path\To\pythonw.exe" "C:\Path\To\netpause.py"
```

Conda 环境示例：

```bat
@echo off
start "" "D:\code\Miniconda\envs\py311\pythonw.exe" "D:\code\NetPause\netpause.py"
```

双击 BAT 后：

```text
CMD 窗口一闪而过
        ↓
NetPause 后台运行
        ↓
系统托盘出现图标
```

---

# 应用白名单

只有 `TRIGGER_APPS` 中的程序会触发自动暂停。

配置位置：

```python
TRIGGER_APPS = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",

    "potplayermini64.exe",
    "potplayermini.exe",
    "potplayer64.exe",
    "potplayer.exe",

    "vlc.exe",
    "mpv.exe",

    "bilibili.exe",
}
```

例如添加腾讯视频：

```python
TRIGGER_APPS = {
    "chrome.exe",
    "msedge.exe",
    "qqlive.exe",
}
```

不知道某个播放器真实的进程名时，可以直接：

```text
播放该程序的声音
        ↓
右键 NetPause
        ↓
当前正在发声
```

即可看到对应的 `.exe` 名称。

---

# 浏览器说明

Windows Core Audio API 通常只能识别到浏览器进程，例如：

```text
chrome.exe
msedge.exe
firefox.exe
```

而不能直接判断声音来自哪个标签页。

因此，如果把：

```python
"chrome.exe"
```

加入白名单，则 Chrome 中任何网页声音都会被认为是触发音频。

例如：

```text
Bilibili
YouTube
网页视频
网页游戏
在线会议
```

都会触发 NetPause。

---

# 音频检测参数

可以根据自己的使用习惯调整：

```python
AUDIO_THRESHOLD = 0.002

TRIGGER_START_CONFIRM = 0.7

TRIGGER_STOP_CONFIRM = 2.5

PAUSE_GRACE_TIME = 1.2
```

### `AUDIO_THRESHOLD`

判断程序是否正在发声的音量阈值：

```python
AUDIO_THRESHOLD = 0.002
```

如果发现极小的背景声音也会触发，可以提高，例如：

```python
AUDIO_THRESHOLD = 0.005
```

---

### `TRIGGER_START_CONFIRM`

白名单程序连续发声多久后才暂停网易云：

```python
TRIGGER_START_CONFIRM = 0.7
```

这样可以避免很短的声音触发暂停。

例如：

```text
网页“叮”一下
```

通常不会暂停网易云。

---

### `TRIGGER_STOP_CONFIRM`

白名单程序停止发声多久后才恢复网易云：

```python
TRIGGER_STOP_CONFIRM = 2.5
```

这是为了避免视频中人物说话之间的短暂静音导致网易云突然恢复。

---

# 自适应轮询

为了降低后台 CPU 占用，NetPause 没有始终使用高频音频扫描。

空闲状态：

```python
IDLE_POLL_INTERVAL = 0.75
```

检测到视频播放或网易云被 NetPause 暂停时：

```python
ACTIVE_POLL_INTERVAL = 0.25
```

因此工作模式为：

```text
普通空闲
    ↓
每 0.75 秒扫描

发现触发程序
    ↓
进入活跃状态

每 0.25 秒扫描
    ↓
快速检测播放 / 停止

恢复网易云
    ↓
重新进入低频扫描
```

在保持响应速度的同时，可以减少不必要的 Windows Audio Session 查询。

---

# 日志

日志默认保存在程序所在目录：

```text
NetPause/
│
├─ netpause.py
│
├─ logs/
│   ├─ netpause.log
│   ├─ netpause.log.2026-08-30
│   ├─ netpause.log.2026-08-29
│   └─ ...
```

日志每天自动切割一次。

默认：

```python
backupCount=14
```

即保留最近 14 个历史日志文件，更早的日志自动删除。

日志示例：

```text
[2026-08-31 13:20:12] NetPause 启动
[2026-08-31 13:20:12] 网易云程序: cloudmusic.exe
[2026-08-31 13:21:03] 当前正在发声: cloudmusic.exe
[2026-08-31 13:22:16] 当前正在发声: chrome.exe, cloudmusic.exe
[2026-08-31 13:22:16] 检测到触发应用: chrome.exe
[2026-08-31 13:22:17] 确认触发应用正在播放，暂停网易云。来源: chrome.exe
[2026-08-31 13:25:41] 触发应用停止发声: chrome.exe
[2026-08-31 13:25:44] 触发音频已停止 2.5s，恢复网易云。
```

日志只在状态发生变化时记录，不会按照音频扫描频率不断写入。

---

# 单实例运行

NetPause 使用 Windows Named Mutex 保证同一时间只能存在一个实例。

因此即使连续运行：

```text
start_netpause.bat
start_netpause.bat
start_netpause.bat
```

最终仍然只有一个 NetPause 后台进程。

第二个实例检测到已有程序运行后会自动退出。

这比使用：

```text
tasklist
PID 文件
.lock 文件
```

更加可靠。

即使 NetPause 被任务管理器强制结束，Windows 也会自动回收 Mutex。

---

# 用户手动操作保护

NetPause 会记录网易云是否真正是由本程序暂停的。

例如：

```text
网易云本来就是暂停状态
        ↓
打开 Chrome 视频
        ↓
关闭 Chrome
```

NetPause 不会擅自把网易云播放起来。

只有：

```text
网易云正在播放
        ↓
NetPause 自动暂停
```

之后才拥有自动恢复的权限。

同时，如果：

```text
Chrome 正在播放
        ↓
NetPause 暂停网易云
        ↓
用户手动重新播放网易云
```

NetPause 会认为这是用户主动操作，并在当前这一轮视频播放期间停止干预。

---

# 项目结构

推荐目录：

```text
NetPause/
│
├─ netpause.py
├─ requirements.txt
├─ README.md
├─ LICENSE
├─ .gitignore
│
├─ start_netpause.bat
│
└─ logs/
```

其中 `logs/` 不建议提交到 Git。

---

# .gitignore

推荐：

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyd

# Virtual environment
venv/
.env/
.venv/

# Logs
logs/
*.log

# IDE
.idea/
.vscode/

# Windows
Thumbs.db
Desktop.ini

# Build
build/
dist/
*.spec
```

---

# 当前局限

NetPause 当前仍然是一个比较简单的个人工具，存在以下限制：

1. 仅支持 Windows。
2. 当前主要针对网易云音乐。
3. 浏览器只能识别到 `chrome.exe / msedge.exe` 等进程，不能区分具体标签页。
4. 白名单目前需要修改 Python 配置。
5. 播放/暂停依赖网易云全局快捷键。
6. 部分特殊播放器可能使用独立音频进程，需要自行加入白名单。

---

# 后续计划

计划继续增加：

- [ ] GUI 白名单管理
- [ ] 托盘直接加入/移除触发白名单
- [ ] 使用 JSON 保存用户配置
- [ ] 自定义目标音乐播放器
- [ ] 自定义暂停/恢复快捷键
- [ ] 三状态托盘图标
  - 空闲
  - 自动暂停中
  - 已禁用
- [ ] Windows 开机自动启动
- [ ] 更完善的音频 Session 缓存
- [ ] 支持更多音乐播放器
- [ ] 打包独立 Windows EXE

---

# 为什么做这个工具？

平时使用电脑时经常会出现这样的场景：

```text
网易云音乐正在播放
        ↓
打开一个网页视频
        ↓
需要手动暂停网易云
        ↓
看完视频
        ↓
又需要手动恢复网易云
```

如果一天需要重复几十次，这个操作会变得非常繁琐。

NetPause 的目标就是把这个过程变成：

```text
打开视频
    ↓
音乐自动暂停

关闭视频
    ↓
音乐自动恢复
```

同时又尽可能避免微信提示音、系统声音、游戏等无关音频造成误触发。

---

# License

如果你希望项目完全开源并允许其他人自由修改、使用和分发，可以使用 [MIT License](LICENSE)。

例如：

```text
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

建议直接在 GitHub 创建仓库时添加标准 MIT License 文件。

---

# 致谢

本项目主要使用：

- [pycaw](https://github.com/AndreMiras/pycaw) - Windows Core Audio API
- [pystray](https://github.com/moses-palmer/pystray) - Windows 系统托盘
- [Pillow](https://python-pillow.org/) - 托盘图标生成
- [keyboard](https://github.com/boppreh/keyboard) - 快捷键控制
- [comtypes](https://github.com/enthought/comtypes) - Windows COM 接口

---

如果这个小工具对你有帮助，欢迎 Star ⭐。
