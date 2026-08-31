import os
import time
import threading
import logging
from logging.handlers import TimedRotatingFileHandler
import ctypes
import keyboard
import pystray
from PIL import Image, ImageDraw
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
import comtypes


# ============================================================
# 基础配置
# ============================================================

    # ============================================================
    # 单实例运行
    #
    # 防止重复启动多个 NetPause
    # ============================================================

MUTEX_NAME = r"Local\NetPause_SingleInstance_v1"

ERROR_ALREADY_EXISTS = 183

mutex_handle = None

# ============================================================
# 获取单实例锁
# ============================================================

def acquire_single_instance():
    """
    使用 Windows Named Mutex 保证 NetPause 只能运行一个实例。

    返回：
        True  -> 当前是第一个实例，可以继续运行
        False -> 已经有 NetPause 在运行
    """

    global mutex_handle

    kernel32 = ctypes.windll.kernel32

    # 明确声明返回值类型。
    # Windows HANDLE 在 64 位系统上是 64 位值，
    # 如果不声明 restype，ctypes 可能错误截断句柄。
    kernel32.CreateMutexW.restype = ctypes.c_void_p

    mutex_handle = kernel32.CreateMutexW(
        None,
        True,
        MUTEX_NAME
    )

    if not mutex_handle:

        logger.error(
            "创建单实例 Mutex 失败"
        )

        # Mutex 创建异常时不阻止程序启动
        return True


    error = kernel32.GetLastError()


    # 已经存在同名 Mutex
    if error == ERROR_ALREADY_EXISTS:

        kernel32.CloseHandle(
            ctypes.c_void_p(mutex_handle)
        )

        mutex_handle = None

        return False


    return True


# ============================================================
# 释放单实例锁
# ============================================================

def release_single_instance():

    global mutex_handle

    if mutex_handle is None:
        return

    try:

        kernel32 = ctypes.windll.kernel32

        kernel32.ReleaseMutex(
            ctypes.c_void_p(mutex_handle)
        )

        kernel32.CloseHandle(
            ctypes.c_void_p(mutex_handle)
        )

    except Exception:

        pass

    finally:

        mutex_handle = None
APP_NAME = "NetPause"

# 网易云进程名
MUSIC_APP = "cloudmusic.exe"

# 网易云音乐里设置的“播放 / 暂停”全局快捷键
MUSIC_HOTKEY = "ctrl+alt+["


# ============================================================
# 触发白名单
#
# 只有这些程序真正发声时，才会暂停网易云
# exe 名称统一写小写
# ============================================================

TRIGGER_APPS = {
    # 浏览器
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",

    # PotPlayer
    "potplayermini64.exe",
    "potplayermini.exe",
    "potplayer64.exe",
    "potplayer.exe",

    # 其他播放器
    "vlc.exe",
    "mpv.exe",

    # Bilibili
    "bilibili.exe",
}


# ============================================================
# 音频检测参数
# ============================================================

# 音量峰值高于这个值，认为程序正在真正发声
AUDIO_THRESHOLD = 0.002

# 白名单程序持续发声多久以后才触发暂停
TRIGGER_START_CONFIRM = 0.7

# 白名单程序持续停止多久以后才恢复网易云
TRIGGER_STOP_CONFIRM = 2.5

# 暂停网易云后的保护时间
PAUSE_GRACE_TIME = 1.2


# ============================================================
# 自适应轮询
# ============================================================

# 空闲状态
#
# 没有视频播放时降低检测频率，减少 CPU 占用
IDLE_POLL_INTERVAL = 0.75

# 活跃状态
#
# 检测到视频 / 网易云被脚本暂停时提高检测频率
ACTIVE_POLL_INTERVAL = 0.25


# ============================================================
# 日志配置
#
# 日志目录：
#
# netpause.py
# logs\
#     netpause.log
#     netpause.log.2026-08-30
#     netpause.log.2026-08-29
# ============================================================

SCRIPT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

LOG_DIR = os.path.join(
    SCRIPT_DIR,
    "netpause-logs"
)

os.makedirs(
    LOG_DIR,
    exist_ok=True
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "netpause.log"
)


logger = logging.getLogger(
    APP_NAME
)

logger.setLevel(
    logging.INFO
)

logger.propagate = False


