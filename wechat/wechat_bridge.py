# -*- coding: utf-8 -*-
"""
微信 ClawBot 桥：长轮询收消息 → QQ 同款消息调度器（会话合并）→ chat_once → 单条回复。

与 QQ 桥的关键差异（官方协议约束，一手源码核对）：
- 只支持私聊；没有历史消息 API
- 反刷限制（34 秒 18 条触发限流）→ 长回复必须合并成一条发送
- context_token 必须原样回传；client_id 每次唯一（客户端已处理）
- 连发多条消息 → 与 QQ 一样由 MessageScheduler 合并为一次回复（1.5~5 秒窗口）
"""
import os
import uuid

from tool.paths import data_path

from wechat.ilink_client import (
    ILinkClient, ILinkError,
    load_credentials, load_sync_buf, save_sync_buf,
    save_ctx_token, parse_text_from_items,
    ITEM_IMAGE,
)


class WeChatBridge:
    def __init__(self, owner_id="", bot_agent="AIpet/1.12", send_voice=False):
        creds = load_credentials()
        if not creds:
            raise RuntimeError("未登录：请先运行 run_wechat.py 完成扫码登录")
        self.client = ILinkClient(creds.get("baseurl"), creds.get("token"), bot_agent)
        self.bot_user_id = creds.get("user_id", "")
        self.owner_id = (owner_id or "").strip()
        self.send_voice = bool(send_voice)
        self.running = True

        # 复用 QQ 的消息调度器：全局串行 + 同一会话 1.5~5 秒合并
        from qq.qq_scheduler import MessageScheduler
        self.scheduler = MessageScheduler(handler=self._handle_queued)

    # ===== 主循环（长轮询）=====
    def start(self):
        self.client.notify_start()
        whitelist = f"开: {self.owner_id}" if self.owner_id else "关（回复所有人）"
        print(f"[WeChatBot] ✅ 已连接（bot={self.bot_user_id}，白名单{whitelist}）")
        poll_fail = 0
        while self.running:
            try:
                buf = load_sync_buf()
                resp = self.client.get_updates(buf, timeout=45)
                new_buf = resp.get("get_updates_buf") or buf
                save_sync_buf(new_buf)
                for msg in resp.get("msgs") or []:
                    self._enqueue_message(msg)
                poll_fail = 0
            except ILinkError as e:
                if e.ret == -14:
                    print("[WeChatBot] ⚠ bot_token 过期（errcode=-14）。"
                          "删除 data/wechat_credentials.json 后重跑 run_wechat.py 重新扫码，"
                          "或等待自动重试（约 1 小时）。")
                    if not self._sleep(3600):
                        break
                else:
                    poll_fail += 1
                    print(f"[WeChatBot] ⚠ 轮询错误: {e}")
                    if not self._sleep(min(30, 5 * poll_fail)):
                        break
            except Exception as e:
                poll_fail += 1
                print(f"[WeChatBot] ⚠ 网络异常: {e}")
                if not self._sleep(min(30, 5 * poll_fail)):
                    break
        self.client.notify_stop()
        print("[WeChatBot] 连接已关闭")

    def _sleep(self, secs):
        import time
        t0 = time.time()
        while self.running and time.time() - t0 < secs:
            time.sleep(0.5)
        return self.running

    def stop(self):
        self.running = False
        try:
            self.scheduler.stop()
        except Exception:
            pass

    # ===== 入队（解析在收包线程，回复在调度线程）=====
    def _enqueue_message(self, msg):
        # 只处理用户消息（message_type=1）；机器人自己的回显（2）跳过
        if msg.get("message_type") not in (1, None):
            return
        from_user = msg.get("from_user_id") or ""
        items = msg.get("item_list") or []
        text = parse_text_from_items(items)

        # 图片消息 → 下载解密 → 识图（复用 QQ 的 qwen3-vl 视觉）
        vision_desc = None
        if not text:
            image_media = self._find_image_media(items)
            if image_media:
                try:
                    raw = self.client.download_media(image_media, label="image")
                    tmp = os.path.join(data_path("tmp"), f"wechat_img_{uuid.uuid4().hex}.jpg")
                    os.makedirs(os.path.dirname(tmp), exist_ok=True)
                    with open(tmp, "wb") as f:
                        f.write(raw)
                    from qq.qq_vision import describe_image
                    vision_desc = describe_image(tmp)
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[WeChatBot] ⚠ 图片下载/识别失败: {e}")

        if not text and not vision_desc:
            return
        if self.owner_id and from_user != self.owner_id:
            print(f"[WeChatBot] 🚫 非白名单用户 {from_user}，已忽略")
            return
        ctx = msg.get("context_token") or ""
        if ctx:
            save_ctx_token(from_user, ctx)
        print(f"[WeChatBot] 💬 {from_user}: {(text or '[图片]')[:40]}")

        self.scheduler.enqueue({
            "session_key": f"wechat_{from_user}",
            "text": text,
            "vision_desc": vision_desc,
            "user_id": from_user,
            "nickname": "",
            "group_id": None,
            "context_token": ctx,
        })

    # ===== 调度线程：处理合并后的消息 =====
    def _handle_queued(self, m):
        from_user = m.get("user_id") or ""
        text = (m.get("text") or "").strip()
        vision_desc = m.get("vision_desc")
        ctx = m.get("context_token") or ""
        session_key = m.get("session_key") or f"wechat_{from_user}"
        if not text and not vision_desc:
            return

        # 复用 QQ 的对话封装（活动角色人设 + 分仓记忆 + 表情包选择）
        try:
            from qq.qq_chat import chat_once
            reply, stickers = chat_once(
                text, use_sticker=True, vision_desc=vision_desc,
                session_key=session_key,
            )
        except Exception as e:
            print(f"[WeChatBot] ⚠ 对话失败: {e}")
            reply, stickers = "（呜……刚刚走神了，请再说一次？）", []

        reply = (reply or "").strip()
        if reply:
            # 合并为单条发送（官方反刷限制：34 秒 18 条触发限流）
            try:
                self.client.send_text(from_user, reply, context_token=ctx)
                print(f"[WeChatBot] → 已回复 {from_user}（{len(reply)} 字）")
            except ILinkError as e:
                print(f"[WeChatBot] ⚠ 发送失败: {e}")

        # 表情包回图：AI 选了表情 → 从当前角色 biaoqingbao 找文件 → CDN 上传 → 发图片
        # （限 1 张 + 仅文字对话场景，防反刷）
        if stickers and text:
            try:
                from pets.pet_registry import get_sticker_dir
                sdir = get_sticker_dir()
                path = None
                for ext in (".gif", ".png", ".jpg", ".jpeg"):
                    p = os.path.join(sdir, f"{stickers[0]}{ext}")
                    if os.path.exists(p):
                        path = p
                        break
                if path:
                    uploaded = self.client.upload_image(path, from_user)
                    self.client.send_image(from_user, uploaded, context_token=ctx)
                    print(f"[WeChatBot] → 已回复表情: {stickers[0]}")
            except Exception as e:
                print(f"[WeChatBot] ⚠ 表情发送失败: {e}")

        # 语音回复（F5-TTS 合成 → silk → CDN → voice_item；官方插件未实现发语音，实验性）
        if reply and self.send_voice:
            self._send_voice_reply(reply, from_user, ctx)

    @staticmethod
    def _find_image_media(items):
        """从 item_list 提取第一张图片的 media 字段（CDN 引用 + aes_key）"""
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and item.get("type") == ITEM_IMAGE:
                img = item.get("image_item") or {}
                media = img.get("media")
                if isinstance(media, dict):
                    return media
        return None

    # ===== 语音回复（暂不支持）=====
    def _send_voice_reply(self, text, to_user_id, ctx):
        """微信 ClawBot 官方与社区插件均未实现「发送语音」（只有收语音），
        voice_item 字段无参考实现、实测微信端不渲染 → 明确跳过，避免误导。"""
        print("[WeChatBot] ⚠ 微信 ClawBot 通道暂不支持发送语音（官方/社区插件均未实现该能力），已跳过。"
              "可在 config.json 关闭 wechat_send_voice。")
