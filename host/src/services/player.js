// Player service: wraps the VLC RC kernel and exposes it as a Cordis service
// named `player` on the root context. Also forwards kernel events onto the
// global event bus (player/state, player/position, player/end, player/current)
// so the web UI and other plugins can react.

import { Service } from '../core/index.js';
import PlayerKernel, { toVlcUri } from '../kernel.js';

export class PlayerService extends Service {
  constructor(ctx, config = {}) {
    super(ctx, 'player');
    this.kernel = new PlayerKernel({
      vlcPath: config.vlcPath || 'E:/VLC/vlc.exe',
      rcPort: config.rcPort || 18199,
      logger: ctx.logger,
      debug: !!config.debug,
    });
    this.current = null; // { uri, title, path }
    this.ready = this.kernel.start();
    this.kernel.on('state', (s) => ctx.emit('player/state', s));
    this.kernel.on('position', (t, d) => ctx.emit('player/position', t, d));
    this.kernel.on('end', () => ctx.emit('player/end'));
    // stop VLC when the host shuts down
    ctx.on('dispose', () => { this.kernel.stopProcess().catch(() => {}); });
  }

  dispose() {
    this.kernel.stopProcess().catch(() => {});
  }

  async load(media) {
    this.current = media;
    await this.kernel.load(media.uri);
    this.ctx.emit('player/current', media);
    return media;
  }

  play() { this.kernel.play(); }
  pause() { this.kernel.pause(); }
  stop() { this.kernel.stop(); }
  seekMs(ms) { this.kernel.seekMs(ms); }
  seekFraction(f) { this.kernel.seekFraction(f); }
  setVolume(v) { this.kernel.setVolume(v); }
  setMute(m) { this.kernel.setMute(m); }
  getState() { return this.kernel.getState(); }

  /** Convenience: build a media descriptor from a local path. */
  static mediaFromPath(path, title) {
    const uri = toVlcUri(path);
    return { uri, path, title: title || path.split(/[\\/]/).pop() };
  }
}

export default PlayerService;