# 防止重复添加 Handler
if not logger.handlers:

    log_handler = TimedRotatingFileHandler(
        LOG_FILE,

        # 每天凌晨切割日志
        when="midnight",

        interval=1,

        # 自动保留最近 14 天
        backupCount=14,

        encoding="utf-8",

        # 使用 Windows 本地时间
        utc=False
    )

    # 历史日志格式：
    #
    # netpause.log.2026-08-31
    log_handler.suffix = "%Y-%m-%d"

    log_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )

    logger.addHandler(
        log_handler
    )


# ============================================================
# 全局状态
# ============================================================

# 程序退出事件
stop_event = threading.Event()


# 自动暂停启用状态
enabled_event = threading.Event()

# 默认启用
enabled_event.set()


# ============================================================
# 当前正在发声的软件
#
# 用于托盘菜单动态显示
# ============================================================

current_audio_apps = set()

audio_apps_lock = threading.Lock()


# ============================================================
# 获取 Windows 音频状态
# ============================================================

def get_audio_status():
    """
    返回：

    music_audible
        网易云是否正在实际发声

    trigger_audible
        是否存在正在发声的白名单程序

    trigger_apps
        当前正在发声的白名单程序

    all_audible_apps
        当前系统所有正在发声的程序
    """

    music_audible = False

    trigger_apps = set()

    all_audible_apps = set()


    # ========================================================
    # 获取所有 Windows 音频 Session
    # ========================================================

    try:

        sessions = AudioUtilities.GetAllSessions()

    except Exception as e:

        logger.error(
            f"获取 Windows 音频 Session 失败: {e}"
        )

        return (
            False,
            False,
            set(),
            set()
        )


    # ========================================================
    # 遍历 Session
    # ========================================================

    for session in sessions:

        try:

            # ------------------------------------------------
            # 音量检测接口
            # ------------------------------------------------

            meter = session._ctl.QueryInterface(
                IAudioMeterInformation
            )


            peak = meter.GetPeakValue()


            # ------------------------------------------------
            # 没有实际声音
            # ------------------------------------------------

            if peak <= AUDIO_THRESHOLD:

                continue


            # ------------------------------------------------
            # 获取进程
            # ------------------------------------------------

            process = session.Process


            # ------------------------------------------------
            # System Sounds
            #
            # Windows 系统声音通常没有对应进程
            # 仅显示，不会参与白名单触发
            # ------------------------------------------------

            if process is None:

                all_audible_apps.add(
                    "System Sounds"
                )

                continue


            # ------------------------------------------------
            # 获取 exe 名称
            # ------------------------------------------------

            exe_name = (
                process.name().lower()
            )


            # ------------------------------------------------
            # 所有正在发声的软件
            # ------------------------------------------------

            all_audible_apps.add(
                exe_name
            )


            # ------------------------------------------------
            # 网易云
            # ------------------------------------------------

            if exe_name == MUSIC_APP:

                music_audible = True


            # ------------------------------------------------
            # 触发白名单
            # ------------------------------------------------

            elif exe_name in TRIGGER_APPS:

                trigger_apps.add(
                    exe_name
                )


        except Exception:

            # 某一个 Session 出现异常
            # 不影响整个监听程序
            continue


    trigger_audible = bool(
        trigger_apps
    )


    return (
        music_audible,
        trigger_audible,
        trigger_apps,
        all_audible_apps
    )


# ============================================================
# 更新“当前正在发声”
# ============================================================

def update_current_audio_apps(apps):

    global current_audio_apps

    with audio_apps_lock:

        current_audio_apps = (
            apps.copy()
        )


# ============================================================
# 控制网易云
# ============================================================

def send_music_hotkey():

    try:

        keyboard.press_and_release(
            MUSIC_HOTKEY
        )

        return True


    except Exception as e:

        logger.error(
            f"发送网易云快捷键失败: {e}"
        )

        return False


# ============================================================
# 音频监听线程
# ============================================================

