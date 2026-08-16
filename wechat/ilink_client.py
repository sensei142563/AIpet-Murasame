# -*- coding: utf-8 -*-
"""
微信 ClawBot iLink 协议客户端（Python）

协议来源：腾讯官方插件 @tencent-weixin/openclaw-weixin 2.4.6（MIT）
本文件为其 API 层的 Python 移植，仅实现桌面宠物需要的部分：
扫码登录 / 长轮询收消息 / 发送文字（媒体发送留待后续版本）。

关键事实（一手源码核对）：
- 固定域名：https://ilinkai.weixin.qq.com（登录扫码固定；确认后使用返回的 baseurl）
- iLink-App-Id: bot；iLink-App-ClientVersion = uint32(主.次.补) 编码的字符串
- get_bot_qrcode 是 POST，body 带 local_token_list（已有凭据可免扫直接复用）
- get_qrcode_status 是 GET 长轮询（约 35s），status: wait/scaned/need_verifycode/
  expired/verify_code_blocked/binded_redirect/scaned_but_redirect/confirmed
- confirmed 返回 bot_token / ilink_bot_id / ilink_user_id / baseurl
- 收消息：POST /ilink/bot/getupdates {get_updates_buf, base_info}；游标必须持久化
- 发消息：POST /ilink/bot/sendmessage {msg{...}, base_info}；context_token 原样回传、
  client_id 每次唯一；官方反刷实测：34 秒 18 条触发限流 → 长回复合并单条发送
- token 约 24h 过期（errcode -14）；凭据保存在 data/（gitignore 保护）
"""
import base64
import hashlib
import json
import os
import random
import uuid

import requests
from Crypto.Cipher import AES as _AES

from tool.paths import data_path

# ===== 协议常量（官方插件 2.4.6）=====
ILINK_APP_ID = "bot"
CHANNEL_VERSION = "2.4.6"
# uint32: major<<16 | minor<<8 | patch → 2.4.6 = 0x00020406 = 132102
ILINK_APP_CLIENT_VERSION = str((2 << 16) | (4 << 8) | 6)
FIXED_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_BOT_AGENT = "AIpet/1.12"

# 消息项类型（官方 types.js）
ITEM_TEXT = 1
ITEM_IMAGE = 2
ITEM_VOICE = 3
ITEM_FILE = 4
ITEM_VIDEO = 5

# ===== 持久化路径（data/ 已被 .gitignore 排除）=====
CRED_FILE = data_path("data", "wechat_credentials.json")
SYNC_BUF_FILE = data_path("data", "wechat_sync_buf.txt")
CTX_TOKENS_FILE = data_path("data", "wechat_context_tokens.json")

# ===== CDN（官方插件 accounts.js）=====
CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"


