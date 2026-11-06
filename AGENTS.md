# make-oral-video 项目现状

> 票据：facd72c1a1640fd34c2a1d2964393a01（飞书 originate，om_x100b61e7155bfcb8b05cfd7762321dc）
> 更新：2026-11-06 收尾复盘后。下个会话读此文件即可接手，无需重新摸底。

## 当前结论（已验证）

- 成片已交付：`out/superagent-vertical.mp4`（1080×1920@30fps、58.17s、H.264+AAC、13.5MB），竖屏无人脸、中文配音+字幕，抽帧质检通过。
- 源码工程 `video-project/` 已提交 PR #3（分支 agent/make-oral-video-facd72c1a164），**未合并，留人工**。
- 收尾复盘在 `work/项目复盘.md`；新坑已录全局错误录 E82。

## 硬约束（改工程前必读）

1. **Remotion 版本锁定 4.0.448**：≥4.0.449（及 4.0.448 的捆绑工具链）用 macOS 15 SDK 编译，本机 macOS 13.7 加载即 dyld 崩（症状：渲染 EPIPE / ffprobe SIGABRT，详见 `~/.dsh/LESSONS.md` E82）。**只用 Remotion 出帧序列，音轨/封装一律系统 ffmpeg**。
2. 系统链路：`npm run tts → timing → audio → frames → video`（详见 `script.md`）；改文案只动 `video-project/scripts/scenes.json`。
3. 输出目录两个：`out/`（票据根，最终 mp4，gitignore）与 `video-project/out/`（音轨中间产物，gitignore）——不要混用。
4. edge-tts 需 ≥7.3.1（旧版 403）；路径写死在 `scripts/generate-tts.mjs`。
5. 渲染日志写文件、退出码直读，不用管道 tail。

## 未决事项

- AI 文生视频（GLM/CogVideoX）未接入，需另立票据。
- PR #3 等人工合并；memory/dtodo 工具本会话未挂载，记忆合并清理未执行。