def audio_monitor_loop():

    # pycaw / COM 在子线程中使用时
    # 必须初始化 COM
    comtypes.CoInitialize()


    logger.info(
        "=" * 60
    )

    logger.info(
        "NetPause 启动"
    )

    logger.info(
        f"网易云程序: {MUSIC_APP}"
    )

    logger.info(
        "触发白名单: "
        + ", ".join(
            sorted(TRIGGER_APPS)
        )
    )


    # ========================================================
    # 核心状态
    # ========================================================

    # True 表示：
    #
    # 网易云确实是被 NetPause 暂停的
    #
    # 只有这种情况下
    # NetPause 才有权自动恢复
    paused_by_script = False


    # ========================================================
    # 用户手动覆盖
    #
    # 场景：
    #
    # Chrome 播放视频
    # ↓
    # NetPause 暂停网易云
    # ↓
    # 用户手动重新播放网易云
    #
    # 此时尊重用户操作
    #
    # 在本轮 Chrome 停止之前
    # 不再继续强行暂停网易云
    # ========================================================

    manual_override = False


    # 暂停命令执行时间
    pause_time = 0.0


    # 白名单应用开始发声时间
    trigger_started_at = None


    # 白名单应用停止发声时间
    trigger_stopped_at = None


    # 上一次触发应用集合
    last_trigger_apps = set()


    # 上一次所有发声应用
    last_all_audio_apps = set()


    try:

        while not stop_event.is_set():


            # =================================================
            # 获取音频状态
            # =================================================

            (
                music_audible,
                trigger_audible,
                trigger_apps,
                all_audio_apps

            ) = get_audio_status()


            # =================================================
            # 更新托盘：
            #
            # 当前正在发声
            # =================================================

            update_current_audio_apps(
                all_audio_apps
            )


            # =================================================
            # 发声应用发生变化才写日志
            #
            # 防止每 0.25 秒写一条日志
            # =================================================

            if (
                all_audio_apps
                != last_all_audio_apps
            ):

                if all_audio_apps:

                    logger.info(
                        "当前正在发声: "
                        + ", ".join(
                            sorted(
                                all_audio_apps
                            )
                        )
                    )

                else:

                    logger.info(
                        "当前无程序发声"
                    )


                last_all_audio_apps = (
                    all_audio_apps.copy()
                )


            # =================================================
            # 自动暂停被禁用
            #
            # 注意：
            #
            # 即使禁用，
            # 仍然继续扫描音频，
            #
            # 因此：
            #
            # 当前正在发声
            #
            # 仍然可以正常工作。
            # =================================================

            if not enabled_event.is_set():

                trigger_started_at = None

                trigger_stopped_at = None

                last_trigger_apps = set()


                # 放弃之前暂停状态的控制权
                #
                # 防止重新启用以后
                # 突然自动恢复网易云
                paused_by_script = False

                manual_override = False


                # 禁用状态使用低频轮询
                stop_event.wait(
                    IDLE_POLL_INTERVAL
                )

                continue


            now = time.monotonic()


            # =================================================
            # 白名单应用正在发声
            # =================================================

            if trigger_audible:


                # ------------------------------------------------
                # 清空停止时间
                # ------------------------------------------------

                trigger_stopped_at = None


                # ------------------------------------------------
                # 第一次检测到声音
                # ------------------------------------------------

                if trigger_started_at is None:

                    trigger_started_at = now


                # ------------------------------------------------
                # 触发程序发生变化
                # ------------------------------------------------

                if (
                    trigger_apps
                    != last_trigger_apps
                ):

                    logger.info(
                        "检测到触发应用: "
                        + ", ".join(
                            sorted(
                                trigger_apps
                            )
                        )
                    )


                    last_trigger_apps = (
                        trigger_apps.copy()
                    )


                # ------------------------------------------------
                # 已经持续发声多久
                # ------------------------------------------------

                trigger_duration = (
                    now
                    - trigger_started_at
                )


                # =================================================
                # 自动暂停网易云
                # =================================================

                if (

                    trigger_duration
                    >= TRIGGER_START_CONFIRM

                    and music_audible

                    and not paused_by_script

                    and not manual_override

                ):

                    logger.info(
                        "确认触发应用正在播放，"
                        "暂停网易云。来源: "
                        + ", ".join(
                            sorted(
                                trigger_apps
                            )
                        )
                    )


                    if send_music_hotkey():

                        paused_by_script = True

                        pause_time = now


                # =================================================
                # 用户手动恢复网易云
                # =================================================

                elif (

                    paused_by_script

                    and music_audible

                    and (
                        now
                        - pause_time
                        > PAUSE_GRACE_TIME
                    )

                ):

                    logger.info(
                        "触发应用仍在播放，"
                        "但网易云重新发声。"
                        "认为用户进行了手动恢复，"
                        "本轮不再自动暂停。"
                    )


                    paused_by_script = False

                    manual_override = True


            # =================================================
            # 当前没有白名单程序发声
            # =================================================

            else:


                trigger_started_at = None


                # =================================================
                # 一轮视频已经结束
                #
                # 清除“用户手动覆盖”
                # =================================================

                manual_override = False


                # ------------------------------------------------
                # 触发应用刚停止
                # ------------------------------------------------

                if last_trigger_apps:

                    logger.info(
                        "触发应用停止发声: "
                        + ", ".join(
                            sorted(
                                last_trigger_apps
                            )
                        )
                    )


                    last_trigger_apps = set()


                # ------------------------------------------------
                # 开始计算静音时间
                # ------------------------------------------------

                if trigger_stopped_at is None:

                    trigger_stopped_at = now


                quiet_duration = (
                    now
                    - trigger_stopped_at
                )


                # =================================================
                # 自动恢复网易云
                # =================================================

                if (

                    paused_by_script

                    and quiet_duration
                    >= TRIGGER_STOP_CONFIRM

                ):


                    # ------------------------------------------------
                    # 网易云已经自己恢复
                    # ------------------------------------------------

                    if music_audible:

                        logger.info(
                            "网易云已经恢复播放，"
                            "取消自动恢复操作。"
                        )


                        paused_by_script = False


                    # ------------------------------------------------
                    # 网易云仍然没有声音
                    #
                    # 而且确实是我们暂停的
                    #
                    # 可以安全恢复
                    # ------------------------------------------------

                    else:

                        logger.info(
                            f"触发音频已停止 "
                            f"{quiet_duration:.1f}s，"
                            "恢复网易云。"
                        )


                        if send_music_hotkey():

                            paused_by_script = False


            # =================================================
            # 自适应轮询
            #
            # 空闲：
            #     0.75 秒
            #
            # 视频播放 / 网易云被暂停：
            #     0.25 秒
            # =================================================

            if (
                trigger_audible
                or paused_by_script
            ):

                wait_time = (
                    ACTIVE_POLL_INTERVAL
                )

            else:

                wait_time = (
                    IDLE_POLL_INTERVAL
                )


            stop_event.wait(
                wait_time
            )


    except Exception:

        logger.exception(
            "音频监听线程发生异常"
        )


    finally:

        logger.info(
            "音频监听线程退出"
        )

        comtypes.CoUninitialize()


