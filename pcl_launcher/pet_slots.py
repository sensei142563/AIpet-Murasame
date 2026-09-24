# -*- coding: utf-8 -*-
"""「当前使用」三个槽位（桌宠 / QQ / 微信）+ 可拖拽的角色胶囊。

用户 2026-09-24 的界面要求（带草图）：
    当前使用：
        桌宠：（灰色虚线圆角框 + 加号） QQAIPet聊天：（同） 微信chatbot聊天：（同）
    我的桌宠：（全部角色，头像 + 名字的胶囊）
        胶囊可拖动 → 拖进虚线框就填充上去（虚线框自动隐藏）；
        从框里拖出去 / 拖到空白处 → 该槽自动清空（胶囊消失）；
        从「我的桌宠」拖出去的胶囊**不会**从列表里消失（这里是"调色板"，不是搬运）。
    全部桌宠：（详细卡片，保持原样）

落盘/生效由 `pets.pet_registry` 的槽位 API 负责：
  · 桌宠槽 → 老键 active_pet；桌宠正在跑 → 交给总览页 schedule_pet_switch（0.5 秒防误触）
  · QQ / 微信槽 → qq_active_pet / wechat_active_pet；桥接每次聊天都会重新读，无需重启
"""
import os

from PyQt5.QtCore import Qt, QMimeData, QPoint, pyqtSignal
from PyQt5.QtGui import QDrag, QFont, QPixmap
from PyQt5.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
                             QWidget)

from .colors import Color1, Color3, Color5, Gray2, Gray3, GreenDark
from .silicon_ui import M
from .widgets import S                     # 统一的缩放系数（widgets 是常量来源）

PET_MIME = "application/x-aipet-pet"

# "没显式指定"时槽位上追加的说明（每个槽说法不同：桌宠槽没有"跟随"一说）
_DEFAULT_NOTE = {
    "pet": "　（当前是默认角色，还没单独指定）",
    "qq": "　（未单独指定，跟随桌宠）",
    "wechat": "　（未单独指定，跟随桌宠）",
}


def _avatar_path(pet_id: str, avatar: str) -> str:
    try:
        from pets.pet_registry import PETS_DIR
        if avatar:
            p = os.path.join(PETS_DIR, pet_id, avatar)
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return ""


