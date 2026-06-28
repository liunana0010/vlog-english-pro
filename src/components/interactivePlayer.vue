<template>
  <!-- ✅ 修复: 真正的可复用组件，不再包含独立页面布局 -->
  <div class="interactive-player">

    <!-- YouTube 播放器容器 -->
    <div class="video-box">
      <div id="youtube-player"></div>
    </div>

    <!-- 视频标题与频道信息 -->
    <h1 class="main-title" v-html="videoTitle"></h1>
    <div class="channel-row">
      <div class="channel-avatar">{{ channelInitial }}</div>
      <div class="channel-info">
        <div class="channel-name">{{ channelName || '未知频道' }}</div>
        <div class="channel-subscribers">英语学习频道</div>
      </div>
      <button class="subscribe-btn" type="button">订阅</button>
    </div>

    <!-- 字幕面板 -->
    <div class="caption-section" v-loading="isLoading" element-loading-text="正在加载字幕...">
      <div class="caption-header">
        <span class="caption-title">📜 台词本</span>
        <span class="caption-hint">点击/拖动句子跳转 · 点击单词查词</span>
        <el-tag v-if="transcript.length > 0" type="info" effect="dark" size="small">
          已同步 ({{ transcript.length }} 条)
        </el-tag>
        <el-tag
          v-if="transcriptSource"
          :type="transcriptSource === 'demo' ? 'warning' : 'success'"
          effect="dark"
          size="small"
        >
          字幕来源: {{ transcriptSource }}
        </el-tag>
        <el-tag v-else type="warning" effect="dark" size="small">无字幕</el-tag>
      </div>

      <div v-if="transcript.length === 0 && !isLoading" class="empty-transcript">
        <p>暂无字幕数据</p>
        <p class="empty-hint">该视频可能没有英文字幕，或字幕获取失败</p>
      </div>

      <div v-else class="transcript-box" ref="transcriptContainer" @scroll="handleScroll">
        <div
          v-for="(line, index) in transcript"
          :key="index"
          :id="`line-${index}`"
          class="transcript-line"
          :class="{ 'active-line': activeLineIndex === index }"
          @click="seekToLine(index)"
          draggable="true"
          @dragstart="handleDragStart(index)"
          @dragend="handleDragEnd"
        >
          <span class="play-indicator" v-show="activeLineIndex === index">▶</span>
          <span class="word-wrapper">
            <span
              v-for="(wordObj, wIndex) in getWordsForLine(line, index)"
              :key="wIndex"
              class="clickable-word"
              :class="getWordClass(wordObj, index)"
              @click.stop="onWordClick(wordObj.word)"
            >{{ wordObj.word }}</span>
          </span>
          <!-- 评分结果显示在句子右边 -->
          <span class="line-score" v-if="lineScores[index]">
            <el-tag :type="lineScores[index] >= 80 ? 'success' : lineScores[index] >= 60 ? 'warning' : 'danger'" size="small" effect="dark">
              {{ lineScores[index] }}分
            </el-tag>
          </span>
          <!-- 跟读按钮 -->
          <span class="line-actions">
            <button 
              class="read-aloud-btn" 
              :class="{ 'recording': isRecording && recordingIndex === index }"
              @click.stop="toggleRecording(index)"
              :title="isRecording ? '停止录音' : '跟读这句'"
            >
              <span v-if="!isRecording">🎙️</span>
              <span v-else>⏹️</span>
            </button>
            <button 
              class="play-line-btn" 
              @click.stop="playLineAudio(line.text)"
              title="播放原句"
            >🔊</button>
          </span>
        </div>
      </div>
    </div>

    <!-- 录音评分结果 -->
    <div v-if="scoredWords.length > 0" class="score-legend">
      <el-tag type="success" style="margin-right: 8px;">● 优秀</el-tag>
      <el-tag type="danger" style="margin-right: 8px;">● 需改进</el-tag>
      <el-tag type="info">● 未读</el-tag>
    </div>

    <!-- 词典弹窗 (使用 Teleport 挂载到 body，避免被 overflow 裁剪) -->
    <teleport to="body">
      <div
        v-if="showDict"
        class="dict-popover"
        :style="{ left: dictPosition.x + 'px', top: dictPosition.y + 'px' }"
        @click.stop
      >
        <div class="dict-header">
          <span class="dict-word">{{ currentWord }}</span>
          <span class="dict-audio-btn" @click="playAudio(currentWord)">🔈</span>
          <span class="dict-close" @click="showDict = false">✕</span>
        </div>
        <div v-if="isLoadingDef" class="dict-loading">查询中...</div>
        <div v-else class="dict-def">
          <div v-if="wordPhonetic" class="dict-phonetic">{{ wordPhonetic }}</div>
          <div v-html="wordDefinition"></div>
        </div>
        <div class="dict-footer">
          <el-button size="small" type="primary" @click="onAddToVocab({ word: currentWord, definition: wordDefinition })">
            + 加入生词本
          </el-button>
        </div>
      </div>
    </teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, reactive, onBeforeUnmount, onMounted, computed } from 'vue'
