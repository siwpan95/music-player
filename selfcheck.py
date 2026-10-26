#!/usr/bin/env python3
"""无头自检：播放模式索引推进、播放列表导航、LRC 解析定位、均衡器预设。

项目的 engine/__init__.py 会 import python-vlc（缺少 libVLC 时直接抛错），
因此这里只为 music_player / engine / library / metadata 注册包壳（__path__），
直接加载不依赖 VLC 的纯逻辑模块；不创建 Tkinter 窗口。
运行：python selfcheck.py
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "music_player"


def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def install_package_shims():
    """注册不带 __init__ 副作用的包对象，绕开 python-vlc 等重量级导入。"""
    if not PACKAGE.is_dir():
        fail(f"找不到包目录: {PACKAGE}")
    top = types.ModuleType("music_player")
    top.__path__ = [str(PACKAGE)]
    top.__file__ = str(PACKAGE / "__init__.py")
    sys.modules["music_player"] = top
    for name in ("engine", "library", "metadata"):
        module = types.ModuleType(f"music_player.{name}")
        module.__path__ = [str(PACKAGE / name)]
        module.__file__ = str(PACKAGE / name / "__init__.py")
        sys.modules[f"music_player.{name}"] = module


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    install_package_shims()
    try:
        from music_player.engine.equalizer import (
            NUM_BANDS,
            PRESET_NAMES,
            clamp_bands,
            get_preset_bands,
            resolve,
        )
        from music_player.engine.media_item import MediaItem, MediaType
        from music_player.engine.play_mode import next_index, prev_index
        from music_player.engine.player_state import PlayMode
        from music_player.library.playlist_model import PlaylistModel
        from music_player.metadata.lrc_parser import LrcParser
    except Exception as exc:  # pragma: no cover
        fail(f"导入纯逻辑模块失败: {exc}")

    # ---------- 1. 播放模式：下一曲 / 上一曲索引 ----------
    seq, loop, single, rnd = (
        PlayMode.SEQUENTIAL, PlayMode.LOOP, PlayMode.SINGLE, PlayMode.RANDOM
    )
    cases = [
        (next_index(0, 3, seq, set()), 1, "顺序模式下一曲"),
        (next_index(2, 3, seq, set()), None, "顺序模式末尾停止"),
        (prev_index(0, 3, seq, []), None, "顺序模式开头停止"),
        (prev_index(1, 3, seq, []), 0, "顺序模式上一曲"),
        (next_index(2, 3, loop, set()), 0, "列表循环回绕"),
        (prev_index(0, 3, loop, []), 2, "列表循环反向回绕"),
        (next_index(1, 3, single, set()), 1, "单曲循环保持当前"),
        (prev_index(1, 3, single, []), 1, "单曲循环上一曲保持当前"),
        (next_index(0, 0, seq, set()), None, "空列表返回 None"),
        (next_index(-1, 3, seq, set()), 0, "未开始播放时从首曲开始"),
    ]
    for got, expected, label in cases:
        if got != expected:
            fail(f"{label}: 期望 {expected}，实际 {got}")

    picked = next_index(0, 3, rnd, {0})
    if picked not in (1, 2):
        fail(f"随机模式选中了已播索引: {picked}")
    played = {0, 1, 2}
    last = next_index(0, 3, rnd, played)
    if last not in (0, 1, 2) or played:
        fail("随机模式在全部播完后未重置已播集合")
    if prev_index(2, 3, rnd, [0, 2]) != 2:
        fail("随机模式上一曲未回退历史栈")

    # ---------- 2. PlaylistModel：导航与删除后的索引同步 ----------
    model = PlaylistModel()
    model.add([
        MediaItem(name="a", path="/a.mp3", item_type=MediaType.LOCAL_FILE),
        MediaItem(name="b", path="/b.mp3", item_type=MediaType.LOCAL_FILE),
        MediaItem(name="c", path="/c.mp3", item_type=MediaType.LOCAL_FILE),
    ])
    if len(model) != 3:
        fail("播放列表长度错误")
    if model.jump(0).name != "a" or model.next().name != "b" or model.next().name != "c":
        fail("播放列表顺序推进失败")
    if model.next() is not None:
        fail("顺序模式播完末尾未停止")
    model.set_mode(loop)
    if model.next().name != "a":
        fail("列表循环模式未回到首曲")
    model.set_mode(seq)
    model.jump(1)
    model.remove(0)
    if model.index() != 0 or model.current().name != "b":
        fail("删除当前曲目之前的条目后索引未同步")

    # ---------- 3. LRC 解析与二分定位 ----------
    lrc = LrcParser(text=(
        "[00:01.00]first\n"
        "[00:02.50]second\n"
        "[00:03.5]third\n"
        "[00:04.123]fourth\n"
        "[00:01.00][00:05.00]chorus\n"
    ))
    times = [ms for ms, _ in lrc.lines]
    if times != [1000, 1000, 2500, 3500, 4123, 5000]:
        fail(f"LRC 时间标签解析错误: {times}")
    if lrc.line_at(999) != -1:
        fail("LRC 首行之前应返回 -1")
    if lrc.line_at(1000) != 1 or lrc.line_at(2499) != 1 or lrc.line_at(2500) != 2:
        fail("LRC 二分定位边界错误")
    if lrc.line_at(5000) != 5 or lrc.line_at(9999) != 5:
        fail("LRC 末尾定位错误")

    # ---------- 4. 均衡器：预设完整性与增益钳制 ----------
    if NUM_BANDS != 10 or len(PRESET_NAMES) < 7:
        fail(f"均衡器预设定义异常: bands={NUM_BANDS}, presets={PRESET_NAMES}")
    for name in PRESET_NAMES:
        bands = get_preset_bands(name)
        if len(bands) != NUM_BANDS or any(g < -20 or g > 20 for g in bands):
            fail(f"均衡器预设 {name} 数据越界")
    clipped = clamp_bands([99.0, -99.0])
    if clipped[:2] != [20.0, -20.0] or len(clipped) != NUM_BANDS or any(clipped[2:]):
        fail(f"均衡器增益钳制/补齐错误: {clipped}")
    if resolve(None, None) is not None:
        fail("未指定预设与频段时应返回 None（关闭均衡器）")
    rock = resolve("rock", None)
    if rock != get_preset_bands("rock"):
        fail("预设解析结果与预设表不一致")
    if rock is get_preset_bands("rock"):
        fail("预设解析应返回独立的列表副本")
    if resolve(None, [99.0, -99.0])[:2] != [20.0, -20.0]:
        fail("自定义频段未经过钳制")

    print(
        "selfcheck ok: 四种播放模式索引推进、PlaylistModel 导航与删除后索引同步、"
        "LRC 多标签解析与二分定位、均衡器 7 套预设与增益钳制"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