# ============================================================
# 托盘图标
# ============================================================

def create_icon_image(enabled=True):

    """
    enabled=True

        绿色图标
        表示自动暂停功能启用


    enabled=False

        灰色 + 斜杠
        表示自动暂停功能禁用
    """


    image = Image.new(
        "RGBA",
        (64, 64),
        (0, 0, 0, 0)
    )


    draw = ImageDraw.Draw(
        image
    )


    # ========================================================
    # 启用状态
    # ========================================================

    if enabled:


        # 绿色圆形
        draw.ellipse(
            (4, 4, 60, 60),
            fill=(
                46,
                160,
                67,
                255
            )
        )


        # 白色暂停符号
        draw.rounded_rectangle(
            (19, 16, 27, 48),

            radius=2,

            fill=(
                255,
                255,
                255,
                255
            )
        )


        draw.rounded_rectangle(
            (37, 16, 45, 48),

            radius=2,

            fill=(
                255,
                255,
                255,
                255
            )
        )


    # ========================================================
    # 禁用状态
    # ========================================================

    else:


        # 灰色圆形
        draw.ellipse(
            (4, 4, 60, 60),

            fill=(
                95,
                99,
                104,
                255
            )
        )


        # 灰白暂停符号
        draw.rounded_rectangle(
            (19, 16, 27, 48),

            radius=2,

            fill=(
                210,
                210,
                210,
                255
            )
        )


        draw.rounded_rectangle(
            (37, 16, 45, 48),

            radius=2,

            fill=(
                210,
                210,
                210,
                255
            )
        )


        # 禁用斜线
        draw.line(
            (14, 14, 50, 50),

            fill=(
                235,
                235,
                235,
                255
            ),

            width=5
        )


    return image


# ============================================================
# 托盘菜单
# ============================================================

def do_nothing(icon, item):

    pass


# ============================================================
# 动态生成“当前正在发声”
# ============================================================