import { API_BASE_URL } from '../config'

// ==========================================
// ✅ Props - 接收父组件数据
// ==========================================
const props = defineProps<{
  videoId: string
  transcript: Array<{ text: string; start: number; duration: number }>
  transcriptSource?: string
  scoredWords: Array<{ word: string; accuracy: number; error_type: string }>
  videoTitle?: string
  channelName?: string
}>()

const channelInitial = computed(() => {
  const name = props.channelName?.trim()
  return name ? name.charAt(0).toUpperCase() : '?'
})

// ==========================================
// ✅ Emits - 向父组件发送事件
// ==========================================
const emit = defineEmits<{
  'line-change': [text: string]          // 当前高亮句子变化
  'word-click': [word: string]           // 单词被点击
  'seek': [time: number]                // 请求跳转到指定时间
  'add-vocab': [data: { word: string; definition: string }] // 加入生词本
  'record-start': [index: number]        // 开始录音
  'record-stop': [index: number]         // 停止录音
}>()

// ==========================================
// 字幕同步状态
// ==========================================
const activeLineIndex = ref(-1)
const transcriptContainer = ref<HTMLElement | null>(null)
const isLoading = ref(false)
const isUserScrolling = ref(false)
const isDragging = ref(false)
const dragLineIndex = ref(-1)

// 跟读录音状态
const isRecording = ref(false)
const recordingIndex = ref(-1)
const recordingTime = ref(0)
const currentScore = ref<number | null>(null)
const recordedAudioUrl = ref<string | null>(null)
const lineScores = reactive<Record<number, number>>({}) // 每句的评分结果
const lineWordResults = reactive<Record<number, any[]>>({}) // 每句的单词评分详情

let timer: any = null
let audioContext: AudioContext | null = null
let scriptProcessor: ScriptProcessorNode | null = null
let audioInput: MediaStreamAudioSourceNode | null = null
let audioData: Float32Array[] = []
let stream: MediaStream | null = null

// 监听 transcript 变化，重置高亮
watch(() => props.transcript, () => {
  activeLineIndex.value = -1
}, { immediate: true })

// 监听 scoredWords 变化，触发重新渲染
watch(() => props.scoredWords, () => {
  // Vue 响应式会自动处理
}, { deep: true })

// ==========================================
// 单词处理
// ==========================================
const getWordsForLine = (line: { text: string }, lineIndex: number) => {
  const text = line.text || ''
  const words = text.split(/\s+/).filter((w: string) => w.length > 0)
  return words.map((word: string) => ({ word, lineIndex }))
}

const getWordClass = (wordObj: { word: string; lineIndex: number }, lineIndex: number) => {
  // 检查该句是否有评分结果
  const wordResults = lineWordResults[lineIndex]
  if (!wordResults || wordResults.length === 0) return ''

  const cleanWord = wordObj.word.replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, '').toLowerCase()
  const scored = wordResults.find((w: any) => w.word.toLowerCase() === cleanWord)

  if (!scored) return ''
  
  // 根据准确率显示颜色
  // 绿色：准确率 >= 80（读得好）
  // 红色高光：准确率 < 60（读得不标准）
  // 黄色：60-80（中等）
  if (scored.accuracy >= 80) return 'good-word' // 绿色字体
  if (scored.accuracy < 60) return 'bad-word-highlight' // 红色高光
  return 'medium-word' // 黄色
}