def _aes_ecb_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-128-ECB 加密（PKCS7 填充，官方 aes-ecb.js 同款）"""
    pad = 16 - (len(plaintext) % 16)
    data = plaintext + bytes([pad]) * pad
    return _AES.new(key, _AES.MODE_ECB).encrypt(data)


def _aes_ecb_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """AES-128-ECB 解密（PKCS7 填充）"""
    data = _AES.new(key, _AES.MODE_ECB).decrypt(ciphertext)
    return data[:-data[-1]]


def _parse_aes_key(aes_key_b64: str):
    """解析 CDN aes_key：base64(16 字节) 或 base64(32 字符 hex 字符串)（官方 pic-decrypt.js）"""
    raw = base64.b64decode(aes_key_b64)
    if len(raw) == 16:
        return raw
    if len(raw) == 32 and all(c in "0123456789abcdefABCDEF" for c in raw.decode("ascii")):
        return bytes.fromhex(raw.decode("ascii"))
    raise ValueError(f"aes_key 无法解析（{len(raw)} 字节）")


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_credentials():
    """返回 {token, bot_id, user_id, baseurl}；无凭据返回 None"""
    d = _load_json(CRED_FILE, None)
    if isinstance(d, dict) and d.get("token"):
        return d
    return None


def save_credentials(data):
    _save_json(CRED_FILE, data)


def clear_credentials():
    try:
        if os.path.exists(CRED_FILE):
            os.remove(CRED_FILE)
    except Exception:
        pass


def load_sync_buf():
    try:
        with open(SYNC_BUF_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def save_sync_buf(buf):
    try:
        os.makedirs(os.path.dirname(SYNC_BUF_FILE), exist_ok=True)
        with open(SYNC_BUF_FILE, "w", encoding="utf-8") as f:
            f.write(buf or "")
    except Exception:
        pass


def load_ctx_tokens():
    return _load_json(CTX_TOKENS_FILE, {})


def save_ctx_token(user_id, token):
    d = load_ctx_tokens()
    d[user_id] = token
    _save_json(CTX_TOKENS_FILE, d)


def get_ctx_token(user_id):
    return load_ctx_tokens().get(user_id, "")


def _base_info(bot_agent=DEFAULT_BOT_AGENT):
    return {"channel_version": CHANNEL_VERSION, "bot_agent": bot_agent}


def _common_headers():
    return {
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": ILINK_APP_CLIENT_VERSION,
    }


def _post_headers(token=""):
    """POST 请求头；登录类请求（fetch_qrcode）不带 Authorization"""
    h = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        # X-WECHAT-UIN: random uint32 → 十进制字符串 → base64（防重放）
        "X-WECHAT-UIN": base64.b64encode(str(random.getrandbits(32)).encode("utf-8")).decode("ascii"),
        **_common_headers(),
    }
    if token:
        h["Authorization"] = "Bearer " + token
    return h


class ILinkClient:
    """iLink 已登录客户端：长轮询 + 发消息"""

    def __init__(self, base_url, token, bot_agent=DEFAULT_BOT_AGENT):
        self.base_url = (base_url or FIXED_BASE_URL).rstrip("/")
        self.token = token or ""
        self.bot_agent = bot_agent

    def _post(self, endpoint, body, timeout=15):
        payload = dict(body)
        payload["base_info"] = _base_info(self.bot_agent)
        r = requests.post(
            f"{self.base_url}/{endpoint}",
            json=payload,
            headers=_post_headers(self.token),
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()

    # ===== 收消息（长轮询）=====
    def get_updates(self, buf="", timeout=45):
        """返回 {ret, msgs, get_updates_buf, ...}；ret!=0 时抛异常"""
        resp = self._post("ilink/bot/getupdates",
                          {"get_updates_buf": buf or ""},
                          timeout=timeout)
        if resp.get("ret", 0) not in (0, None):
            raise ILinkError(resp.get("ret"), resp.get("errmsg", "getupdates failed"))
        return resp

    # ===== 发消息 =====
    def send_text(self, to_user_id, text, context_token="", run_id=""):
        msg = {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": str(uuid.uuid4()),
            "message_type": 2,   # BOT
            "message_state": 2,  # FINISH
            "item_list": [{"type": ITEM_TEXT, "text_item": {"text": text}}],
        }
        if context_token:
            msg["context_token"] = context_token
        if run_id:
            msg["run_id"] = run_id
        resp = self._post("ilink/bot/sendmessage", {"msg": msg})
        if resp.get("ret", 0) not in (0, None):
            raise ILinkError(resp.get("ret"), resp.get("errmsg", "sendmessage failed"))
        return resp

    def notify_start(self):
        try:
            return self._post("ilink/bot/msg/notifystart", {})
        except Exception:
            return None

    def notify_stop(self):
        try:
            return self._post("ilink/bot/msg/notifystop", {})
        except Exception:
            return None

    # ===== 媒体（CDN + AES-128-ECB，官方 upload.js/pic-decrypt.js 移植）=====
    def _upload_media(self, file_path, to_user_id, media_type):
        """上传本地文件到微信 CDN → 返回发送 media item 需要的引用字段"""
        with open(file_path, "rb") as f:
            plaintext = f.read()
        rawsize = len(plaintext)
        rawfilemd5 = hashlib.md5(plaintext).hexdigest()
        filesize = ((rawsize + 16) // 16) * 16  # PKCS7 填充后的密文大小
        filekey = uuid.uuid4().hex
        aeskey = os.urandom(16)
        aeskey_hex = aeskey.hex()

        resp = self._post("ilink/bot/getuploadurl", {
            "filekey": filekey,
            "media_type": media_type,
            "to_user_id": to_user_id,
            "rawsize": rawsize,
            "rawfilemd5": rawfilemd5,
            "filesize": filesize,
            "no_need_thumb": True,
            "aeskey": aeskey_hex,
        })
        full_url = (resp.get("upload_full_url") or "").strip()
        upload_param = resp.get("upload_param") or ""
        if full_url:
            cdn_url = full_url
        elif upload_param:
            cdn_url = (f"{CDN_BASE_URL}/upload?encrypted_query_param="
                       f"{requests.utils.quote(upload_param)}&filekey={requests.utils.quote(filekey)}")
        else:
            raise ILinkError(-1, "getUploadUrl 未返回上传地址")

        ciphertext = _aes_ecb_encrypt(plaintext, aeskey)
        up = requests.post(cdn_url, data=ciphertext,
                           headers={"Content-Type": "application/octet-stream"}, timeout=60)
        up.raise_for_status()
        download_param = up.headers.get("x-encrypted-param")
        if not download_param:
            raise ILinkError(-1, "CDN 上传响应缺少 x-encrypted-param")
        return {
            "filekey": filekey,
            "download_param": download_param,
            "aes_key_b64": base64.b64encode(aeskey_hex.encode("ascii")).decode("ascii"),
            "mid_size": filesize,
            "raw_size": rawsize,
        }

    def upload_image(self, file_path, to_user_id):
        """上传图片（media_type=1 IMAGE）"""
        return self._upload_media(file_path, to_user_id, media_type=1)

    def upload_voice(self, file_path, to_user_id):
        """上传语音（media_type=4 VOICE，silk 格式）"""
        return self._upload_media(file_path, to_user_id, media_type=4)

    def send_image(self, to_user_id, uploaded, context_token=""):
        """发送已上传的图片（image_item）"""
        item = {
            "type": ITEM_IMAGE,
            "image_item": {
                "media": {
                    "encrypt_query_param": uploaded["download_param"],
                    "aes_key": uploaded["aes_key_b64"],
                    "encrypt_type": 1,
                },
                "mid_size": uploaded["mid_size"],
            },
        }
        return self._send_item(to_user_id, item, context_token)

    def send_voice(self, to_user_id, uploaded, duration_ms, context_token=""):
        """发送已上传的语音（voice_item；官方插件未实现发语音，字段为协议外推，
        服务端接受则微信端显示语音条）"""
        item = {
            "type": ITEM_VOICE,
            "voice_item": {
                "media": {
                    "encrypt_query_param": uploaded["download_param"],
                    "aes_key": uploaded["aes_key_b64"],
                    "encrypt_type": 1,
                },
                "voice_size": uploaded["mid_size"],
                "duration": int(duration_ms or 0),
            },
        }
        return self._send_item(to_user_id, item, context_token)

    def _send_item(self, to_user_id, item, context_token=""):
        msg = {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": str(uuid.uuid4()),
            "message_type": 2,
            "message_state": 2,
            "item_list": [item],
        }
        if context_token:
            msg["context_token"] = context_token
        resp = self._post("ilink/bot/sendmessage", {"msg": msg})
        if resp.get("ret", 0) not in (0, None):
            raise ILinkError(resp.get("ret"), resp.get("errmsg", "send media failed"))
        return resp

    def download_media(self, item_media, label="media"):
        """下载并解密 CDN 媒体（image/voice/file 共用）→ 明文 bytes"""
        encrypt_query_param = item_media.get("encrypt_query_param") or ""
        aes_key_b64 = item_media.get("aes_key") or ""
        full_url = item_media.get("full_url") or ""
        if full_url:
            url = full_url
        elif encrypt_query_param:
            url = (f"{CDN_BASE_URL}/download?encrypted_query_param="
                   f"{requests.utils.quote(encrypt_query_param)}")
        else:
            raise ILinkError(-1, f"{label}: 无下载地址")
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        if not aes_key_b64:
            return r.content  # 明文媒体
        key = _parse_aes_key(aes_key_b64)
        return _aes_ecb_decrypt(r.content, key)


class ILinkError(Exception):
    """iLink 协议错误（ret 非 0）"""

    def __init__(self, ret, errmsg):
        super().__init__(f"iLink errcode={ret}: {errmsg}")
        self.ret = ret
        self.errmsg = errmsg


# ===== 登录流程（未登录时用）=====

def fetch_qrcode(local_tokens=None):
    """POST /ilink/bot/get_bot_qrcode?bot_type=3 → {qrcode, qrcode_img_content(URL)}"""
    r = requests.post(
        f"{FIXED_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3",
        json={"local_token_list": list(local_tokens or [])},
        headers=_post_headers(""),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def poll_qrcode_status(qrcode, base_url=FIXED_BASE_URL, verify_code="", timeout=35):
    """GET /ilink/bot/get_qrcode_status?qrcode=xxx[&verify_code=yyy]（长轮询）→ {status, ...}"""
    url = f"{base_url}/ilink/bot/get_qrcode_status?qrcode={qrcode}"
    if verify_code:
        url += f"&verify_code={verify_code}"
    r = requests.get(url, headers=_common_headers(), timeout=timeout)
    return r.json()


def parse_text_from_items(item_list):
    """从消息 item_list 提取纯文本；语音带转文字时直接用 voice_item.text"""
    if not isinstance(item_list, list):
        return ""
    for item in item_list:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t == ITEM_TEXT:
            ti = item.get("text_item") or {}
            if ti.get("text") is not None:
                return str(ti["text"])
        elif t == ITEM_VOICE:
            vi = item.get("voice_item") or {}
            if vi.get("text"):
                return str(vi["text"])  # 官方：语音消息自带转文字
    return ""
