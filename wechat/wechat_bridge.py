# -*- coding: utf-8 -*-
"""
微信 ClawBot 桥：长轮询收消息 → 待处理收件箱（防丢）→ QQ 同款消息调度器 → 回复。

与 QQ 桥的关键差异（官方协议约束，一手源码核对）：
- 只支持私聊；没有历史消息 API
- 反刷限制（34 秒 18 条触发限流）→ 长回复必须合并成一条发送
- context_token 必须原样回传；client_id 每次唯一（客户端已处理）
- 连发多条消息 → 与 QQ 一样由 MessageScheduler 合并为一次回复

防丢设计（Android PendingInbox 移植，at-least-once）：
- 收包循环顺序：get_updates → 逐条落 pending 收件箱 → 再推游标 → 再分发处理
  （处理中进程崩溃 → 游标未超前于 pending，重启后补处理收件箱，消息不丢）
- 回复「发送成功」才从收件箱删除；启动进入轮询前先补处理残留收件箱
- 识图不阻塞收包线程：收包线程只解析入队，图片下载+识图延后到调度线程
"""
import os
import uuid
import time

from tool.paths import data_path

from wechat.ilink_client import (
    ILinkClient, ILinkError,
    load_credentials, load_sync_buf, save_sync_buf,
    save_ctx_token, parse_text_from_items,
    ITEM_IMAGE,
)
from wechat import pending_inbox