// ==========================================
// 字幕同步 - 由父组件调用
// ==========================================
let syncTimer: ReturnType<typeof setInterval> | null = null

/**
 * 父组件传入当前播放时间，自动更新高亮行
 * 这是字幕实时交互的核心方法
 */
const syncCurrentTime = (currentTime: number) => {
  if (!props.transcript || props.transcript.length === 0) return
  // 用户正在拖动或手动滚动时，不自动滚动
  if (isUserScrolling.value || isDragging.value) return

  let newIndex = -1
  for (let i = 0; i < props.transcript.length; i++) {
    const line = props.transcript[i]
    if (currentTime >= line.start && currentTime < line.start + line.duration) {
      newIndex = i
      break
    }
  }

  if (newIndex !== -1 && newIndex !== activeLineIndex.value) {
    activeLineIndex.value = newIndex
    emit('line-change', props.transcript[newIndex].text)
    scrollToActiveLine()
  }
}

/**
 * 点击句子跳转播放
 */
const seekToLine = (index: number) => {
  if (!props.transcript[index]) return
  const time = props.transcript[index].start
  emit('seek', time)
  activeLineIndex.value = index
  emit('line-change', props.transcript[index].text)
  scrollToActiveLine()
}

/**
 * 拖动开始
 */
const handleDragStart = (index: number) => {
  isDragging.value = true
  dragLineIndex.value = index
}

/**
 * 拖动结束 - 跳转到拖动的句子
 */
const handleDragEnd = () => {
  if (dragLineIndex.value !== -1) {
    seekToLine(dragLineIndex.value)
  }
  isDragging.value = false
  dragLineIndex.value = -1
}

/**
 * 用户手动滚动时，暂停自动滚动
 */
const handleScroll = () => {
  isUserScrolling.value = true
  // 3秒后恢复自动滚动
  setTimeout(() => {
    isUserScrolling.value = false
  }, 3000)
}

/**
 * 自动滚动到居中位置（像音乐软件歌词滚动）
 */
const scrollToActiveLine = async () => {
  if (isUserScrolling.value || isDragging.value) return
  
  await nextTick()
  const container = transcriptContainer.value
  const activeLine = document.getElementById(`line-${activeLineIndex.value}`)

  if (!container || !activeLine) return

  const containerHeight = container.clientHeight
  const lineOffsetTop = activeLine.offsetTop
  const lineHeight = activeLine.clientHeight
  
  // 计算居中位置 - 当前句子保持在容器垂直中心
  const scrollTo = lineOffsetTop - (containerHeight / 2) + (lineHeight / 2)
  
  // 确保滚动位置在有效范围内
  const maxScroll = container.scrollHeight - containerHeight
  const finalScroll = Math.max(0, Math.min(scrollTo, maxScroll))

  // 立即滚动到目标位置（不带动画，避免延迟）
  container.scrollTop = finalScroll
}

// ==========================================
// 跟读录音功能
// ==========================================

/**
 * 切换录音状态
 */
const toggleRecording = (index: number) => {
  if (isRecording.value) {
    stopRecording()
  } else {
    startRecording(index)
  }
}

/**
 * 开始录音
 */
const startRecording = async (index: number) => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    audioInput = audioContext.createMediaStreamSource(stream)
    scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1)
    audioData = []

    scriptProcessor.onaudioprocess = (e: AudioProcessingEvent) => {
      if (!isRecording.value) return
      audioData.push(new Float32Array(e.inputBuffer.getChannelData(0)))
    }

    audioInput.connect(scriptProcessor)
    scriptProcessor.connect(audioContext.destination)
    
    isRecording.value = true
    recordingIndex.value = index
    recordingTime.value = 0
    currentScore.value = null

    emit('record-start', index)

    timer = setInterval(() => {
      recordingTime.value++
      if (recordingTime.value >= 30) stopRecording()
    }, 1000)

  } catch (err) {
    console.error('无法开启麦克风:', err)
    alert('无法开启麦克风，请检查权限设置')
  }
}

/**
 * 停止录音
 */
