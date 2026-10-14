# 第三方组件与素材声明

整理日期：2026-10-10。核对基准、方法和未确认事项见 [版权核对记录](docs/COPYRIGHT_AUDIT.md)。
本文件不为第三方内容授予新权利，也不把第三方许可替换为本仓库的 AGPL-3.0。

## 字体：已核对文件内嵌声明

| 仓库文件 | 内嵌版本 | 许可 |
|---|---|---|
| `fonts/NotoSansCJKsc-Regular.otf` | Noto Sans CJK SC 2.004 | SIL OFL 1.1 |
| `fonts/NotoSansCJKjp-Regular.otf` | Noto Sans CJK JP 2.004 | SIL OFL 1.1 |
| `fonts/LXGWWenKaiLite-Regular.ttf` | LXGW WenKai Lite 1.522 | SIL OFL 1.1 |
| `fonts/ZCOOLXiaoWei-Regular.ttf` | ZCOOL XiaoWei 1.000 | SIL OFL 1.1 |
| `fonts/MaShanZheng-Regular.ttf` | Ma Shan Zheng 2.003 | SIL OFL 1.1 |
| `思源黑体Bold.otf` | Source Han Sans CN Bold 1.000 | Apache-2.0 |

版权字符串、文件 SHA-256、许可文本及取回来源见 [字体声明](third_party/fonts/NOTICE.md)。
根目录旧字体与 `fonts/` 中的新字体许可不同，不应统一描述为 OFL。

## Python 依赖与外部运行时

直接依赖见 [requirements.txt](requirements.txt)。包括 PyQt5、NumPy、OpenCV、Requests、
FastAPI、Uvicorn、PyTorch、Transformers、ModelScope、faster-whisper、ONNX Runtime、
InsightFace、live2d-py、PyOpenGL、pygame、pynput、sounddevice、soundfile 等；
完整依赖还应结合实际安装环境和各分发包内的元数据核对。

GPT-SoVITS、F5-TTS、NapCat/QQ、便携 Python、模型权重、CUDA/ROCm 运行时等可能由用户
另行安装，或在构建发布包时从本地目录加入。当前 Git 源码树没有覆盖这些目录的全部内容。
各组件和模型分别适用其自身条款；源码库的许可不能代替模型权重、训练数据或运行时的许可。

运行时分发必须保留各已安装版本的版权与许可文件；仅有依赖名称、API 调用或主页链接不足以
确认发布包已满足所有再分发义务。本次整理不为尚未核对的组件填写推测的 SPDX 标识。

## Live2D 原生组件

- 文件：`Live2d/Live2DCubismCore.dll`。
- 本仓库代码使用 `live2d-py`，但 Python 封装与 Cubism Core 是不同组件。
- 应取得该 DLL 的确切 SDK/版本、来源、对应版权文本及适用的再分发条件。
- 条款核对入口：[Live2D 官方许可与协议](https://www.live2d.com/eula/)。

当前公开树没有随附该 DLL 的独立许可文本。本声明不推定其属于 AGPL，也不确认其再分发授权。

## 角色、立绘、Live2D 模型与语音

| 路径或资源 | 已有来源信息 | 尚需核对的范围 |
|---|---|---|
| `pets/murasame/` | 丛雨，柚子社《千恋＊万花》；Live2D 制作来源链接见 README | 原作素材、模型制作及语音数据各自的使用/修改/再分发条件 |
| `pets/natsume/` | 配置与人设标识为四季夏目（ナツメ）；角色原作涉及柚子社 | 当前导入立绘的具体出处与授权依据，语音数据与衍生资源条件 |
| `pets/noir/` | README 将其称为诺瓦，指向《星空列车与白的旅行》/しらたまこ及 Live2D 视频来源 | 角色原作、模型制作者与实际文件的对应关系及各自许可 |
| 角色中文语音/参考音色 | README 提到《蔚蓝档案》爱理、枫香的 Wiki 来源；配置引用参考音频 | 实际发布音频/训练权重的来源与授权；Wiki 链接不等于再分发许可 |
| `场景素材/`、图标、表情图片与其他资源 | 场景目录说明仅称“示例素材”；部分来源见 README | 每项或同一来源资源组的作者、原始链接及授权条件 |

当前源码树含有模型/图片，但 `.gitignore` 会排除多数音频和模型权重；构建脚本仍可能从本地
加入这些文件。因此必须分别核对源码快照与实际绿色版/安装包。学习交流用途不自动解决授权问题。
若某素材确有非商业限制，该限制只作用于该素材及适用作品，不应表述成 AGPL 源代码全面禁止商用。

## 随附数据

文件：`tool/nltk_data/taggers/averaged_perceptron_tagger/averaged_perceptron_tagger.pickle`。
当前树未随附可对应到该数据文件的来源、版本或许可说明。NLTK 软件库的许可不能自动证明
标注器数据文件的许可；需补充实际数据来源与其再分发条件。

## 设计参考与独立项目

部分模块注释提及 Miru、OpenPets、AgentPet、Mitra、HealthMate、PyQt-SiliconUI 等设计参考。
这些注释应保留，但仅凭“参考”无法认定复制了哪段代码，也不能确认相应授权；若实际复制或
改编了代码，应按具体版本补充来源和许可证，而不是只列产品名。

README 和规划文档中的 `chatter`、只读参考项目或尚未实施的设计，均不自动纳入本仓库
AGPL 的授权范围。外部仓库与其 SDK/素材许可应单独核对。
