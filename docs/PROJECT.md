# Vlog English Pro — 项目文档

| 项目 | 内容 |
|------|------|
| 项目名称 | Vlog English Pro |
| 版本 | v1.0.0 |
| 文档日期 | 2026-06-25 |

---

## 1. 项目简介

Vlog English Pro 是一个前后端分离的 Web 应用，帮助用户通过 YouTube Vlog 视频进行沉浸式英语口语练习。前端负责视频播放、字幕交互与录音；后端负责字幕抓取、缓存与 Azure 发音评估。

---

## 2. 技术栈

### 2.1 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | ^3.5 | UI 框架（Composition API + `<script setup>`） |
| TypeScript | ~5.9 | 类型安全 |
| Vite | ^7.3 | 构建工具 |
| Element Plus | ^2.13 | UI 组件库 |
| YouTube IFrame API | — | 视频播放 |
| Web Audio API | — | 麦克风录音 |
| localStorage | — | 本地数据持久化 |

### 2.2 后端

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 运行时 |
| FastAPI | REST API 框架 |
| uvicorn | ASGI 服务器 |
| youtube-transcript-api | YouTube 字幕获取（方法 1） |
| yt-dlp | YouTube 字幕获取（方法 2） |
| webvtt-py | VTT 字幕解析 |
| azure-cognitiveservices-speech | 发音评估 |

---

## 3. 项目结构

```
vlog-english/
├── docs/                      # 文档
│   ├── PRD.md                 # 产品需求文档
│   └── PROJECT.md             # 项目文档（本文件）
├── public/                    # 静态资源
│   └── logo.png
├── src/                       # 前端源码
│   ├── App.vue                # 主应用（布局、搜索、录音、持久化）
│   ├── components/
│   │   └── interactivePlayer.vue  # 播放器、字幕、词典、跟读
│   ├── config.ts              # 环境变量配置
│   ├── main.ts                # 入口
│   └── style.css              # 全局样式
├── backend/                   # 后端源码
│   ├── main.py                # FastAPI 主程序
│   ├── requirements.txt       # Python 依赖
│   └── subtitle_cache/        # 字幕缓存（git 忽略）
├── index.html
├── vite.config.ts
├── netlify.toml               # Netlify 部署配置
├── render.yaml                # Render 后端部署配置
├── .env.example               # 前端环境变量示例
└── package.json
```

---

## 4. 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                      浏览器（前端）                       │
│  ┌──────────┐  ┌─────────────────┐  ┌──────────────┐   │
│  │ App.vue  │  │ InteractivePlayer│  │ localStorage │   │
│  │ 搜索/导航 │  │ 播放器/字幕/词典  │  │ 生词/历史    │   │
│  └────┬─────┘  └────────┬────────┘  └──────────────┘   │
│       │                 │                                │
│       │    YouTube IFrame API / Data API                 │
└───────┼─────────────────┼────────────────────────────────┘
        │                 │
        ▼                 ▼
┌───────────────┐  ┌──────────────────┐
│ YouTube API   │  │ FastAPI 后端      │
│ (搜索/播放)    │  │ localhost:8001   │
└───────────────┘  │                  │
                   │ /transcript      │──► youtube-transcript-api
                   │ /assess          │──► Azure Speech
                   │ subtitle_cache   │
                   └──────────────────┘
```

---

## 5. 核心模块说明

### 5.1 App.vue — 应用主控制器

- **页面路由**：通过 `activeTab` 切换「练习室」与「学习大厅」（无 Vue Router，轻量 tab 切换）
- **YouTube 搜索**：调用 YouTube Data API v3
- **播放器管理**：初始化 YT.Player，100ms 轮询同步字幕
- **录音流程**：getUserMedia → ScriptProcessor → WAV 编码 → POST `/assess`
- **持久化**：`studyHistory`、`vocabulary` 存入 localStorage

### 5.2 interactivePlayer.vue — 交互播放器

- **Props**：`videoId`、`transcript`、`scoredWords`、`videoTitle`、`channelName`
- **Emits**：`line-change`、`word-click`、`seek`、`add-vocab`
- **字幕同步**：`syncCurrentTime(currentTime)` 由父组件调用
- **词典**：点击单词调用第三方 API 查词，Teleport 弹窗避免 overflow 裁剪
- **键盘快捷键**：Space 播放/暂停，Alt+←/→ 切换句子

### 5.3 backend/main.py — 后端服务

- **SubtitleFetcher**：多源字幕获取 + MD5 缓存
- **GET /transcript**：按 video_id 返回字幕 JSON
- **POST /assess**：接收 WAV 文件 + reference_text，返回 Azure 评分
- **缓存管理**：`/cache-list`、`/clear-cache`

---

## 6. 环境变量

### 6.1 前端（`.env` / Netlify 环境变量）

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `VITE_YOUTUBE_API_KEY` | 是 | YouTube Data API Key（搜索功能） |
| `VITE_API_BASE_URL` | 否 | 后端地址，默认 `http://localhost:8001` |

