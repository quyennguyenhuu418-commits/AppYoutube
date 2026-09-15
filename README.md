# AI Documentary Animation Factory

一个 **输入主题、输出纪录片视频** 的 AI 生产系统。模仿现代 2D / 火柴人科普频道的内容语法（好奇心驱动的提问、口播解说、简洁角色、动态镜头、信息图动画），但视觉与文案完全原创。

> 用户在前端输入一个主题（例如 `How Did Ancient Humans Survive Deadly Winters?`），系统会自动完成：检索 → 论点 → 标题 → 脚本 → 分镜 → 角色与背景素材 → 口播音频 → 场景 JSON → 渲染成片 → 自动切短视频。

> **核心设计原则**：大语言模型（LLM）**绝不直接写视频代码**。LLM 只输出严格的 `SceneDefinition` JSON，真正的几何 / 动画由确定性渲染器（Remotion）执行。

---

## 系统组成

```
videoAI/
├── orchestrator/   # Python (FastAPI) 后端 + 流水线编排
├── renderer/       # Node (Remotion) 视频渲染器
├── webapp/         # Next.js 控制台前端
├── workspace/      # 每个任务的产物（自动生成，git 忽略）
└── README.md       # 你正在读的文件
```

---

## 0. 先决条件（Windows）

在开始之前，请先在你的电脑上安装以下三样工具。我无法在当前会话里帮你安装，所以请按顺序操作：

### 0.1 Python 3.11 或以上

1. 打开 https://www.python.org/downloads/windows/
2. 下载最新的 Python 3.11.x 或 3.12.x 安装包。
3. 运行安装包：**务必勾选** `Add Python to PATH`，然后点 `Install Now`。
4. 打开 PowerShell，输入：
   ```powershell
   python --version
   ```
   应该看到类似 `Python 3.11.9` 的输出。

### 0.2 Node.js 20 或以上

1. 打开 https://nodejs.org/en/download
2. 下载 `Windows Installer (.msi)` 的 LTS 版本（20.x 或更新）。
3. 运行安装包，一路下一步。
4. 打开 PowerShell，输入：
   ```powershell
   node --version
   npm --version
   ```
   应该看到 `v20.x.x` 和 `10.x.x`。

### 0.3 FFmpeg

1. 打开 https://www.gyan.dev/ffmpeg/builds/
2. 下载 `ffmpeg-release-essentials.zip`。
3. 解压到一个**不会变动的路径**，例如 `C:\ffmpeg\`。
4. 把 `C:\ffmpeg\bin` 加入系统环境变量 `Path`：
   - Win+R → 输入 `sysdm.cpl` → `高级` → `环境变量`
   - 在 `Path` 里新建一项，填入 `C:\ffmpeg\bin`
   - 确定 → 关闭所有窗口
5. **重新打开** PowerShell，输入：
   ```powershell
   ffmpeg -version
   ```
   应该看到版本信息。

> 完成以上三步后，整个系统就可以跑起来了。下面教你启动它。

---

## 1. 安装项目

打开 PowerShell，进入项目目录：

```powershell
cd c:\Users\Administrator\Downloads\videoAI
```

依次执行：

```powershell
# 1) Python 后端依赖
cd orchestrator
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 2) Node 渲染器依赖
cd renderer
npm install
cd ..