const stopRecording = async () => {
  if (isRecording.value) {
    isRecording.value = false
    clearInterval(timer)
    
    if (scriptProcessor && audioInput && audioContext) {
      audioInput.disconnect()
      scriptProcessor.disconnect()
    }
    if (stream) stream.getTracks().forEach(t => t.stop())

    const wavBlob = encodeWAV(audioData, audioContext?.sampleRate || 44100)
    recordedAudioUrl.value = URL.createObjectURL(wavBlob)
    await sendToBackend(wavBlob)
    
    emit('record-stop', recordingIndex.value)
    recordingIndex.value = -1
  }
}

/**
 * 发送到后端进行 Azure 评分
 */
const sendToBackend = async (blob: Blob) => {
  const formData = new FormData()
  formData.append('file', blob, 'recording.wav')

  const targetLine = props.transcript[recordingIndex.value]
  if (!targetLine) {
    console.warn('未找到参考文本')
    return
  }

  formData.append('reference_text', targetLine.text)

  try {
    const response = await fetch(`${API_BASE_URL}/assess`, { method: 'POST', body: formData })
    const result = await response.json()

    if (result.status === 'success') {
      // 存储该句的总分（满分100）
      lineScores[recordingIndex.value] = Math.round(result.score)
      currentScore.value = result.score
      
      // 存储单词评分详情
      if (result.words && Array.isArray(result.words)) {
        lineWordResults[recordingIndex.value] = result.words
      }
      
      // 更新 props.scoredWords（用于显示颜色）
      emit('word-click', JSON.stringify(result.words))
    }
  } catch (error) {
    console.error('评分失败:', error)
  }
}

/**
 * 编码为 WAV 格式
 */
const encodeWAV = (audioData: Float32Array[], sampleRate: number): Blob => {
  const length = audioData.reduce((acc, chunk) => acc + chunk.length, 0)
  const buffer = new ArrayBuffer(44 + length * 2)
  const view = new DataView(buffer)

  // WAV header
  const setUint16 = (data: number, offset: number) => {
    view.setUint16(offset, data, true)
  }
  const setUint32 = (data: number, offset: number) => {
    view.setUint32(offset, data, true)
  }

  setUint32(0x46464952, 0) // "RIFF"
  setUint32(36 + length * 2, 4) // file length
  setUint32(0x45564157, 8) // "WAVE"
  setUint32(0x20746d66, 12) // "fmt "
  setUint32(16, 16) // subchunk size
  setUint16(1, 20) // PCM format
  setUint16(1, 22) // channels
  setUint32(sampleRate, 24) // sample rate
  setUint32(sampleRate * 2, 28) // byte rate
  setUint16(2, 32) // block align
  setUint16(16, 34) // bits per sample
  setUint32(0x61746164, 36) // "data"
  setUint32(length * 2, 40) // data length

  // PCM data
  let offset = 44
  audioData.forEach(chunk => {
    for (let i = 0; i < chunk.length; i++) {
      const sample = Math.max(-1, Math.min(1, chunk[i]))
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
      offset += 2
    }
  })

  return new Blob([buffer], { type: 'audio/wav' })
}

/**
 * 使用 Web Speech API 播放句子
 */
const playLineAudio = (text: string) => {
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'en-US'
  u.rate = 0.9
  window.speechSynthesis.speak(u)
}

// ==========================================
// 词典功能 - 使用 dictionaryapi.dev API
// ==========================================
const showDict = ref(false)
const currentWord = ref('')
const wordDefinition = ref('')
const wordPhonetic = ref('')
const isLoadingDef = ref(false)
const dictPosition = reactive({ x: 0, y: 0 })

