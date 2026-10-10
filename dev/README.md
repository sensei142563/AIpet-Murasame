# dev/ —— 开发与验收辅助区

这里放的是**开发过程中用到的脚本与文档**（从临时实验区搬回主仓库，主战场就是本仓库）。

## 文档
- `docs/汇报素材-两天工作总结.md` —— 两天工作汇报素材
- `docs/功能清点-功能与实现与状态.md` —— 功能清点（功能 + 实现 + 状态）

## 一键脚本（Windows）
- `一键启动-本地Jev与语音.bat` —— 依次启动 NanoJev(8765) / F5-TTS(9881) / api.py(28565)，
  并建立手机到电脑的 USB 反向转发。**手机端设置填 `http://127.0.0.1:28565` 与 `http://127.0.0.1:9881`。**
- `手机连电脑-一键重连.bat` —— 只重建 USB 转发（拔线/重启手机后用）。

## 脚本（python，adb 驱动的真机验收）
- `phone_camera_component.py` —— 给手机加「拍摄」能力（权限 → 系统相机 → 照片进会话）并装机
- `fix_voice_riff2.py` —— 修 VoiceClient 里写反的 RIFF 判断（朗读优先走电脑 F5-TTS）
- `phone_send_pet.py` —— 手机朗读按角色选音色（请求带 pet）
- `f5_pet_param3.py` —— 电脑端 F5 服务加 pet 参数（按角色解析权威范例）+ 两角色音频对比
- `emotion_to_motion.py` / `motion_wire2.py` —— 情绪 → Live2D 动作（合成命中区触摸）
- `ar_live2d_restore2.py` —— AR 的 Live2D 透明叠加（补回被回滚冲掉的改动）
- `chat_framing_fix.py` / `ar_calibrate*.py` —— 聊天页与 AR 的取景调整与标定
- `usb_reverse_link.py` —— USB 反向端口转发（绕开校园网客户端隔离）
- `e2e_jev_phone2.py` / `verify_voice_chain.py` / `jev_status_check.py` —— 端到端验收与状态核查
- `commit_*.py` —— 提交辅助（中文提交信息用文件传入，避免引号/编码问题）

## 注意
校园网做了客户端隔离（手机与电脑互相 ping 不通），因此手机访问电脑一律走 **USB 反向转发**。
`adb reverse` 在拔线或重启手机后失效，重跑 `手机连电脑-一键重连.bat` 即可。