# ══════════════ 胶囊：头像 + 名字，可拖 ══════════════
class PetCapsule(QFrame):
    """角色胶囊。拖出去时 mime 里带上 pet_id 和来源槽（空 = 来自「我的桌宠」列表）。"""

    def __init__(self, pet_id: str, name: str, avatar: str = "", source_slot: str = "",
                 on_drag_done=None, parent=None):
        super().__init__(parent)
        self.pet_id = pet_id
        self.pet_name = name or pet_id
        self.source_slot = source_slot or ""
        self._on_drag_done = on_drag_done
        self._press = None
        self._dragging = False

        self.setObjectName("petCapsule")
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet(f"""
            QFrame#petCapsule {{
                background: rgba({Color3.red()},{Color3.green()},{Color3.blue()},60);
                border: 1px solid {Color5.name()};
                border-radius: {int(14*S)}px;
            }}
            QFrame#petCapsule:hover {{
                background: rgba({Color3.red()},{Color3.green()},{Color3.blue()},110);
            }}
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(int(8*S), int(5*S), int(12*S), int(5*S))
        row.setSpacing(int(7*S))

        av_path = _avatar_path(pet_id, avatar)
        if av_path:
            av = QLabel()
            av.setFixedSize(int(26*S), int(26*S))
            av.setScaledContents(True)
            av.setStyleSheet("border: none; background: transparent;")
            av.setPixmap(QPixmap(av_path).scaled(int(26*S), int(26*S),
                                                 Qt.KeepAspectRatio, Qt.SmoothTransformation))
            row.addWidget(av)
        lb = QLabel(self.pet_name)
        lb.setStyleSheet(f"color: {Color1.name()}; border: none;"
                         f" font-size: {int(12*S)}px; font-family: '{M.font}';")
        row.addWidget(lb)
        self.setToolTip(f"{self.pet_name}（{pet_id}）\n拖动我 → 放进上面的「当前使用」槽位")

    # ── 拖拽 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is None or self._dragging:
            return
        if (event.pos() - self._press).manhattanLength() < 12:
            return
        self._dragging = True
        drag = QDrag(self)
        mime = QMimeData()
        # 文本里放 "pet_id|来源槽"（槽为空 = 从「我的桌宠」拖的）
        mime.setText("%s|%s" % (self.pet_id, self.source_slot))
        mime.setData(PET_MIME, ("%s|%s" % (self.pet_id, self.source_slot)).encode("utf-8"))
        drag.setMimeData(mime)
        pm = self.grab()
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        self.setCursor(Qt.ClosedHandCursor)
        # ⚠ 拖拽期间槽位那边会 refresh()，本控件可能已经被 deleteLater ——
        #   所以先把回调与来源存成局部变量，回来时绝不碰 self 的 Qt 对象。
        cb, src = self._on_drag_done, self.source_slot
        try:
            drag.exec_(Qt.CopyAction)
        finally:
            try:
                self.setCursor(Qt.OpenHandCursor)
            except Exception:
                pass
            self._press = None
            self._dragging = False
            if cb:
                try:
                    cb(src)
                except Exception as e:
                    print(f"[PCL] ⚠ 拖拽收尾失败: {e}")


# ══════════════ 槽位：虚线框 + 加号 / 填充态 ══════════════
class PetSlot(QFrame):
    """一个「当前使用」槽位。空着时是灰色虚线圆角框 + 加号；有角色时显示胶囊。"""

    changed = pyqtSignal(str, str)          # (slot, pet_id 或 "")

    def __init__(self, slot: str, title: str, hint: str = "", on_drag_done=None, parent=None):
        super().__init__(parent)
        self.slot = slot
        self._on_drag_done = on_drag_done
        self.setAcceptDrops(True)
        self.setMinimumHeight(int(64 * S))

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(int(4 * S))
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {Color1.name()}; border: none;"
                                     f" font-size: {int(12*S)}px; font-weight: bold;")
        v.addWidget(self.title_lbl)
        self.hint_lbl = QLabel(hint)
        self.hint_lbl.setStyleSheet(f"color: {Gray2.name()}; border: none;"
                                    f" font-size: {int(10*S)}px;")
        self.hint_lbl.setVisible(bool(hint))
        self._base_hint = hint or ""
        v.addWidget(self.hint_lbl)

        self.box = QFrame()                  # 虚线框本体（放加号 或 胶囊）
        self.box.setObjectName("petSlotBox")
        self.box.setMinimumHeight(int(44 * S))
        # 注意：**不要**给 box 开 acceptDrops —— 拖放统一由 PetSlot 处理，
        # 否则鼠标落在框本体上时事件被 box 吃掉，drop 就没反应了。
        self._box_layout = QHBoxLayout(self.box)
        self._box_layout.setContentsMargins(int(8*S), int(4*S), int(8*S), int(4*S))
        self._box_layout.setSpacing(int(6*S))
        v.addWidget(self.box)

        self._placeholder = QLabel("＋")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {Gray2.name()}; border: none; font-size: {int(20*S)}px;")
        self._box_layout.addWidget(self._placeholder)
        self._capsule = None
        self._empty_qss = f"""
            QFrame#petSlotBox {{
                background: rgba(255,255,255,0.05);
                border: 2px dashed {Gray2.name()};
                border-radius: {int(10*S)}px;
            }}
        """
        self._filled_qss = f"""
            QFrame#petSlotBox {{
                background: rgba({Color3.red()},{Color3.green()},{Color3.blue()},40);
                border: 1px solid {Color5.name()};
                border-radius: {int(10*S)}px;
            }}
        """
        self._apply_empty_style()

    def _apply_empty_style(self):
        self.box.setStyleSheet(self._empty_qss)
        self._placeholder.setVisible(True)

    def set_pet(self, pet_id: str, name: str, avatar: str = "", is_default: bool = False):
        """填上角色（is_default=True 表示"没显式指定，跟着桌宠槽"→ 角上标一下）"""
        if self._capsule is not None:
            self._box_layout.removeWidget(self._capsule)
            self._capsule.deleteLater()
            self._capsule = None
        self._placeholder.setVisible(False)
        self.box.setStyleSheet(self._filled_qss)
        cap = PetCapsule(pet_id, name, avatar, source_slot=self.slot,
                         on_drag_done=self._on_drag_done)
        self._box_layout.addWidget(cap)
        self._capsule = cap
        # 提示行保留"这个槽是干嘛的"，只在"没显式指定"时追加一句说明
        note = _DEFAULT_NOTE.get(self.slot, "") if is_default else ""
        self.hint_lbl.setText(self._base_hint + note)
        self.hint_lbl.setVisible(bool(self.hint_lbl.text()))

    def clear_slot_view(self, hint: str = ""):
        if self._capsule is not None:
            self._box_layout.removeWidget(self._capsule)
            self._capsule.deleteLater()
            self._capsule = None
        self._apply_empty_style()
        self.hint_lbl.setText(hint or self._base_hint)
        self.hint_lbl.setVisible(bool(self.hint_lbl.text()))

    # ── 接收拖放（框本体与外围都收，手感宽容一点）──
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(PET_MIME):
            event.acceptProposedAction()
            self.box.setStyleSheet(f"""
                QFrame#petSlotBox {{
                    background: rgba({GreenDark.red()},{GreenDark.green()},{GreenDark.blue()},70);
                    border: 2px dashed {GreenDark.name()};
                    border-radius: {int(10*S)}px;
                }}
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.box.setStyleSheet(self._filled_qss if self._capsule is not None else self._empty_qss)

    def dropEvent(self, event):
        md = event.mimeData()
        if not md.hasFormat(PET_MIME):
            event.ignore()
            return
        raw = bytes(md.data(PET_MIME)).decode("utf-8", "replace")
        pet_id, _src = (raw.split("|", 1) + [""])[:2]
        # 由上层写配置并刷新（这里只负责把结果报上去）
        self.changed.emit(self.slot, pet_id)
        event.acceptProposedAction()


