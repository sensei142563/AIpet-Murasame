# 版权与来源核对记录

核对日期：2026-10-10（北京时间）。本文是公开源码和声明的核对记录，不是发布包或全部素材的授权证明。

## 范围与基准

- 对方仓库：[sensei142563/AIpet-Murasame](https://github.com/sensei142563/AIpet-Murasame)。
- 当前核对快照：[`a4a5f8e0191e7094a72192af0be2f9495027b228`](https://github.com/sensei142563/AIpet-Murasame/commit/a4a5f8e0191e7094a72192af0be2f9495027b228)，提交时间为 2026-10-10 13:14:51 +08:00。
- 直接上游历史基准：[kuxiaowo/AIpet-Murasame 的 `a23e7177be87f90a928943eefeb9c8ac0365f20a`](https://github.com/kuxiaowo/AIpet-Murasame/commit/a23e7177be87f90a928943eefeb9c8ac0365f20a)，2025-11-22。
- 历史复制证据快照：[`06e0869637079ef25aa0cb2e759b6140824009c5`](https://github.com/sensei142563/AIpet-Murasame/commit/06e0869637079ef25aa0cb2e759b6140824009c5)。
- 原来源修正：[`3d6968df211ecc70b35981676ab758bfd6b418c3`](https://github.com/sensei142563/AIpet-Murasame/commit/3d6968df211ecc70b35981676ab758bfd6b418c3) 和 [issue #4](https://github.com/sensei142563/AIpet-Murasame/issues/4)。

方法：清点整个 Git 树及提交记录；比较同路径 blob 与跨路径同 blob；检索公开文本中的
来源/版权/许可信息；读取 Python AST 做模块清点并抽查主要实现；读取六个字体的内嵌
版权/许可/版本并计算 SHA-256；核对构建收集路径。未执行整个应用或生成绿色版/安装包。
二进制角色资源仅做清单核对，不据此认定其完整授权链。

初次清点基于 `51c3d666…`，提交前复查的新快照 `a4a5f8e0…` 仅在
`pcl_launcher/colors.py` 增加 15 行 `secondary_text` 颜色辅助；已纳入核对，
未改变下列文件/路径统计或许可文件。

## 目录与差异统计

以下数字都针对上述**核对前快照**，不包含本次新增的声明和许可文件。

| 项目 | 数量 |
|---|---:|
| 全部追踪文件 | 645 |
| Python 文件 | 149 |
| 已取回检索的文本/配置文件（含 LICENSE、.gitignore） | 305 |
| 与历史上游同路径且相同 blob 的全部文件 | 6 |
| 与历史上游同路径但不同 blob 的全部文件 | 14 |
| 本仓库存在而历史基准没有的路径 | 625 |
| 历史基准存在而本仓库没有的路径 | 161 |
| 同路径且未变的 Python 文件 | 3（其中两个是空 `__init__.py`） |
| 同路径但已修改的 Python 文件 | 12 |
| 历史基准没有的 Python 路径 | 134 |

“新增路径”不等于原创代码：它可能是移动后的资源、外部组件、历史版本之外的继承代码
或协作者贡献；不同 blob 也不等于整个文件已经重写。这里只用统计支持范围说明。

主要目录文件数：`pets/` 383、`tool/` 77、`pcl_launcher/` 40、`plugins/` 19、
`qq/` 18、`docs/` 15、`更新日志/` 15、`tests/` 10、`fonts/` 6、`longtext/` 6、
`场景素材/` 6、`classes/` 5、`wechat/` 4、`Live2d/` 2、`ui/` 2；根目录文件 37。
目录存在或文件数量不证明功能已经生效。功能差异及实现位置见 [COPYRIGHT.md](../COPYRIGHT.md)。

## 代码来源结果

| 文件 | 上游历史 blob | 历史快照 blob | 当前核对快照 blob |
|---|---|---|---|
| `download.py` | `197f5bb03d723840f934594ff3b7c3b70be84f28` | 同上 | `9db9cf6176fc8a8ce214c1b1b3027b4660f9ff16` |
| `tool/stt.py` | `4672d886c5768a0484c7a1872042493bce3d4eb4` | 同上 | `016a4285c17955dd136454b97d64c42250c1cf21` |
| `tool/voice_trigger.py` | `6a149774617bfe761352ac8aee5cd40b22ea8924` | 本表不另作历史快照断言 | 同上 |

当前同路径已修改的十二个 Python 文件是 `api.py`、`classes/Worker_class.py`、
`classes/murasame_class.py`、`download.py`、`main.py`、`run.py`、`tool/chat.py`、
`tool/cloud_API_chat.py`、`tool/config.py`、`tool/generate.py`、`tool/stt.py`、`tool/time_utils.py`。

当前 `LICENSE` 与历史上游相同，blob 为 `0ad25db4bd1d86c452db3f9602ccdbe172438f52`。
它是 AGPL-3.0 的许可证正文，正文中的 Free Software Foundation 署名是许可证文本版权，
不能代替项目代码作者的署名。

## 修改时间与贡献者

Git 存在不同根提交和备份分支，旧源码历史没有作为当前 main 的完整祖先保留；
不能只看当前历史根提交就认定它是整个项目第一次修改。

旧首发说明对应 `4214f5db59807f99af1bef87d4b7b60a9cf2ecb3` 的作者时间为
2026-08-16 20:33:23 +08:00，提交者时间为 2026-08-22 00:28:37 +08:00；
历史证据快照 `06e08696…` 的时间为 2026-08-12 20:06:44 +08:00。
这些是 Git 元数据，不是对真实首发日期或私人修改起点的独立证明。
旧声明中的“修改开始日期 2026-08-10”未在本次公开记录中得到充分核实，
因此新声明改为明确具体快照与本次整理日期，不再把推测的起始日作为确认事实。

核对基准的可达提交作者标识统计为：`developer` 149 次、`dsh-sync` 14 次、
`sensei142563` 5 次、`zcode` 1 次。它们是 author 字段的清点，不是贡献量、真实身份
或版权归属的结论。旧历史还包含协作者整合记录，应保留具体贡献的原署名。

`chatter` 安卓端及文档里的未来记忆架构属于关联项目或规划。当前 Git 树没有
`.kt`/`.java` Android 实现，因此新版权声明不将这些功能写成本仓库已公开代码。

## 字体与分发结果

六个字体均核对了 `name` 表的版权、版本及许可：五个 `fonts/` 字体为 OFL 1.1，
根目录旧版 Source Han Sans CN Bold 1.000 为 Apache-2.0。
已补回字体许可文本和内嵌版权记录，见 [字体声明](../third_party/fonts/NOTICE.md)。
未修改字体二进制或 AGPL 正文。

`build_launcher.py` 正常路径以 `git ls-files` 收集追踪文件，但没有 Git 的手工清单
此前不包含 COPYRIGHT.md；本次补入 COPYRIGHT.md、THIRD_PARTY_NOTICES.md 和
`third_party/`，使来源声明及字体许可也可进入绿色版。安装包脚本随后收集绿色版目录。
本次只核对文件收集规则，没有实际构建或核验已有发布包。

## 尚需维护者提供的依据

1. `Live2d/Live2DCubismCore.dll` 的版本、来源及对应再分发许可；当前树只有二进制，没有独立许可文本。
2. 三个角色包的立绘、Live2D 模型、语音/训练权重、表情图片和场景素材的具体来源及使用/再分发授权。
3. `tool/nltk_data/taggers/averaged_perceptron_tagger/averaged_perceptron_tagger.pickle` 的数据来源、版本与许可。
4. 实际绿色版/安装包中另行加入的 Python 依赖、GPT-SoVITS、F5-TTS、NapCat/QQ、模型权重等
   外部内容的版本与许可文本，以及这些发布包的对应源码提供方式。

这些缺口不会因更新 COPYRIGHT.md 而自动消失；本次采用明确的待核对说明，未替权利人
编造授权。详细路径与范围见 [第三方声明](../THIRD_PARTY_NOTICES.md)。

## 复核示例

在相应仓库和历史对象已可读取的情况下，可用以下命令复核：

```bash
git ls-tree -r a4a5f8e0191e7094a72192af0be2f9495027b228
git ls-tree 06e0869637079ef25aa0cb2e759b6140824009c5 download.py
git ls-tree 06e0869637079ef25aa0cb2e759b6140824009c5:tool stt.py
git shortlog -sn a4a5f8e0191e7094a72192af0be2f9495027b228
# 以下在 kuxiaowo/AIpet-Murasame 的历史对象中运行：
git ls-tree a23e7177be87f90a928943eefeb9c8ac0365f20a download.py
git ls-tree a23e7177be87f90a928943eefeb9c8ac0365f20a:tool stt.py
```

字体 SHA-256 直接对文件字节计算，元数据可用 fontTools 的 `TTFont(...)["name"]` 读取。
统计时应固定上述快照；本次 PR 新增文件后，直接对新分支计数会得到不同结果。