class WeChatBridge:
    def __init__(self, owner_id="", bot_agent="AIpet/1.15", send_voice=False):
        creds = load_credentials()
        if not creds:
            raise RuntimeError("未登录：请先运行 run_wechat.py 完成扫码登录")
        self.client = ILinkClient(creds.get("baseurl"), creds.get("token"), bot_agent)
        self.bot_user_id = creds.get("user_id", "")
        self.bot_id = creds.get("bot_id", "")
        self.owner_id = (owner_id or "").strip()
        self.send_voice = bool(send_voice)
        self.running = True

        # 复用 QQ 的消息调度器：全局串行 + 同一会话合并
        from qq.qq_scheduler import MessageScheduler
        self.scheduler = MessageScheduler(handler=self._handle_queued)

    # ===== 主循环（长轮询）=====
    def start(self):
        self.client.notify_start()
        whitelist = f"开: {self.owner_id}" if self.owner_id else "关（回复所有人）"
        print(f"[WeChatBot] 🔑 凭据已加载（bot={self.bot_id}，user={self.bot_user_id}），验证连接中…")

        # 补处理上次未完成的收件箱（at-least-once：宁可重复不可丢）
        self._replay_pending()

        poll_fail = 0
        announced = False  # 「已连接」只在首次轮询真实成功后才打印（防凭据已失效还误报在线）
        while self.running:
            try:
                buf = load_sync_buf()
                resp = self.client.get_updates(buf, timeout=45)
                new_buf = resp.get("get_updates_buf") or buf
                # 1. 逐条先落收件箱（处理前崩溃不丢）
                accepted = []
                persist_failed = False
                for msg in resp.get("msgs") or []:
                    if not self._should_accept(msg):
                        continue
                    pid = pending_inbox.add(msg)
                    if pid is None:
                        # 落盘失败 → 不推游标，让服务端下轮重发（假 at-least-once 是最隐蔽的丢消息）
                        persist_failed = True
                        print("[WeChatBot] ⛔ pending 落盘失败，本轮不推游标（下轮重拉重试）")
                        break
                    accepted.append((pid, msg))
                if persist_failed:
                    if not self._sleep(2):
                        break
                    continue
                # 2. 全部落盘成功后才推游标
                save_sync_buf(new_buf)
                # 3. 分发处理（下载/识图/回复都在调度线程，不阻塞收包）
                for pid, msg in accepted:
                    self._enqueue_message(msg, pid)
                poll_fail = 0
                if not announced:
                    print(f"[WeChatBot] ✅ 已连接（bot={self.bot_id}，白名单{whitelist}）")
                    announced = True
            except ILinkError as e:
                if e.ret == -14:
                    print("[WeChatBot] ⚠ bot_token 过期（errcode=-14），尝试免扫续期...")
                    if self._try_token_reuse():
                        print("[WeChatBot] ✅ 免扫续期成功，继续轮询")
                        poll_fail = 0
                        continue
                    print("[WeChatBot] ⛔ 免扫续期失败，需要重新扫码登录："
                          "在 PCL 点击「重新登录微信」，或删除 data/wechat_credentials.json 后重跑 run_wechat.py。"
                          "（保留自动重试，约 1 小时后再次尝试）")
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

    def _replay_pending(self):
        """启动时补处理收件箱残留消息（上次处理中崩溃/未回复完成的）"""
        items = pending_inbox.all_items()
        if not items:
            return
        print(f"[WeChatBot] ↻ 发现 {len(items)} 条待处理消息，补处理中...")
        for pid, msg in items:
            if not self._should_accept(msg):
                pending_inbox.remove(pid)
                continue
            self._enqueue_message(msg, pid)
        print("[WeChatBot] ↻ 待处理消息补处理完成")

    def _try_token_reuse(self) -> bool:
        """-14 后带旧 token 免扫续期：成功则换新凭据重建客户端"""
        try:
            from wechat.ilink_client import try_token_reuse, save_credentials
            creds = load_credentials()
            if not creds:
                return False
            renewed = try_token_reuse(creds)
            if not renewed:
                return False
            save_credentials(renewed)
            # 重建客户端（baseurl/token 都可能更新）
            self.client = ILinkClient(renewed.get("baseurl"), renewed.get("token"),
                                      self.client.bot_agent)
            self.bot_id = renewed.get("bot_id", self.bot_id)
            self.bot_user_id = renewed.get("user_id", self.bot_user_id)
            return True
        except Exception as e:
            print(f"[WeChatBot] ⚠ 免扫续期异常: {e}")
            return False

    def _sleep(self, secs):
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

    # ===== 入队前的快速过滤（纯逻辑，无 IO）=====
    def _should_accept(self, msg) -> bool:
        """是否应处理该消息：类型 + 白名单（收件箱落盘与入队共用）"""
        if not isinstance(msg, dict):
            return False
        if msg.get("message_type") not in (1, None):
            return False  # 机器人自己的回显（2）等跳过
        from_user = msg.get("from_user_id") or ""
        if self.owner_id and from_user != self.owner_id:
            print(f"[WeChatBot] 🚫 非白名单用户 {from_user}，已忽略")
            return False
        items = msg.get("item_list") or []
        text = parse_text_from_items(items)
        has_image = self._find_image_media(items) is not None
        if not text and not has_image:
            return False  # 无内容消息（空消息/纯未知类型）不处理
        return True

    # ===== 入队（收包线程：只解析 + 落 ctx + 入队，绝不阻塞下载/识图）=====
    def _enqueue_message(self, msg, pid=""):
        from_user = msg.get("from_user_id") or ""
        items = msg.get("item_list") or []
        text = parse_text_from_items(items)
        ctx = msg.get("context_token") or ""
        if ctx:
            save_ctx_token(from_user, ctx)
        print(f"[WeChatBot] 💬 {from_user}: {(text or '[图片]')[:40]}")

        self.scheduler.enqueue({
            "session_key": f"wechat_{from_user}",
            "text": text,
            "user_id": from_user,
            "nickname": "",
            "group_id": None,
            "context_token": ctx,
            # 图片 media 引用不在此下载——由调度线程 _handle_queued 下载+识图，
            # 避免收包线程被数秒~十几秒的视觉请求阻塞导致长轮询停摆。
            "image_media": self._find_image_media(items) if not text else None,
            "pending_id": pid,
        })

    # ===== 调度线程：处理合并后的消息（串行，天然不阻塞收包）=====
    def _handle_queued(self, m):
        from_user = m.get("user_id") or ""
        ctx = m.get("context_token") or ""
        session_key = m.get("session_key") or f"wechat_{from_user}"
        pids = self._collect_pending_ids(m)

        # 合并后的多条消息可能各带图片 → 下载+识图全部延后到这里（调度线程）
        vision_desc = None
        tmp_files = []
        # 图片下载/识图失败的子消息 pid（这类消息未真正处理完 → 即使组内文字回复成功
        # 也要保留该 pid，供重启补拉重试；整组无内容时才整组保留）
        failed_img_pids = set()
        try:
            merged = m.get("merged_msgs") or [m]
            descs = []
            for sub in merged:
                media = sub.get("image_media")
                if not media:
                    continue
                sub_pid = (sub or {}).get("pending_id", "")
                try:
                    raw = self.client.download_media(media, label="image")
                    tmp = os.path.join(data_path("tmp"), f"wechat_img_{uuid.uuid4().hex}.jpg")
                    os.makedirs(os.path.dirname(tmp), exist_ok=True)
                    with open(tmp, "wb") as f:
                        f.write(raw)
                    tmp_files.append(tmp)
                    from qq.qq_vision import describe_image
                    desc = describe_image(tmp)
                    if desc:
                        descs.append(desc)
                    else:
                        if sub_pid:
                            failed_img_pids.add(sub_pid)  # 识别无结果视为未完成
                except Exception as e:
                    if sub_pid:
                        failed_img_pids.add(sub_pid)
                    print(f"[WeChatBot] ⚠ 图片下载/识别失败: {e}")
            if descs:
                vision_desc = "\n".join(descs)
        finally:
            for tmp in tmp_files:
                try:
                    os.remove(tmp)
                except Exception:
                    pass

        text = (m.get("text") or "").strip()
        if not text and not vision_desc:
            if failed_img_pids:
                # 纯图片消息处理失败：保留对应 pid，重启后补拉重试（at-least-once，
                # 宁可重复不可丢；超 48h 的旧条目会被收件箱自动清理）
                print(f"[WeChatBot] ⚠ 图片消息处理失败，{len(failed_img_pids)} 条保留待处理（重启自动补拉）")
            else:
                self._drop_pending(pids)
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
        send_failed = False
        if reply:
            # 合并为单条发送（官方反刷限制：34 秒 18 条触发限流）
            try:
                self.client.send_text(from_user, reply, context_token=ctx)
                print(f"[WeChatBot] → 已回复 {from_user}（{len(reply)} 字）")
            except ILinkError as e:
                send_failed = True
                print(f"[WeChatBot] ⚠ 发送失败: {e}")
            except Exception as e:
                send_failed = True
                print(f"[WeChatBot] ⚠ 发送异常: {e}")

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

        # at-least-once 收尾语义：
        # - 发送失败（异常）→ 保留 pending，重启后自动补发（宁可重复不可丢）
        # - 发送成功 → 处理完成，删除；但组内「图片下载/识图失败」的子消息 pid 保留
        #   （图片内容从未成功处理，重启后单独补拉重试——整组删除会丢掉它）
        if send_failed:
            if pids:
                print(f"[WeChatBot] ⚠ 回复未送达，{len(pids)} 条消息保留在待处理队列（重启自动补发）")
        else:
            drop_pids = [p for p in pids if p not in failed_img_pids]
            if drop_pids:
                self._drop_pending(drop_pids)
            if failed_img_pids:
                print(f"[WeChatBot] ⚠ {len(failed_img_pids)} 条图片消息处理失败保留待处理（重启自动补拉）")

    @staticmethod
    def _collect_pending_ids(m):
        """合并后的消息可能含多条子消息（每条带各自 pending_id）"""
        pids = []
        merged = m.get("merged_msgs") or [m]
        for sub in merged:
            pid = (sub or {}).get("pending_id", "")
            if pid and pid not in pids:
                pids.append(pid)
        return pids

    @staticmethod
    def _drop_pending(pids):
        for pid in pids:
            pending_inbox.remove(pid)

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