// 扩展词典（备用）
const cnDictionary: Record<string, string> = {
  "welcome": "欢迎", "amazing": "极好的", "never": "从不，决不",
  "gonna": "将要（going to 口语）", "wanna": "想要（want to 口语）",
  "give": "给予", "up": "向上，放弃", "let": "让", "down": "向下，失望",
  "around": "周围", "desert": "抛弃，沙漠", "make": "制作，使",
  "cry": "哭泣", "say": "说", "goodbye": "再见", "tell": "告诉",
  "lie": "说谎，躺", "hurt": "伤害", "video": "视频",
  "experience": "体验", "practice": "练习", "speaking": "说话",
  "hello": "你好", "world": "世界", "thank": "感谢",
  "please": "请", "sorry": "对不起", "help": "帮助",
  "love": "爱", "like": "喜欢", "want": "想要", "need": "需要",
  "know": "知道", "think": "认为", "time": "时间", "people": "人们",
  "great": "伟大的", "good": "好的", "new": "新的", "first": "第一",
  "last": "最后的", "long": "长的", "right": "正确的，右边",
  "old": "老的，旧的", "big": "大的", "high": "高的",
  "small": "小的", "different": "不同的", "important": "重要的",
  "every": "每个", "many": "许多", "some": "一些", "get": "得到",
  "go": "去", "come": "来", "see": "看见", "look": "看",
  "use": "使用", "find": "找到", "work": "工作", "call": "呼叫",
  "try": "尝试", "ask": "询问", "learn": "学习", "study": "学习",
  "english": "英语", "language": "语言", "word": "单词",
  "sentence": "句子", "pronunciation": "发音", "listen": "听",
  "read": "阅读", "write": "写", "speak": "说",
  "beautiful": "美丽的", "interesting": "有趣的", "happy": "快乐的",
  "today": "今天", "tomorrow": "明天", "yesterday": "昨天",
  "morning": "早上", "night": "夜晚", "day": "天，日",
  "week": "周", "month": "月", "year": "年",
  "friend": "朋友", "family": "家庭", "home": "家",
  "school": "学校", "teacher": "老师", "student": "学生",
  "book": "书", "music": "音乐", "food": "食物", "water": "水",
  "house": "房子", "city": "城市", "country": "国家",
  "story": "故事", "idea": "想法", "problem": "问题",
  "answer": "答案", "question": "问题", "way": "方式，道路"
}

/**
 * 从支持中文释义的词典API获取单词定义
 */
const fetchWordDefinition = async (word: string) => {
  try {
    // 调用中文词典API获取完整释义
    const cnResponse = await fetch(`https://v2.xxapi.cn/api/englishwords?word=${word}`)
    if (!cnResponse.ok) {
      throw new Error('API请求失败')
    }
    const cnData = await cnResponse.json()
    
    if (cnData.code === 200 && cnData.data) {
      const data = cnData.data
      
      // 获取音标
      wordPhonetic.value = data.ukphone || data.usphone || ''
      
      // 构建释义HTML
      let definitionsHtml = ''
      
      // 中文翻译（主要释义）
      if (data.translations && data.translations.length > 0) {
        definitionsHtml += '<div class="meaning-block"><strong>翻译</strong>'
        data.translations.forEach((t: any) => {
          definitionsHtml += `<div class="definition-item">• ${t.tran_cn || ''} <span class="word-pos">${t.pos || ''}</span></div>`
        })
        definitionsHtml += '</div>'
      }
      
      // 例句
      if (data.sentences && data.sentences.length > 0) {
        definitionsHtml += '<div class="meaning-block"><strong>例句</strong>'
        data.sentences.slice(0, 2).forEach((s: any) => {
          definitionsHtml += `<div class="example-item"><span class="en-sentence">${s.s_content || ''}</span><br><span class="cn-sentence">${s.s_cn || ''}</span></div>`
        })
        definitionsHtml += '</div>'
      }
      
      // 短语
      if (data.phrases && data.phrases.length > 0) {
        definitionsHtml += '<div class="meaning-block"><strong>短语</strong>'
        data.phrases.slice(0, 3).forEach((p: any) => {
          definitionsHtml += `<div class="phrase-item">• ${p.p_content || ''} - ${p.p_cn || ''}</div>`
        })
        definitionsHtml += '</div>'
      }
      
      // 同义词
      if (data.synonyms && data.synonyms.length > 0) {
        definitionsHtml += '<div class="meaning-block"><strong>同义词</strong>'
        data.synonyms.slice(0, 2).forEach((syn: any) => {
          const words = syn.Hwds?.map((h: any) => h.word).join(', ') || ''
          definitionsHtml += `<div class="synonym-item">• ${words} (${syn.tran || ''})</div>`
        })
        definitionsHtml += '</div>'
      }
      
      wordDefinition.value = definitionsHtml || '暂无释义'
      return true
    }
    return false
  } catch (error) {
    console.log('API查询失败，使用备用词典')
    return false
  }
}