def create_audio_apps_menu():


    with audio_apps_lock:

        apps = sorted(
            current_audio_apps
        )


    # ========================================================
    # 当前没有声音
    # ========================================================

    if not apps:

        return (

            pystray.MenuItem(
                "（当前无程序发声）",

                do_nothing,

                enabled=False
            ),

        )


    menu_items = []


    # ========================================================
    # 动态生成程序列表
    # ========================================================

    for app in apps:


        # ----------------------------------------------------
        # 网易云
        # ----------------------------------------------------

        if app == MUSIC_APP:

            text = (
                f"♫ {app}"
            )


        # ----------------------------------------------------
        # 白名单触发程序
        # ----------------------------------------------------

        elif app in TRIGGER_APPS:

            text = (
                f"▶ {app}  [触发]"
            )


        # ----------------------------------------------------
        # 普通程序
        # ----------------------------------------------------

        else:

            text = app


        menu_items.append(

            pystray.MenuItem(
                text,

                do_nothing,

                enabled=False
            )

        )


    return tuple(
        menu_items
    )


# ============================================================
# 查看当天日志
# ============================================================

def view_log(icon, item):


    if not os.path.exists(
        LOG_FILE
    ):

        with open(
            LOG_FILE,
            "a",
            encoding="utf-8"
        ):
            pass


    os.startfile(
        LOG_FILE
    )


# ============================================================
# 打开日志目录
# ============================================================

def open_log_dir(icon, item):


    os.startfile(
        LOG_DIR
    )


# ============================================================
# 启用 / 禁用自动暂停
# ============================================================

def toggle_enabled(icon, item):


    # ========================================================
    # 当前启用 → 禁用
    # ========================================================

    if enabled_event.is_set():


        enabled_event.clear()


        # 修改托盘图标
        icon.icon = (
            create_icon_image(
                False
            )
        )


        # 修改鼠标悬停文字
        icon.title = (
            "网易云自动启停 - 已禁用"
        )


        logger.info(
            "自动暂停功能已禁用"
        )


    # ========================================================
    # 当前禁用 → 启用
    # ========================================================

    else:


        enabled_event.set()


        icon.icon = (
            create_icon_image(
                True
            )
        )


        icon.title = (
            "网易云自动启停 - 已启用"
        )


        logger.info(
            "自动暂停功能已启用"
        )


    # ========================================================
    # 更新托盘菜单勾选状态
    # ========================================================

    try:

        icon.update_menu()

    except Exception:

        pass


# ============================================================
# 菜单勾选状态
# ============================================================

def is_enabled(item):

    return (
        enabled_event.is_set()
    )


# ============================================================
# 退出
# ============================================================

def exit_app(icon, item):


    logger.info(
        "正在退出 NetPause"
    )


    stop_event.set()


    icon.stop()


# ============================================================
# 主程序
# ============================================================

def main():


    # ========================================================
    # 音频监听线程
    # ========================================================

    monitor_thread = threading.Thread(

        target=audio_monitor_loop,

        name="AudioMonitor",

        daemon=True
    )


    monitor_thread.start()


    # ========================================================
    # 动态音频菜单
    # ========================================================

    audio_apps_menu = pystray.Menu(
        create_audio_apps_menu
    )


    # ========================================================
    # 托盘菜单
    # ========================================================

    menu = pystray.Menu(


        pystray.MenuItem(
            "启用自动暂停",

            toggle_enabled,

            checked=is_enabled
        ),


        pystray.Menu.SEPARATOR,


        pystray.MenuItem(
            "当前正在发声",

            audio_apps_menu
        ),


        pystray.Menu.SEPARATOR,


        pystray.MenuItem(
            "查看今日日志",

            view_log
        ),


        pystray.MenuItem(
            "打开日志目录",

            open_log_dir
        ),


        pystray.Menu.SEPARATOR,


        pystray.MenuItem(
            "退出",

            exit_app
        )

    )


    # ========================================================
    # 创建托盘图标
    # ========================================================

    icon = pystray.Icon(

        APP_NAME,

        create_icon_image(
            True
        ),

        "网易云自动启停 - 已启用",

        menu
    )


    try:

        icon.run()


    finally:

        stop_event.set()

        logger.info(
            "NetPause 已退出"
        )


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    # ========================================================
    # 防止重复启动
    # ========================================================

    if not acquire_single_instance():

        # 已经有一个 NetPause 在后台运行
        # 第二次启动直接静默退出
        raise SystemExit(0)


    try:

        main()

    finally:

        release_single_instance()