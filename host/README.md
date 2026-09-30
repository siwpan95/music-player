# Music Player · Cordis Host

基于 **Cordis 架构**重构的音乐播放器内核，全量 Node.js 重写，零 npm 依赖，本地 Web UI。

## 架构

```
app.js                    入口：装配 root Context、注册服务、加载插件
src/
  core/index.js           零依赖的 Cordis 兼容内核（Context / Service / 事件总线 / inject / dispose）
  kernel.js               VLC RC 控制器（框架无关，可直接单测/复用）
  services/
    player.js             PlayerService —— 包装 kernel，转发 player/* 事件
    playlist.js           PlaylistService —— 队列 + 播放模式 + 自动切歌
  plugins/
    webui.js              node:http 静态页 + REST + SSE 实时推送
    example.js            扩展点示例插件（订阅事件总线即可）
public/index.html         浏览器 UI（单文件，SSE 实时更新）
test/
  playlist.test.mjs       播放模式纯函数 + 服务逻辑离线单测（无 VLC）
  e2e.mjs                 端到端验证（真实 VLC 播放 + Web API + 自动切歌）
```

分层与职责：

- **core**：DI 作用域 + 生命周期 + 全局事件总线。`provide(name)` 把服务挂到 root 上下文，兄弟插件经 `get(name)` 解析；`on/emit` 走 root 全局总线。
- **kernel**：只跟 VLC RC 协议打交道（进程拉起、TCP 命令、状态/进度轮询、`End` 检测），不 import Cordis。
- **services**：把 kernel 包装成命名服务，并把底层事件转发成 `player/*`、`playlist/*` 总线事件。
- **plugins**：函数 `(ctx, config)`，订阅总线、暴露 REST/SSE，即可扩展功能。

## 为什么是"零依赖兼容内核"

本机离线（npm 不可达），本地 `E:\cordis` 源码需 `@cordisjs/cosmokit` + 构建工具才能跑。故 `src/core/index.js` 按本地源码语义重写了一个最小可用的 Cordis 子集。

**可切换**：联网后把 `app.js` 里唯一的一处 import 换成真实框架即可，其余代码不动：

```js
// import { Context, Logger } from './src/core/index.js';
import { Context, Logger } from 'cordis';   // 切换为真实 @cordisjs/core
```

## 运行

前置：本机装有 VLC（默认 `E:/VLC/vlc.exe`），Node ≥ 22。

```bash
node app.js            # 启动 host，默认 http://127.0.0.1:19718
```

环境变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `VLC_PATH` | `E:/VLC/vlc.exe` | VLC 可执行文件 |
| `VLC_RC_PORT` | `18199` | VLC RC 端口 |
| `WEB_PORT` | `19718` | Web UI 端口 |
| `WEB_HOST` | `127.0.0.1` | Web UI 绑定地址 |
| `PLAY_MODE` | `sequential` | 初始播放模式 |
| `VLC_DEBUG` | — | 置 `1` 打印原始 RC 收发 |

## Web API

| 端点 | 说明 |
| --- | --- |
| `GET /api/status` | 播放器 + 播放列表合并状态 |
| `GET /api/playlist` | 列表 / 当前索引 / 模式 |
| `GET /api/stream` | SSE 实时状态推送 |
| `POST /api/play?index=N` | 播放指定曲目（无 index 则恢复当前） |
| `POST /api/pause` `POST /api/stop` | 暂停 / 停止 |
| `POST /api/next` `POST /api/prev` | 下一曲 / 上一曲 |
| `POST /api/seek?f=0.5` `?ms=1500` | 定位（比例 / 毫秒） |
| `POST /api/volume?v=0-100` `POST /api/mute?m=1` | 音量 / 静音 |
| `POST /api/mode?m=loop` | 播放模式（sequential/loop/single/random） |
| `POST /api/add` | 添加曲目（JSON `{path,title}` 或 `{paths:[...]}`） |
| `POST /api/remove?index=N` | 移除曲目 |

## 已验证的 VLC RC 协议要点（实测）

- 拉起：`vlc --intf=dummy --extraintf=rc --rc-host=127.0.0.1:PORT --no-video --no-osd`
- 音量满量程 **256 == 100%**；状态码 `3` 播放 / `4` 暂停 / `5` 停止 / `6` 结束 / `7` 错误
- `get_length` / `get_time` 返回**裸秒数**
- `seek <sec>` 是**绝对秒**
- **结束信号**：`status change: ( play state: 4 ): End`（`: End` 后缀区分"播完"与"手动暂停"）
- **`pause` 是开关（toggle）**，且 `play` 命令**不会**从暂停态恢复 —— 恢复要再发 `pause`
- **暂停态下 `clear/add/play` 不会重启**（进度冻结），须先 toggle 出暂停再 reload

## 测试

```bash
node test/playlist.test.mjs   # 离线单测（播放模式逻辑 + 自动切歌接线）
node test/e2e.mjs             # 端到端（真实 VLC + 临时音频 + Web API + 自动切歌）
```