const onWordClick = async (word: string) => {
  const cleanWord = word.replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, '').toLowerCase()
  currentWord.value = word.replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, '')
  showDict.value = true
  isLoadingDef.value = true
  wordDefinition.value = ''
  wordPhonetic.value = ''

  // 定位到点击位置附近
  const event = window.event as MouseEvent
  if (event) {
    dictPosition.x = Math.min(event.clientX, window.innerWidth - 300)
    dictPosition.y = Math.max(event.clientY - 180, 10)
  }

  // 先尝试在线词典 API
  const apiSuccess = await fetchWordDefinition(cleanWord)
  
  // 如果API失败，使用备用词典
  if (!apiSuccess) {
    wordPhonetic.value = ''
    wordDefinition.value = cnDictionary[cleanWord] || '暂无释义，请尝试其他单词'
  }
  
  isLoadingDef.value = false
  emit('word-click', cleanWord)
}

const playAudio = (word: string) => {
  const u = new SpeechSynthesisUtterance(word)
  u.lang = 'en-US'
  window.speechSynthesis.speak(u)
}

const onAddToVocab = (data: { word: string; definition: string }) => {
  emit('add-vocab', data)
  showDict.value = false
}

// 点击外部关闭词典
const handleGlobalClick = (e: MouseEvent) => {
  if (showDict.value) {
    const popover = document.querySelector('.dict-popover')
    if (popover && !popover.contains(e.target as Node)) {
      showDict.value = false
    }
  }
}

onMounted(() => {
  document.addEventListener('click', handleGlobalClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleGlobalClick)
  if (syncTimer) clearInterval(syncTimer)
})

// ==========================================
// 暴露方法给父组件调用
// ==========================================
defineExpose({
  syncCurrentTime,  // 父组件播放时定时调用此方法同步字幕
  seekToLine,
  scrollToActiveLine
})
</script>

<style scoped>
.interactive-player {
  max-width: 100%;
  display: flex;
  flex-direction: column;
  flex: 1;
  color: #f1f1f1;
}

.video-box {
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  width: 100%;
  aspect-ratio: 16 / 9;
}

.video-box :deep(iframe),
#youtube-player {
  width: 100%;
  height: 100%;
}

.main-title {
  margin: 12px 0 8px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: #f1f1f1;
  flex-shrink: 0;
}

.channel-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #303030;
}

.channel-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #c9a227, #8b6914);
  color: #fff;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.channel-info {
  flex: 1;
  min-width: 0;
}

.channel-name {
  font-size: 14px;
  font-weight: 600;
  color: #f1f1f1;
}

.channel-subscribers {
  font-size: 12px;
  color: #aaa;
  margin-top: 2px;
}

.subscribe-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 18px;
  background: #f1f1f1;
  color: #0f0f0f;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
}

.subscribe-btn:hover {
  background: #d9d9d9;
}

.caption-section {
  background: #181818;
  border-radius: 12px;
  border: 1px solid #303030;
  overflow: hidden;
}

.caption-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #303030;
  background: #212121;
}

.caption-title {
  color: #3ea6ff;
  font-weight: 600;
}

.caption-hint {
  font-size: 12px;
  color: #aaa;
  flex: 1;
}

.empty-transcript {
  text-align: center;
  color: #aaa;
  padding: 40px 0;
}

.empty-hint {
  color: #777;
  font-size: 13px;
  margin-top: 8px;
}

/* 台词本：固定显示约 6 句，超出滚动 */
.transcript-box {
  max-height: 336px;
  overflow-y: auto;
  padding: 8px 12px;
  background: #181818;
  position: relative;
  scrollbar-width: thin;
  scrollbar-color: #555 #181818;
}

.transcript-box::-webkit-scrollbar {
  width: 8px;
}

.transcript-box::-webkit-scrollbar-track {
  background: #181818;
}

.transcript-box::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

.transcript-box::-webkit-scrollbar-thumb:hover {
  background: #777;
}

.transcript-line {
  padding: 10px 12px;
  margin-bottom: 4px;
  min-height: 48px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: flex-start;
  color: #aaa;
  font-size: 14px;
  line-height: 1.5;
  user-select: none;
  opacity: 0.65;
}