### 6.2 后端（环境变量 / Render Dashboard）

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `SPEECH_KEY` | 是（评分功能） | Azure Speech 订阅密钥 |
| `SPEECH_REGION` | 否 | Azure 区域，默认 `eastus` |
| `PORT` | 否 | 服务端口，默认 `8001` |

---

## 7. 本地开发

### 7.1 前置条件

- Node.js 18+
- Python 3.10+
- YouTube Data API Key
- Azure Speech Key（可选，无则评分不可用）

### 7.2 启动步骤

```bash
# 1. 克隆项目
git clone https://github.com/<your-username>/vlog-english-pro.git
cd vlog-english-pro

# 2. 前端
cp .env.example .env
# 编辑 .env 填入 VITE_YOUTUBE_API_KEY
npm install
npm run dev          # http://localhost:5173

# 3. 后端（新终端）
cd backend
pip install -r requirements.txt
# Windows PowerShell:
$env:SPEECH_KEY="your-azure-speech-key"
python main.py       # http://localhost:8001
```

### 7.3 构建

```bash
npm run build        # 输出到 dist/
npm run preview      # 预览生产构建
```

---

## 8. 部署指南

### 8.1 前端 — Netlify

1. 将代码推送到 GitHub
2. 登录 [Netlify](https://app.netlify.com)，Import Git Repository
3. 构建设置（已在 `netlify.toml` 中配置）：
   - Build command: `npm run build`
   - Publish directory: `dist`
4. 在 Site settings → Environment variables 添加：
   - `VITE_YOUTUBE_API_KEY`
   - `VITE_API_BASE_URL`（指向已部署的后端 URL）
5. 重新 Deploy

### 8.2 后端 — Render（推荐）

1. 登录 [Render](https://render.com)，New → Blueprint
2. 连接 GitHub 仓库，Render 读取 `render.yaml` 自动部署
3. 在 Dashboard 设置环境变量 `SPEECH_KEY`、`SPEECH_REGION`
4. 部署完成后复制服务 URL，填入 Netlify 的 `VITE_API_BASE_URL`

> **注意**：Netlify 仅托管静态前端。字幕获取与发音评分依赖 Python 后端，需单独部署。

---

## 9. API 参考

### GET /transcript

```
GET /transcript?video_id=dQw4w9WgXcQ&use_cache=true
```

响应示例：

```json
{
  "status": "success",
  "source": "youtube-transcript-api",
  "transcript": [
    { "text": "We're no strangers to love", "start": 0.0, "duration": 3.5 }
  ],
  "count": 42
}
```

### POST /assess

```
POST /assess
Content-Type: multipart/form-data

file: recording.wav
reference_text: We're no strangers to love
```

响应示例：

```json
{
  "status": "success",
  "score": 85.2,
  "fluency": 78.5,
  "accuracy": 85.2,
  "words": [
    { "word": "we're", "accuracy": 90, "error_type": "None" }
  ]
}
```

---

## 10. 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 搜索无结果 | YouTube API Key 无效或配额用尽 | 检查 Key 与 Google Cloud 配额 |
| 获取字幕失败 | 后端未启动或 CORS | 确认后端运行；检查 `VITE_API_BASE_URL` |
| 视频无法播放 | 所有者禁止嵌入（错误 101/150） | 换其他视频 |
| 评分失败 | Azure Key 未配置 | 设置 `SPEECH_KEY` 环境变量 |
| 麦克风无法使用 | 浏览器未授权 | 点击地址栏锁图标允许麦克风 |

---

## 11. 许可证

本项目仅供学习交流使用。YouTube、Azure 等服务需遵守各自的使用条款。
