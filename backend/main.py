import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import azure.cognitiveservices.speech as speechsdk
import tempfile
import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict

# 设置标准输出编码为 UTF-8（解决 Windows GBK 编码问题）
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ==========================================
# 字幕获取相关库
# ==========================================
try:
    import youtube_transcript_api
    HAS_YOUTUBE_TRANSCRIPT = True
except ImportError:
    HAS_YOUTUBE_TRANSCRIPT = False
    print("⚠️ youtube-transcript-api 未安装")

try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False
    print("⚠️ yt-dlp 未安装")

try:
    import webvtt
    HAS_WEBVTT = True
except ImportError:
    HAS_WEBVTT = False
    print("⚠️ webvtt 未安装 (pip install webvtt-py)")

# ==========================================
# 配置
# ==========================================
SPEECH_KEY = os.environ.get("SPEECH_KEY", "")
SPEECH_REGION = os.environ.get("SPEECH_REGION", "eastus")

# 字幕缓存目录
CACHE_DIR = Path("./subtitle_cache")
CACHE_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 字幕获取核心逻辑
# ==========================================

class SubtitleFetcher:
    """多源字幕获取器"""
    
    @staticmethod
    def get_cache_path(video_id: str) -> Path:
        """获取缓存文件路径"""
        # 使用 hash 避免特殊字符问题
        safe_id = hashlib.md5(video_id.encode()).hexdigest()
        return CACHE_DIR / f"{video_id}_{safe_id}.json"
    
    @staticmethod
    def load_from_cache(video_id: str) -> Optional[List[Dict]]:
        """从缓存加载字幕"""
        cache_file = SubtitleFetcher.get_cache_path(video_id)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"✅ 从缓存加载字幕: {video_id}")
                    return data.get('transcript')
            except Exception as e:
                print(f"⚠️ 缓存读取失败: {e}")
        return None
    
    @staticmethod
    def save_to_cache(video_id: str, transcript: List[Dict]):
        """保存字幕到缓存"""
        cache_file = SubtitleFetcher.get_cache_path(video_id)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'video_id': video_id,
                    'transcript': transcript,
                    'cached_at': str(Path(cache_file).stat().st_mtime)
                }, f, ensure_ascii=False, indent=2)
            print(f"✅ 字幕已缓存: {video_id}")
        except Exception as e:
            print(f"⚠️ 缓存保存失败: {e}")
    
    @staticmethod
    def fetch_youtube_transcript_api(video_id: str) -> Optional[List[Dict]]:
        """方法1: 使用 youtube-transcript-api"""
        if not HAS_YOUTUBE_TRANSCRIPT:
            return None
        
        try:
            print(f"🔍 [方法1] 使用 youtube-transcript-api 获取字幕...")
            
            # 尝试多种语言
            languages = ['en', 'en-US', 'en-GB', 'a.en']  # a.en 是自动生成的英文字幕
            
            transcript_list = youtube_transcript_api.YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=languages
            )
            
            # 清理文本
            for item in transcript_list:
                item['text'] = item['text'].replace('\n', ' ').strip()
            
            print(f"✅ [方法1] 成功获取 {len(transcript_list)} 句字幕")
            return transcript_list
            
        except youtube_transcript_api.TranscriptsDisabled:
            print(f"⚠️ [方法1] 该视频禁用了字幕")
            return None
        except youtube_transcript_api.NoTranscriptFound:
            print(f"⚠️ [方法1] 未找到英文字幕")
            return None
        except Exception as e:
            print(f"⚠️ [方法1] 获取失败: {e}")
            return None
    
    @staticmethod
    def _parse_vtt_text(vtt_text: str) -> Optional[List[Dict]]:
        """解析 VTT 格式字幕为 transcript 列表"""
        try:
            # 尝试使用 webvtt 库解析
            if HAS_WEBVTT:
                import webvtt
                from io import StringIO
                vtt = webvtt.read_buffer(StringIO(vtt_text))
                transcript = []
                for caption in vtt:
                    text = caption.text.strip().replace('\n', ' ')
                    if not text:
                        continue
                    start_seconds = SubtitleFetcher._timestamp_to_seconds(caption.start)
                    end_seconds = SubtitleFetcher._timestamp_to_seconds(caption.end)
                    transcript.append({
                        'text': text,
                        'start': round(start_seconds, 2),
                        'duration': round(end_seconds - start_seconds, 2)
                    })
                if transcript:
                    print(f"✅ webvtt 解析成功: {len(transcript)} 条")
                    return transcript
        except Exception as e:
            print(f"⚠️ webvtt 解析失败: {e}")
        
        # 手动解析 VTT（备用方案）
        return SubtitleFetcher._parse_vtt_manual(vtt_text)
    
    @staticmethod
    def _parse_srt_text(srt_text: str) -> List[Dict]:
        """手动解析 SRT 格式字幕"""
        transcript = []
        blocks = srt_text.strip().split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            # SRT 时间格式: 00:00:01,000 --> 00:00:04,000
            time_line = lines[1]
            if '-->' not in time_line:
                continue
            parts = time_line.split('-->')
            if len(parts) != 2:
                continue
            start_sec = SubtitleFetcher._srt_time_to_seconds(parts[0].strip())
            end_sec = SubtitleFetcher._srt_time_to_seconds(parts[1].strip())
            text = ' '.join(lines[2:]).strip()
            # 去除 SRT 标签（如 <c>、</c> 等）
            import re
            text = re.sub(r'<[^>]+>', '', text).strip()
            if text and start_sec is not None and end_sec is not None:
                transcript.append({
                    'text': text,
                    'start': round(start_sec, 2),
                    'duration': round(end_sec - start_sec, 2)
                })
        return transcript
    
    @staticmethod
    def _srt_time_to_seconds(time_str: str) -> Optional[float]:
        """SRT 时间转秒数: 00:00:01,000"""
        try:
            import re
            match = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', time_str)
            if not match:
                return None
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, '0')[:3]) / 1000
        except Exception:
            return None
    
    @staticmethod
    def _timestamp_to_seconds(ts: str) -> float:
        """VTT 时间戳转秒数: 00:00:01.000 或 0:01.000"""
        try:
            parts = ts.replace(',', '.').split(':')
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            return float(ts)
        except Exception:
            return 0.0
    
    @staticmethod
    def _parse_vtt_manual(vtt_text: str) -> Optional[List[Dict]]:
        """手动解析 VTT 格式（不依赖 webvtt 库）"""
        try:
            import re
            transcript = []
            # 去掉 WEBVTT 头部
            content = re.sub(r'^WEBVTT.*?\n\n', '', vtt_text, flags=re.DOTALL)
            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) < 2:
                    continue
                # 找包含 --> 的时间行
                time_line_idx = -1
                for i, line in enumerate(lines):
                    if '-->' in line:
                        time_line_idx = i
                        break
                if time_line_idx == -1:
                    continue
                time_line = lines[time_line_idx]
                parts = time_line.split('-->')
                if len(parts) != 2:
                    continue
                start_sec = SubtitleFetcher._timestamp_to_seconds(parts[0].strip())
                end_sec = SubtitleFetcher._timestamp_to_seconds(parts[1].strip())
                text = ' '.join(lines[time_line_idx + 1:]).strip()
                # 去除 VTT 标签
                text = re.sub(r'<[^>]+>', '', text).strip()
                if text and start_sec >= 0 and end_sec > start_sec:
                    transcript.append({
                        'text': text,
                        'start': round(start_sec, 2),
                        'duration': round(end_sec - start_sec, 2)
                    })
            if transcript:
                print(f"✅ 手动 VTT 解析成功: {len(transcript)} 条")
                return transcript
        except Exception as e:
            print(f"⚠️ 手动 VTT 解析失败: {e}")
        return None
    
    @staticmethod
    def _download_subtitle_text(url: str) -> Optional[str]:
        """下载字幕文件文本"""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode('utf-8')
        except Exception as e:
            print(f"⚠️ 字幕下载失败: {e}")
            return None
    
    @staticmethod
    def fetch_yt_dlp(video_id: str) -> Optional[List[Dict]]:
        """方法2: 使用 yt-dlp 获取并解析字幕"""
        if not HAS_YT_DLP:
            return None
        
        try:
            print(f"🔍 [方法2] 使用 yt-dlp 获取字幕...")
            
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US'],
                'quiet': True,
                'no_warnings': True,
            }
            
            url = f'https://www.youtube.com/watch?v={video_id}'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # 优先级1: 手动上传的英文字幕
                if 'subtitles' in info:
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in info['subtitles']:
                            subs = info['subtitles'][lang]
                            for sub_info in subs:
                                if 'url' in sub_info:
                                    ext = sub_info.get('ext', 'vtt')
                                    subtitle_url = sub_info['url']
                                    print(f"✅ [方法2] 找到 {lang} 字幕 (格式: {ext})")
                                    subtitle_text = SubtitleFetcher._download_subtitle_text(subtitle_url)
                                    if subtitle_text:
                                        if ext in ('vtt', 'webvtt'):
                                            transcript = SubtitleFetcher._parse_vtt_text(subtitle_text)
                                        elif ext == 'srt':
                                            transcript = SubtitleFetcher._parse_srt_text(subtitle_text)
                                        else:
                                            # 尝试 VTT 解析
                                            transcript = SubtitleFetcher._parse_vtt_text(subtitle_text)
                                        if transcript:
                                            print(f"✅ [方法2] 成功解析 {len(transcript)} 条字幕")
                                            return transcript
                
                # 优先级2: 自动生成的字幕
                if 'automatic_captions' in info:
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in info['automatic_captions']:
                            subs = info['automatic_captions'][lang]
                            for sub_info in subs:
                                if 'url' in sub_info:
                                    ext = sub_info.get('ext', 'vtt')
                                    subtitle_url = sub_info['url']
                                    print(f"✅ [方法2] 找到 {lang} 自动字幕 (格式: {ext})")
                                    subtitle_text = SubtitleFetcher._download_subtitle_text(subtitle_url)
                                    if subtitle_text:
                                        if ext in ('vtt', 'webvtt'):
                                            transcript = SubtitleFetcher._parse_vtt_text(subtitle_text)
                                        elif ext == 'srt':
                                            transcript = SubtitleFetcher._parse_srt_text(subtitle_text)
                                        else:
                                            transcript = SubtitleFetcher._parse_vtt_text(subtitle_text)
                                        if transcript:
                                            print(f"✅ [方法2] 成功解析 {len(transcript)} 条自动字幕")
                                            return transcript
                
            print(f"⚠️ [方法2] 未找到可用字幕")
            return None
            
        except Exception as e:
            print(f"⚠️ [方法2] 获取失败: {e}")
            return None
    
    @staticmethod
    def get_fallback_transcript() -> List[Dict]:
        """备用字幕数据"""
        return [
            {
                "text": "Welcome to this video! This is a demo subtitle.",
                "start": 0.0,
                "duration": 4.0
            },
            {
                "text": "Unfortunately, real subtitles are not available for this video.",
                "start": 4.5,
                "duration": 5.0
            },
            {
                "text": "But you can still practice with these demo subtitles.",
                "start": 10.0,
                "duration": 4.0
            },
            {
                "text": "Try clicking on words to look them up in the dictionary.",
                "start": 14.5,
                "duration": 4.5
            },
            {
                "text": "You can also practice pronunciation by recording yourself.",
                "start": 19.5,
                "duration": 4.0
            },
            {
                "text": "Click on any sentence to jump to that part of the video.",
                "start": 24.0,
                "duration": 4.0
            },
            {
                "text": "Use keyboard shortcuts for better control.",
                "start": 28.5,
                "duration": 3.5
            },
            {
                "text": "Press Space to play or pause the video.",
                "start": 32.5,
                "duration": 3.5
            },
            {
                "text": "Press Alt + Arrow keys to navigate between sentences.",
                "start": 36.5,
                "duration": 4.0
            },
            {
                "text": "Happy learning!",
                "start": 41.0,
                "duration": 2.0
            }
        ]
    
    @staticmethod
    def fetch_ted_transcript(ted_url: str) -> Optional[List[Dict]]:
        """
        额外方法: 从 TED 视频获取字幕
        TED 字幕是开放的，可靠性远高于 YouTube
        
        参数: ted_url - TED talk URL 或 talk ID
        返回: transcript 列表
        """
        try:
            print(f"🔍 [TED] 尝试获取 TED 字幕: {ted_url}")
            
            # TED 字幕 API: https://www.ted.com/talks/<slug>/subtitle/en/manifest.json
            # 或者从页面中提取
            import re
            import urllib.request
            
            # 如果是完整 URL，提取 talk ID
            if ted_url.startswith('http'):
                match = re.search(r'talks/([^/]+)', ted_url)
                if match:
                    talk_slug = match.group(1)
                else:
                    print(f"⚠️ [TED] 无法解析 URL")
                    return None
            else:
                talk_slug = ted_url
            
            # 尝试获取字幕 manifest
            manifest_url = f'https://www.ted.com/talks/{talk_slug}/subtitle/en/manifest.json'
            req = urllib.request.Request(manifest_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                manifest = json.loads(resp.read().decode('utf-8'))
            
            # 获取 VTT 字幕 URL
            vtt_url = None
            for lang_sub in manifest.get('captions', []):
                if lang_sub.get('language') == 'en':
                    vtt_url = lang_sub.get('url', '')
                    break
            
            if not vtt_url:
                print(f"⚠️ [TED] 未找到英文字幕")
                return None
            
            # 下载并解析 VTT
            if not vtt_url.startswith('http'):
                vtt_url = f'https://www.ted.com{vtt_url}'
            
            vtt_text = SubtitleFetcher._download_subtitle_text(vtt_url)
            if vtt_text:
                transcript = SubtitleFetcher._parse_vtt_text(vtt_text)
                if transcript:
                    print(f"✅ [TED] 成功获取 {len(transcript)} 条字幕")
                    return transcript
            
            return None
            
        except Exception as e:
            print(f"⚠️ [TED] 获取失败: {e}")
            return None
    
    @staticmethod
    def fetch_multi_source(video_id: str, use_cache: bool = True) -> Dict:
        """
        多源获取字幕
        
        优先级:
        1. 本地缓存
        2. youtube-transcript-api
        3. yt-dlp (✅ 已补全 VTT/SRT 解析)
        4. 备用数据
        
        替代方案（当 YouTube 无法获取时）:
        - fetch_ted_transcript(): TED 字幕完全开放
        - 本地视频 + 外挂 SRT/VTT 字幕
        - OpenAI Whisper 自动语音识别
        """
        
        # 1. 尝试从缓存加载
        if use_cache:
            cached = SubtitleFetcher.load_from_cache(video_id)
            if cached:
                return {
                    "status": "success",
                    "source": "cache",
                    "transcript": cached,
                    "count": len(cached)
                }
        
        # 2. 尝试 youtube-transcript-api
        transcript = SubtitleFetcher.fetch_youtube_transcript_api(video_id)
        if transcript:
            SubtitleFetcher.save_to_cache(video_id, transcript)
            return {
                "status": "success",
                "source": "youtube-transcript-api",
                "transcript": transcript,
                "count": len(transcript)
            }
        
        # 3. 尝试 yt-dlp
        transcript = SubtitleFetcher.fetch_yt_dlp(video_id)
        if transcript:
            SubtitleFetcher.save_to_cache(video_id, transcript)
            return {
                "status": "success",
                "source": "yt-dlp",
                "transcript": transcript,
                "count": len(transcript)
            }
        
        # 4. 返回备用数据
        fallback = SubtitleFetcher.get_fallback_transcript()
        return {
            "status": "fallback",
            "source": "demo",
            "message": "真实字幕获取失败，使用演示数据",
            "transcript": fallback,
            "count": len(fallback)
        }


# ==========================================
# API 端点
# ==========================================

@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "message": "Vlog English Pro 后端服务运行中",
        "version": "2.0.0",
        "features": {
            "youtube_transcript_api": HAS_YOUTUBE_TRANSCRIPT,
            "yt_dlp": HAS_YT_DLP,
            "cache": True,
            "azure_speech": bool(SPEECH_KEY)
        }
    }