.transcript-line:hover {
  background: #272727;
  opacity: 0.9;
}

.transcript-line:active {
  background: #303030;
}

.active-line {
  background: #272727;
  color: #f1f1f1;
  font-weight: 600;
  font-size: 15px;
  border-left: 3px solid #3ea6ff;
  opacity: 1;
}

.play-indicator {
  color: #3ea6ff;
  margin-right: 8px;
  font-size: 12px;
  margin-top: 3px;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.word-wrapper {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 3px 5px;
}

/* 单词交互 */
.clickable-word {
  cursor: pointer;
  padding: 1px 3px;
  border-radius: 3px;
  transition: 0.2s;
}

.clickable-word:hover {
  background: rgba(62, 166, 255, 0.2);
  color: #3ea6ff;
}

/* 打分颜色 */
.good-word {
  color: #67C23A;
  font-weight: bold;
}

.bad-word-highlight {
  background-color: rgba(245, 108, 108, 0.3);
  color: #F56C6C;
  font-weight: bold;
  border-radius: 4px;
  padding: 2px 4px;
}

.medium-word {
  color: #E6A23C;
  font-weight: 500;
}

.missing-word {
  color: #909399;
  text-decoration: line-through;
}

/* 句子评分标签 */
.line-score {
  margin-left: 10px;
  flex-shrink: 0;
}

/* 句子操作按钮 */
.line-actions {
  display: flex;
  gap: 6px;
  margin-left: 8px;
  opacity: 0;
  transition: opacity 0.3s;
}

.transcript-line:hover .line-actions {
  opacity: 1;
}

.active-line .line-actions {
  opacity: 1;
}

.read-aloud-btn,
.play-line-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  background: #303030;
  color: #f1f1f1;
}

.read-aloud-btn:hover {
  background: #3ea6ff;
  color: #fff;
  transform: scale(1.1);
}

.play-line-btn:hover {
  background: #2ecc71;
  color: #fff;
  transform: scale(1.1);
}

.read-aloud-btn.recording {
  background: #F56C6C;
  color: #fff;
  animation: recording-pulse 1s infinite;
}

@keyframes recording-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

/* 评分图例 */
.score-legend {
  margin-top: 12px;
  padding: 8px;
  text-align: center;
  flex-shrink: 0;
}

/* 词典弹窗 */
.dict-popover {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 16px;
  width: 300px;
  max-height: 400px;
  overflow-y: auto;
}

.dict-header {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
  margin-bottom: 10px;
}

.dict-word {
  font-size: 20px;
  font-weight: bold;
  color: #409EFF;
}

.dict-phonetic {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.dict-audio-btn {
  cursor: pointer;
  font-size: 18px;
}

.dict-audio-btn:hover {
  transform: scale(1.2);
}

.dict-close {
  margin-left: auto;
  cursor: pointer;
  color: #999;
  font-size: 16px;
}

.dict-close:hover {
  color: #333;
}

.dict-loading {
  color: #999;
  padding: 10px 0;
}

.dict-def {
  line-height: 1.8;
  color: #606266;
  padding: 5px 0;
}

.meaning-block {
  margin-bottom: 12px;
}

.definition-item {
  margin-left: 10px;
  color: #303133;
  margin-bottom: 4px;
}

.cn-def {
  color: #409EFF;
  font-weight: 500;
  margin-left: 8px;
}

.example-item {
  margin-left: 20px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

.en-sentence {
  color: #303133;
  font-style: italic;
}

.cn-sentence {
  color: #67C23A;
  display: block;
  margin-top: 4px;
}

.phrase-item {
  margin-left: 10px;
  color: #606266;
  font-size: 13px;
}

.synonym-item {
  margin-left: 10px;
  color: #909399;
  font-size: 13px;
}

.word-pos {
  color: #909399;
  font-size: 12px;
  margin-left: 6px;
}

.dict-footer {
  margin-top: 12px;
  text-align: center;
}

/* 滚动条美化 */
.transcript-box::-webkit-scrollbar {
  width: 6px;
}

.transcript-box::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.transcript-box::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .transcript-box {
    max-height: 300px;
  }
  
  .transcript-line {
    font-size: 14px;
    padding: 10px;
  }
}
</style>