# 3) Next.js 前端依赖
cd webapp
npm install
cd ..
```

> 安装比较慢很正常，主要是 PyTorch 之类的包。请耐心等待。

---

## 2. 配置 API 密钥（可跳过）

回到项目根目录：

```powershell
cd c:\Users\Administrator\Downloads\videoAI
copy .env.example .env
```

用记事本打开 `.env`，填入：

- `OPENAI_API_KEY`：在 https://platform.openai.com/api-keys 申请。
- `ELEVENLABS_API_KEY`：在 https://elevenlabs.io 申请。
- `ELEVENLABS_VOICE_ID`：选一个你喜欢的男声或女声 ID。
- `OPENAI_IMAGE_MODEL`：默认 `dall-e-3`。

> **如果你暂时没有 API 密钥，也可以继续！** 系统会**自动启用 mock 模式**：所有 LLM 阶段返回固定的演示剧本，所有 TTS 阶段用 Google TTS 兜底，你依然可以跑通整个流水线并产出一个完整的演示视频。这让你在花钱之前就能验证系统。

---

## 3. 启动系统

回到根目录，双击或运行：

```powershell
.\start.bat
```

这个脚本会启动三个进程：

| 进程 | 地址 | 作用 |
|------|------|------|
| 后端 | http://localhost:8000 | 流水线编排 + REST API |
| 渲染器 | （按需调用） | 把场景 JSON 渲染成 MP4 |
| 前端 | http://localhost:3000 | 控制台 |

打开浏览器访问 **http://localhost:3000**。

---

## 4. 第一次生成

1. 在首页输入框写下一个主题，例如：
   > How Did Ancient Humans Survive Deadly Winters?
2. 点击 **生成视频** 按钮。
3. 系统会创建任务并跳转到详情页。你会看到 11 个阶段（研究、论点、标题、脚本、分镜、素材、口播、场景 JSON、校验、渲染、Shorts）依次跑过。
4. 第一次跑大约需要 2-5 分钟（取决于素材生成速度）。
5. 跑完后页面底部会出现视频播放器，点击播放。

---

## 5. 项目结构

```
videoAI/
├── orchestrator/                  # Python 后端
│   ├── app/
│   │   ├── main.py                # FastAPI 入口
│   │   ├── api/                   # REST 接口
│   │   ├── core/                  # 配置 / 日志 / 路径
│   │   ├── pipeline/              # 流水线编排 + 11 个阶段
│   │   ├── schemas/               # Pydantic 数据契约
│   │   ├── providers/             # OpenAI / ElevenLabs / DALL-E 封装
│   │   └── db/                    # 数据库模型
│   ├── tests/                     # 单元测试
│   └── requirements.txt
├── renderer/                      # Remotion 渲染器
│   ├── src/
│   │   ├── index.ts               # CLI 入口
│   │   ├── compositions/          # Remotion 主合成
│   │   ├── scenes/                # 确定性场景渲染器
│   │   └── components/            # 角色 / 镜头 / 字幕
│   └── package.json
├── webapp/                        # Next.js 控制台
│   ├── app/                       # 页面
│   └── components/                # UI 组件
├── workspace/                     # 每个任务的产物
└── README.md
```

---

## 6. 下一步（暂未实现）

为保持 MVP 简洁，以下功能标记为"下一阶段"，架构已为之预留接口：

- 用户登录 / 多账号
- Celery + Redis 异步队列（当前是同步执行）
- S3 / OSS 云存储（当前是本地文件系统）
- 智能 Shorts 选段（当前是简单地切中段）
- 缩略图自动生成
- 多家 LLM / TTS / 图像厂商（已抽象，但只接了 OpenAI / ElevenLabs）
- 自动发布到 YouTube
- 事实核查 + 来源可视化

如果你想优先实现其中某一项，告诉我，我会接着写。

---

## 7. 研究情报引擎 (Research Intelligence Engine)

研究阶段（Stage 1）现在使用 **研究情报引擎**。它将一个主题转换为一个结构化、可追溯、带不确定性建模的研究包，而不是简单的"搜索 + 摘要"。

### 7.1 13 步流水线

```
question_decomposition
        ↓
search_sources (DuckDuckGo 免费)
        ↓
fetch_and_score_sources
        ↓
deduplicate_sources
        ↓
extract_claims (LLM)
        ↓
build_claim_source_graph
        ↓
detect_contradictions (LLM)
        ↓
model_uncertainty
        ↓
build_timeline
        ↓
extract_visual_opportunities (LLM)
        ↓
extract_story_opportunities (LLM)
        ↓
synthesize (LLM)
        ↓