@app.get("/ted-transcript")
async def get_ted_transcript(talk_url: str):
    """
    获取 TED 演讲字幕
    
    参数:
        talk_url: TED talk URL 或 talk slug
    
    返回:
        JSON 格式字幕数据
    """
    print(f"\n{'='*50}")
    print(f"🎓 请求 TED 字幕: {talk_url}")
    print(f"{'='*50}")
    
    result = SubtitleFetcher.fetch_ted_transcript(talk_url)
    
    if result:
        return {
            "status": "success",
            "source": "ted",
            "transcript": result,
            "count": len(result)
        }
    else:
        return {
            "status": "error",
            "source": "ted",
            "message": "TED 字幕获取失败",
            "transcript": [],
            "count": 0
        }


@app.get("/transcript")
async def get_transcript(video_id: str, use_cache: bool = True):
    """
    获取视频字幕
    
    参数:
        video_id: YouTube 视频 ID
        use_cache: 是否使用缓存 (默认: True)
    
    返回:
        JSON 格式字幕数据
    """
    print(f"\n{'='*50}")
    print(f"📺 请求字幕: {video_id}")
    print(f"{'='*50}")
    
    result = SubtitleFetcher.fetch_multi_source(video_id, use_cache)
    
    print(f"✅ 返回结果: {result['status']} ({result['source']}) - {result['count']} 句")
    print(f"{'='*50}\n")
    
    return result


