/** 应用配置 — 从 Vite 环境变量读取 */
export const YOUTUBE_API_KEY = import.meta.env.VITE_YOUTUBE_API_KEY ?? ''
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001'