score_quality
```

### 7.2 研究包结构 (ResearchPackage)

每个研究都生成一个 `workspace/{job_id}/research_package.json`，包含：

| 章节 | 说明 |
|------|------|
| `metadata` | 主题、版本、耗时、质量分数 |
| `research_questions` | 10–15 个研究问题（按重要性评分） |
| `sources` | 每个来源带 TIER1-4 评级、独立性评分、内容哈希 |
| `claims` | 提取的事实性声明，附置信度、确定性等级 |
| `claim_source_links` | 声明 ↔ 来源 多对多关系（supports/contradicts/qualifies） |
| `contradictions` | 矛盾检测结果（未解决 / 部分解决 / 已解决） |
| `research_gaps` | 显式记录的证据空白 |
| `timeline` | 时间线事件（保留 BCE/CE 与近似性） |
| `geography` | 地理站点（含经纬度可选） |
| `quantitative_facts` | 定量事实（保留 min/max/approximate/uncertainty） |
| `visual_opportunities` | 视觉化机会（character_action / environment / artifact / map 等） |
| `story_opportunities` | 故事钩子、反直觉发现、情感节拍 |
| `synthesis` | 综合分析：已知、推断、未知 |
| `quality_score` | 9 维度质量评分 + 总体评分 |

### 7.3 来源等级

- **TIER1**：Nature / Science / PNAS / 同行评议论文 / 高校研究库 / 博物馆研究馆藏
- **TIER2**：Smithsonian / 主要博物馆 / 大学 / 知名科学刊物
- **TIER3**：参考书 / 百科 / Wikipedia / 教育资源
- **TIER4**：博客 / 商业站点 / 论坛（**仅用作发现线索，不作权威证据**）

### 7.4 确定性等级

每个 Claim 都有 `certainty_level` 字段：

- `STRONG_EVIDENCE`（2+ 高质量来源，confidence ≥ 0.85）
- `PLAUSIBLE_INTERPRETATION`（单一来源或一般置信度）
- `SPECULATION`（confidence 0.3–0.6）
- `UNKNOWN`（confidence < 0.3 或无来源）

### 7.5 研究包 API

```bash
# 获取完整研究包
GET /research/{job_id}/package

# 分页获取来源（可按 tier 过滤）
GET /research/{job_id}/sources?tier=TIER1&page=1

# 分页获取 Claim（可按 claim_type / certainty 过滤）
GET /research/{job_id}/claims?certainty=SPECULATION

# 获取矛盾列表
GET /research/{job_id}/contradictions

# 获取质量评分
GET /research/{job_id}/quality

# 人工审核：批准 / 拒绝来源
POST /research/{job_id}/review/sources/{source_id}
Body: {"approved": false, "notes": "..."}

# 人工审核：标记 Claim 为不确定
POST /research/{job_id}/review/claims/{claim_id}
Body: {"approved": false, "notes": "..."}
```

### 7.6 缓存与可重试性

研究是昂贵的。每个步骤都通过内容哈希缓存到 `workspace/{job_id}/research_cache/`：

- `search:{query_hash}` → 搜索结果
- `fetch:{url_hash}` → 抓取的网页内容
- `claims:{content_hash}` → 从来源提取的声明

7 天 TTL。失败重试不会重复已成功的工作。

### 7.7 旧版兼容

为保证下游阶段（thesis, script, storyboard）继续工作，`s1_research` 阶段同时写：

- `workspace/{job_id}/research_package.json` — 完整的丰富包（新）
- `workspace/{job_id}/research.json` — 旧版精简格式（向下兼容）

### 7.8 研究质量阈值

如果 `quality_score.overall_score < research_quality_min_threshold` (默认 0.6)，系统会发出 WARNING 但不会失败，以允许人工审核介入。可通过环境变量调整：

```
RESEARCH_QUALITY_MIN_THRESHOLD=0.7
```

---

## 7. 常见问题

**Q：报错 `ffmpeg not found`？**
A：你没把 FFmpeg 的 bin 目录加入 PATH，或者加入后没重启 PowerShell。

**Q：报错 `OPENAI_API_KEY not set`？**
A：正常 —— 系统会自动进入 mock 模式跑通演示。

**Q：渲染出来的视频没有声音？**
A：在 mock 模式下会用 Google TTS 兜底，可能没有时间戳对齐字幕。配置 ElevenLabs 后会正常。

**Q：可以商用吗？**
A：本项目代码是 MIT 协议，但生成的视频中包含的图片 / 音频仍受对应厂商条款约束，请自行检查。

---

## 8. 反馈

如果你在使用过程中遇到任何问题（安装失败、运行报错、效果不理想），把错误信息和你的操作步骤告诉我，我会持续迭代。

祝玩得开心。
