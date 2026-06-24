# Vlog English Pro — 部署指南

本文档说明如何将项目部署到 GitHub 与 Netlify（前端）+ Render（后端）。

---

## 一、推送到 GitHub

### 1. 登录 GitHub CLI（首次）

```powershell
gh auth login
# 选择: GitHub.com → HTTPS → Login with a web browser
```

### 2. 创建仓库并推送

```powershell
cd c:\Users\nanaliu\my-apps\vlog-english

# 创建公开仓库（仓库名可自定义）
gh repo create vlog-english-pro --public --source=. --remote=origin --push

# 若仓库已存在，仅推送：
git branch -M main
git remote add origin https://github.com/<你的用户名>/vlog-english-pro.git
git push -u origin main
```

---

## 二、部署后端（Render）

> 字幕获取与发音评分需要 Python 后端，Netlify 无法运行 FastAPI。

1. 打开 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New → Blueprint**
3. 连接 GitHub 仓库 `vlog-english-pro`
4. Render 自动读取 `render.yaml` 创建 Web Service
5. 在 **Environment** 中添加：
   - `SPEECH_KEY` = 你的 Azure Speech Key
   - `SPEECH_REGION` = `eastus`
6. 部署完成后复制服务 URL，例如：`https://vlog-english-api.onrender.com`

---

## 三、部署前端（Netlify）

### 方式 A：Git 自动部署（推荐）

1. 打开 [Netlify](https://app.netlify.com) → **Add new site → Import an existing project**
2. 选择 GitHub → 仓库 `vlog-english-pro`
3. 构建设置（`netlify.toml` 已配置，通常自动识别）：
   - Build command: `npm run build`
   - Publish directory: `dist`
4. 在 **Site configuration → Environment variables** 添加：

   | 变量名 | 值 |
   |--------|-----|
   | `VITE_YOUTUBE_API_KEY` | 你的 YouTube Data API Key |
   | `VITE_API_BASE_URL` | Render 后端 URL（如 `https://vlog-english-api.onrender.com`） |

5. 点击 **Deploy site**

### 方式 B：Netlify CLI 手动部署

```powershell
# 安装 CLI
npm install -g netlify-cli

# 登录
netlify login

# 构建（Windows 若 npm run build 失败，使用下方命令）
node .\node_modules\vite\bin\vite.js build

# 首次部署（创建新站点）
netlify deploy --prod --dir=dist
```

部署后在 Netlify Dashboard 设置环境变量，然后 **Trigger deploy** 重新构建。

### 方式 C：拖拽部署（最快预览）

1. 本地构建：`node .\node_modules\vite\bin\vite.js build`
2. 打开 [Netlify Drop](https://app.netlify.com/drop)
3. 将 `dist` 文件夹拖入

> 拖拽方式不含环境变量，YouTube 搜索与后端 API 需在 Git 部署中配置。

---

## 四、部署后验证

| 检查项 | 预期结果 |
|--------|----------|
| 访问 Netlify URL | 页面正常加载，深色主题 |
| 选择测试视频 | YouTube 播放器就绪 |
| 字幕加载 | 显示字幕条数（需后端在线） |
| 跟读录音 | 返回评分（需 Azure Key） |
| 后端健康检查 | 访问 `https://<后端URL>/` 返回 JSON status ok |

---

## 五、环境变量汇总

### 前端（Netlify）

```
VITE_YOUTUBE_API_KEY=xxx
VITE_API_BASE_URL=https://vlog-english-api.onrender.com
```

### 后端（Render）

```
SPEECH_KEY=xxx
SPEECH_REGION=eastus
```

---

## 六、常见问题

**Q: Netlify 构建失败 `vue-tsc` 报错？**  
A: Netlify 使用 Linux 环境，一般正常。若失败，将 `package.json` 的 build 改为 `"build": "vite build"`。

**Q: 线上字幕/评分不可用？**  
A: 确认 `VITE_API_BASE_URL` 指向 Render 后端，且后端已部署成功。

**Q: Render 免费版冷启动慢？**  
A: 免费实例 15 分钟无请求会休眠，首次访问需等待约 30 秒唤醒。

**Q: API Key 安全？**  
A: 密钥通过环境变量注入，不要提交 `.env` 到 Git。YouTube Key 建议限制 HTTP Referrer。