# ══════════════ 「当前使用」整块 ══════════════
class CurrentUsePanel(QWidget):
    """三个槽位 + 「我的桌宠」胶囊列表。拖进槽 = 指定；拖出槽 = 取消指定。"""

    def __init__(self, on_pet_switch=None, on_toast=None, on_refresh_all=None, parent=None):
        super().__init__(parent)
        self._on_pet_switch = on_pet_switch        # fn(display_name) → 桌宠立即换（可选）
        self._on_toast = on_toast                  # fn(text)（可选）
        self._on_refresh_all = on_refresh_all      # fn() 让外面的「全部桌宠」也刷新（可选）
        self._drop_handled = False

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, int(10 * S))
        v.setSpacing(int(8 * S))

        head = QLabel("当前使用")
        head.setStyleSheet(f"color: {Color1.name()}; font-size: {int(15*S)}px;"
                           f" font-weight: bold; font-family: '{M.font}';")
        v.addWidget(head)

        slots_row = QHBoxLayout()
        slots_row.setSpacing(int(14 * S))
        self.slots = {}
        for slot, title, hint in (("pet", "桌宠", "拖一个角色进来 = 立刻换成它"),
                                  ("qq", "QQAIPet聊天", "空 = 跟桌宠一样"),
                                  ("wechat", "微信chatbot聊天", "空 = 跟桌宠一样")):
            sl = PetSlot(slot, title, hint, on_drag_done=self._on_drag_finished)
            sl.changed.connect(self._on_slot_changed)
            self.slots[slot] = sl
            slots_row.addWidget(sl, 1)
        v.addLayout(slots_row)

        mine = QLabel("我的桌宠")
        mine.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px;"
                           f" font-weight: bold; font-family: '{M.font}';")
        v.addWidget(mine)
        self.capsule_host = QWidget()
        self.capsule_grid = QGridLayout(self.capsule_host)
        self.capsule_grid.setContentsMargins(0, 0, 0, 0)
        self.capsule_grid.setSpacing(int(8 * S))
        v.addWidget(self.capsule_host)

        self.refresh()

    # ── 数据 ──
    def _summaries(self):
        try:
            from pets.pet_registry import get_all_pets_summary
            return get_all_pets_summary() or []
        except Exception as e:
            print(f"[PCL] ⚠ 读取角色列表失败: {e}")
            return []

    def refresh(self):
        """按 config 里的槽位现状重画三个槽 + 胶囊列表

        用户 2026-09-24 定的规则：
          · 桌宠槽：**总是显示当前生效的角色**（没显式指定过就是默认角色，通常「丛雨」）
            —— 桌宠永远得有一个形象，所以这个槽不给虚线空态
          · QQ / 微信槽：显示的是**你显式指定的**角色；没指定就是灰色虚线框 + 加号，
            提示里写清"空着时跟桌宠一样（<角色名>）"
        """
        from pets.pet_registry import get_slot_map, get_pet_config, get_slot_pet_id
        smap = get_slot_map()
        for slot, info in smap.items():
            sl = self.slots.get(slot)
            if sl is None:
                continue
            eff = info.get("effective") or ""
            cfg = get_pet_config(eff) or {} if eff else {}
            eff_name = (cfg.get("display_name") or cfg.get("name") or eff) if eff else "（没有角色）"
            if slot == "pet":
                # 桌宠槽永远填着实效角色（虚线空态只在"一个角色都没有"时出现）
                if eff:
                    sl.set_pet(eff, eff_name, cfg.get("avatar") or "", not info.get("raw"))
                else:
                    sl.clear_slot_view("还没有任何桌宠角色")
            elif info.get("raw"):
                sl.set_pet(eff, eff_name, cfg.get("avatar") or "", False)
            else:
                sl.clear_slot_view("空 = 跟桌宠一样（%s）" % eff_name)

        # 「我的桌宠」胶囊（清空重画）
        while self.capsule_grid.count():
            item = self.capsule_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, p in enumerate(self._summaries()):
            cap = PetCapsule(p["id"], p.get("display_name") or p.get("name") or p["id"],
                             p.get("avatar") or "", source_slot="")
            self.capsule_grid.addWidget(cap, i // 4, i % 4)
        self.capsule_grid.setColumnStretch(4, 1)

    # ── 拖放结果 ──
    def _on_drag_finished(self, source_slot):
        """一次拖拽结束：从槽里拖出去且没落到任何槽 → 取消该槽的指定"""
        if not source_slot:
            return                                  # 从「我的桌宠」拖的：原地不动，什么都不做
        if self._drop_handled:
            self._drop_handled = False
            return
        self._clear(source_slot)

    def _on_slot_changed(self, slot, pet_id):
        self._drop_handled = True
        self._assign(slot, pet_id)

    def _assign(self, slot, pet_id):
        from pets.pet_registry import set_slot_pet_id, get_pet_config, SLOT_LABELS
        if not set_slot_pet_id(slot, pet_id):
            self._toast("换角色失败：角色不存在或 config.json 不可写")
            return
        cfg = get_pet_config(pet_id) or {}
        name = cfg.get("display_name") or cfg.get("name") or pet_id
        label = SLOT_LABELS.get(slot, slot)
        if slot == "pet":
            self._toast(f"桌宠已换成「{name}」")
            if self._on_pet_switch:
                try:
                    self._on_pet_switch(name)       # 正在跑 → 0.5 秒防误触后自动换
                except Exception as e:
                    print(f"[PCL] ⚠ 通知换桌宠失败: {e}")
        else:
            self._toast(f"{label} 已换成「{name}」（聊天桥接下一次回复就生效）")
        print(f"[PCL] 槽位 {slot} → {pet_id}")
        self.refresh()
        if self._on_refresh_all:
            try:
                self._on_refresh_all()
            except Exception:
                pass

    def _clear(self, slot):
        from pets.pet_registry import clear_slot_pet_id, SLOT_LABELS, get_slot_pet_id, get_pet_config
        clear_slot_pet_id(slot)
        label = SLOT_LABELS.get(slot, slot)
        if slot == "pet":
            # 桌宠槽清空 = 回到默认角色（仍然填着，不会变成虚线空框）
            eff = get_slot_pet_id("pet")
            cfg = get_pet_config(eff) or {}
            name = cfg.get("display_name") or cfg.get("name") or eff
            self._toast("桌宠槽已清空 —— 回到默认角色「%s」" % name)
        else:
            self._toast(f"{label} 已取消指定 —— 跟随桌宠")
        print(f"[PCL] 槽位 {slot} 已清空")
        self.refresh()
        if self._on_refresh_all:
            try:
                self._on_refresh_all()
            except Exception:
                pass

    def _toast(self, text):
        if self._on_toast:
            try:
                self._on_toast(text)
            except Exception:
                pass
        else:
            print("[PCL] %s" % text)