@app.post("/clear-cache")
async def clear_cache(video_id: Optional[str] = None):
    """
    清除缓存
    
    参数:
        video_id: 指定视频 ID (可选，不指定则清空所有)
    """
    try:
        if video_id:
            cache_file = SubtitleFetcher.get_cache_path(video_id)
            if cache_file.exists():
                cache_file.unlink()
                return {"status": "success", "message": f"已清除 {video_id} 的缓存"}
            else:
                return {"status": "error", "message": "缓存不存在"}
        else:
            # 清空所有缓存
            count = 0
            for cache_file in CACHE_DIR.glob("*.json"):
                cache_file.unlink()
                count += 1
            return {"status": "success", "message": f"已清除 {count} 个缓存文件"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/cache-list")
async def list_cache():
    """列出所有缓存的视频"""
    try:
        cached_videos = []
        for cache_file in CACHE_DIR.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cached_videos.append({
                        "video_id": data.get('video_id'),
                        "sentence_count": len(data.get('transcript', [])),
                        "cached_at": data.get('cached_at')
                    })
            except:
                pass
        
        return {
            "status": "success",
            "count": len(cached_videos),
            "videos": cached_videos
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/assess")
async def assess_pronunciation(
    file: UploadFile = File(...), 
    reference_text: str = Form(...)
):
    """
    发音评估接口（需要 Azure Speech Key）
    """
    print(f"\n{'='*50}")
    print(f"🎤 评测单句: {reference_text}")
    print(f"{'='*50}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
        temp_audio.write(await file.read())
        temp_audio_path = temp_audio.name

    try:
        if not SPEECH_KEY or SPEECH_KEY == "":
            print("⚠️ 未配置 Azure Speech Key")
            return {
                "status": "error",
                "details": "未配置 Azure Speech Key，请设置 SPEECH_KEY 环境变量"
            }

        speech_config = speechsdk.SpeechConfig(
            subscription=SPEECH_KEY, 
            region=SPEECH_REGION
        )
        audio_config = speechsdk.audio.AudioConfig(filename=temp_audio_path)
        
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True
        )
        
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        pronunciation_config.apply_to(recognizer)
        
        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            assess_result = speechsdk.PronunciationAssessmentResult(result)
            
            word_details = []
            for word in assess_result.words:
                word_details.append({
                    "word": word.word,
                    "accuracy": word.accuracy_score,
                    "error_type": word.error_type
                })
            
            print(f"✅ 评分完成! 总分: {assess_result.accuracy_score}")
            print(f"{'='*50}\n")
            
            return {
                "status": "success",
                "score": round(assess_result.accuracy_score, 1),
                "fluency": round(assess_result.fluency_score, 1),
                "accuracy": round(assess_result.accuracy_score, 1),
                "words": word_details
            }
            
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("⚠️ 没听到声音")
            return {
                "status": "error",
                "details": "没听到声音，请确保麦克风正常工作"
            }
            
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            print(f"❌ Azure 错误: {cancellation.error_details}")
            return {
                "status": "error",
                "details": f"Azure 配置错误: {cancellation.error_details}"
            }
            
    except Exception as e:
        print(f"❌ 评估失败: {e}")
        print(f"{'='*50}\n")
        return {
            "status": "error",
            "details": str(e)
        }
        
    finally:
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except:
            pass


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Vlog English Pro 后端服务启动中...")
    print("="*60)
    print(f"📝 字幕服务:")
    print(f"   - youtube-transcript-api: {'✅ 已安装' if HAS_YOUTUBE_TRANSCRIPT else '❌ 未安装'}")
    print(f"   - yt-dlp: {'✅ 已安装' if HAS_YT_DLP else '❌ 未安装'}")
    print(f"   - 本地缓存: ✅ 已启用 ({CACHE_DIR})")
    print(f"🎤 发音评估: {'✅ 已配置' if SPEECH_KEY else '❌ 需配置 Azure Key'}")
    print("="*60)
    print("💡 提示:")
    print("   1. 字幕获取支持多个来源，自动备用")
    print("   2. 成功获取的字幕会自动缓存，下次更快")
    port = int(os.environ.get("PORT", "8001"))
    print(f"   3. 访问 http://0.0.0.0:{port} 查看服务状态")
    print(f"   4. 访问 http://0.0.0.0:{port}/cache-list 查看缓存")
    print("="*60)
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=port)
