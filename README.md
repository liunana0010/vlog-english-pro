# Vlog English Pro

基于 YouTube Vlog 的沉浸式英语口语练习 Web 应用。观看真实视频、同步字幕跟读、AI 发音评分、生词本与学习记录，一站式提升口语能力。

![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178c6)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688)

## 功能亮点

- **YouTube 视频搜索与内嵌播放** — 支持 Vlog、TED、美妆、音乐等分类
- **多源字幕同步** — 自动高亮当前句，点击跳转，键盘快捷键
- **AI 跟读评分** — Azure 语音评估，逐词标注发音问题
- **交互词典** — 点击单词查释义，一键加入生词本
- **学习大厅** — 练习历史、最高得分、生词统计

## 快速开始

### 前置条件

- Node.js 18+
- Python 3.10+
- [YouTube Data API Key](https://console.cloud.google.com/)
- [Azure Speech Key](https://azure.microsoft.com/products/ai-services/speech-to-text)（发音评分，可选）

### 本地运行

```bash
# 克隆
git clone https://github.com/nanaliu/vlog-english-pro.git
cd vlog-english-pro

# 前端
cp .env.example .env
# 编辑 .env 填入 VITE_YOUTUBE_API_KEY
npm install
npm run dev

# 后端（新终端）
cd backend
pip install -r requirements.txt
$env:SPEECH_KEY="your-azure-key"   # PowerShell
python main.py
```

访问 http://localhost:5173

## 文档

- [产品需求文档（PRD）](docs/PRD.md)
- [项目技术文档](docs/PROJECT.md)

## 部署

| 组件 | 平台 | 说明 |
|------|------|------|
| 前端 | [Netlify](https://www.netlify.com) | 静态站点，配置 `VITE_*` 环境变量 |
| 后端 | [Render](https://render.com) | 使用 `render.yaml` 一键部署 FastAPI |

Netlify 环境变量：
- `VITE_YOUTUBE_API_KEY`
- `VITE_API_BASE_URL`（Render 后端 URL）

## 技术栈

**前端：** Vue 3 · TypeScript · Vite · Element Plus · YouTube IFrame API

**后端：** FastAPI · youtube-transcript-api · yt-dlp · Azure Speech SDK

## 许可证

仅供学习交流使用。
