<template>
  <el-container class="layout-container">
    <el-header class="header">
      <div class="header-left">
        <el-dropdown trigger="click" @command="handleSelect">
          <button class="menu-btn" type="button" aria-label="菜单">☰</button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="home">🏠 练习室</el-dropdown-item>
              <el-dropdown-item command="history">📊 学习大厅</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <span class="logo-text" @click="handleSelect('home')">Vlog English Pro</span>
      </div>

      <div class="header-search">
        <el-input
          v-model="searchQuery"
          placeholder="搜索 YouTube (如: TED)"
          class="search-input"
          @keyup.enter="searchYouTube"
        >
          <template #suffix>
            <span class="search-icon" @click="searchYouTube">🔍</span>
          </template>
        </el-input>
      </div>

      <div class="nav-right">
        <el-badge :value="vocabulary.length" class="item" :hidden="vocabulary.length === 0">
          <el-button @click="showVocabDrawer = true" circle>📖</el-button>
        </el-badge>
      </div>
    </el-header>

    <el-container v-show="activeTab === 'home'" class="home-container">
      <div class="practice-layout">
        <el-aside class="aside">
          <div class="filter-chips">
            <button
              v-for="tag in filterTags"
              :key="tag"
              class="chip"
              :class="{ active: activeFilter === tag }"
              type="button"
              @click="selectFilter(tag)"
            >{{ tag }}</button>
          </div>
          <el-scrollbar class="video-list-scroll">
            <div v-if="videos.length === 0" class="empty-tip">暂无视频，搜索试试？</div>
            <div
              v-for="video in videos"
              :key="video.id"
              class="video-item"
              :class="{ active: currentVideo.id === video.id }"
              @click="switchVideo(video)"
            >
              <div class="video-thumb-wrap">
                <el-image :src="video.thumbnail" class="video-thumb" fit="cover" />
              </div>
              <div class="video-info">
                <div class="video-title" v-html="video.title"></div>
                <div class="video-meta">{{ video.channel }}</div>
              </div>
            </div>
          </el-scrollbar>
        </el-aside>

        <el-main class="main-content">
          <InteractivePlayer
            ref="interactivePlayerRef"
            :video-id="currentVideo.id"
            :transcript="currentTranscript"
            :scored-words="wordResults"
            :video-title="currentVideo.title"
            :channel-name="currentVideo.channel"
            @line-change="handleLineChange"
            @word-click="onWordClick"
            @seek="handleSeek"
            @add-vocab="handleAddVocab"
          />
        </el-main>
      </div>
    </el-container>

    <div v-show="activeTab === 'home'" class="control-bar">
      <div class="control-panel">
        <div class="actions">
          <el-button
            :type="isRecording ? 'danger' : 'primary'"
            size="large"
            round
            @click="isRecording ? stopRecording() : startRecording()"
            :disabled="activeLineIndex === -1"
          >
            <template v-if="isRecording">⏹ 停止录音 ({{ recordingTime }}s)</template>
            <template v-else>🎙️ 跟读当前句</template>
          </el-button>
          <el-button
            v-if="recordedAudioUrl && !isRecording"
            type="warning"
            size="large"
            round
            @click="playRecording"
          >
            ▶️ 听听我的发音
          </el-button>
        </div>

        <div v-if="lastScore !== null" class="score-summary">
          <el-tag type="success" effect="dark" size="large">总分: {{ lastScore }}</el-tag>
          <el-tag type="info">准确度: {{ lastAccuracy }} | 流利度: {{ lastFluency }}</el-tag>
        </div>
      </div>
    </div>

    <el-container v-show="activeTab === 'history'" class="history-container">
      <el-main>
        <div class="history-header"><h1>📊 我的学习大厅</h1></div>
        <el-row :gutter="20" style="margin-bottom: 20px;">
          <el-col :span="8"><el-card shadow="hover" class="stat-card"><h3>累计练习</h3><div class="stat-num">{{ studyHistory.length }}</div></el-card></el-col>
          <el-col :span="8"><el-card shadow="hover" class="stat-card"><h3>最高得分</h3><div class="stat-num high-score">{{ maxScore }}</div></el-card></el-col>
          <el-col :span="8"><el-card shadow="hover" class="stat-card"><h3>生词积累</h3><div class="stat-num">{{ vocabulary.length }}</div></el-card></el-col>
        </el-row>
        <el-card>
          <el-table :data="studyHistory" stripe style="width: 100%">
            <el-table-column prop="date" label="时间" width="180" />
            <el-table-column prop="videoTitle" label="视频" />
            <el-table-column prop="score" label="得分" width="100"><template #default="scope"><el-tag>{{ scope.row.score }}</el-tag></template></el-table-column>
          </el-table>
        </el-card>
      </el-main>
    </el-container>

    <el-drawer v-model="showVocabDrawer" title="📖 我的生词本" direction="rtl" size="400px">
      <div class="vocab-actions" v-if="vocabulary.length > 0">
        <el-button type="success" :disabled="selectedVocab.length === 0" @click="batchRemoveVocab" plain style="width: 100%;">标记已学会 ({{ selectedVocab.length }})</el-button>
      </div>
      <el-table :data="vocabulary" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="40" />
        <el-table-column prop="word" label="单词" width="100"><template #default="scope"><strong>{{ scope.row.word }}</strong></template></el-table-column>
        <el-table-column prop="definition" label="释义" />
        <el-table-column width="50"><template #default="scope"><span class="speaker-icon-small" @click="playWordAudio(scope.row.word)">🔈</span></template></el-table-column>
      </el-table>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import InteractivePlayer from './components/interactivePlayer.vue'
import { YOUTUBE_API_KEY, API_BASE_URL } from './config'

// ==========================================
// 页面状态
// ==========================================
const activeTab = ref('home')
const handleSelect = (key: string) => { activeTab.value = key }

// ==========================================
// 视频搜索与切换
// ==========================================
const searchQuery = ref('')
const videos = ref<any[]>([])
const isSearching = ref(false)
const filterTags = ['vlog my life', 'TED sppech', 'Makeup vlog', 'Music', 'Interview']
const activeFilter = ref('全部')
const currentVideo = ref<any>({ id: '', title: '请先搜索视频或点击左侧测试视频', channel: '' })

const selectFilter = (tag: string) => {
  activeFilter.value = tag
  if (tag === '全部') return
  searchQuery.value = tag
  searchYouTube()
}

// ==========================================
// 字幕相关
// ==========================================
const currentTranscript = ref<any[]>([])
const activeLineIndex = ref(-1)
const activeSentenceText = ref('')

// ==========================================
// YouTube Player
// ==========================================
let player: any = null
let playerInterval: any = null

onMounted(() => {
  console.log('🚀 开始初始化应用...')

  // 加载 YouTube IFrame API
  if (!(window as any).YT) {
    console.log('📥 正在加载 YouTube IFrame API...')
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    const firstScriptTag = document.getElementsByTagName('script')[0]
    firstScriptTag.parentNode?.insertBefore(tag, firstScriptTag)
  }

  ;(window as any).onYouTubeIframeAPIReady = () => {
    console.log('✅ YouTube API 加载完成')
    initPlayer()
  }

  if ((window as any).YT && (window as any).YT.Player) {
    console.log('✅ YouTube API 已存在，直接初始化')
    initPlayer()
  }

  loadTestVideos()
})

onBeforeUnmount(() => {
  if (playerInterval) clearInterval(playerInterval)
  if (player) player.destroy()
})

// 🎯 测试视频
const loadTestVideos = () => {
  videos.value = [
    {
      id: 'dQw4w9WgXcQ',
      title: '🎵 测试视频 1 - Rick Astley',
      channel: 'Rick Astley',
      thumbnail: 'https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg'
    },
    {
      id: 'jNQXAC9IVRw',
      title: '🎬 测试视频 2 - Me at the zoo',
      channel: 'jawed',
      thumbnail: 'https://i.ytimg.com/vi/jNQXAC9IVRw/mqdefault.jpg'
    },
    {
      id: '9bZkp7q19f0',
      title: '🎤 测试视频 3 - Gangnam Style',
      channel: 'officialpsy',
      thumbnail: 'https://i.ytimg.com/vi/9bZkp7q19f0/mqdefault.jpg'
    }
  ]

  if (videos.value.length > 0 && !currentVideo.value.id) {
    switchVideo(videos.value[0])
  }
}

// ==========================================
// YouTube 播放器初始化
// ==========================================
const getPlayerSize = () => {
  const container = document.getElementById('youtube-player')
  const box = container?.parentElement
  const width = box?.offsetWidth || 960
  return {
    width: '100%',
    height: String(Math.round(width * 9 / 16))
  }
}

const initPlayer = () => {
  if (player) return

  console.log('🎬 正在初始化 YouTube 播放器...')

  try {
    const size = getPlayerSize()
    player = new (window as any).YT.Player('youtube-player', {
      height: size.height,
      width: size.width,
      videoId: '',
      playerVars: {
        autoplay: 0,
        controls: 1,
        modestbranding: 1,
        rel: 0,
        origin: window.location.origin
      },
      events: {
        onReady: onPlayerReady,
        onStateChange: onPlayerStateChange,
        onError: onPlayerError
      }
    })
  } catch (error) {
    console.error('❌ 播放器初始化失败:', error)
    ElMessage.error('播放器初始化失败，请刷新页面重试')
  }
}

const onPlayerReady = (event: any) => {
  console.log('✅ YouTube Player 就绪')
  ElMessage.success('播放器已就绪')
}

const onPlayerError = (event: any) => {
  console.error('❌ YouTube Player 错误:', event.data)
  const errorMessages: Record<number, string> = {
    2: '视频 ID 无效',
    5: 'HTML5 播放器错误',
    100: '视频不存在或已被删除',
    101: '视频所有者不允许嵌入播放',
    150: '视频所有者不允许嵌入播放'
  }
  ElMessage.error(errorMessages[event.data] || '视频播放出错')
}

const onPlayerStateChange = (event: any) => {
  console.log('🎬 播放器状态:', event.data)

  if (event.data === 1) {
    // 播放中 - 启动字幕同步
    startSyncSubtitles()
  } else {
    stopSyncSubtitles()
  }
}

// ==========================================
// 🌟 字幕自动同步 (修复版)
// ==========================================
const interactivePlayerRef = ref<InstanceType<typeof InteractivePlayer> | null>(null)

const startSyncSubtitles = () => {
  if (playerInterval) clearInterval(playerInterval)

  console.log('🎯 启动字幕同步 (每100ms)')

  playerInterval = setInterval(() => {
    if (!player || !player.getCurrentTime) return
    if (!currentTranscript.value || currentTranscript.value.length === 0) return

    try {
      const currentTime = player.getCurrentTime()

      // ✅ 调用 InteractivePlayer 组件的 syncCurrentTime 方法
      if (interactivePlayerRef.value) {
        interactivePlayerRef.value.syncCurrentTime(currentTime)
      }
    } catch (error) {
      console.error('⚠️ 获取播放时间失败:', error)
    }
  }, 100)
}

const stopSyncSubtitles = () => {
  if (playerInterval) {
    clearInterval(playerInterval)
    playerInterval = null
    console.log('⏹ 停止字幕同步')
  }
}

// ==========================================
// 事件处理
// ==========================================
const handleLineChange = (text: string) => {
  activeSentenceText.value = text
  const idx = currentTranscript.value.findIndex((line) => line.text === text)
  if (idx !== -1) activeLineIndex.value = idx
  wordResults.value = []
  lastScore.value = null
}

const onWordClick = (word: string) => {
  console.log('📖 单词点击:', word)
}

const handleSeek = (time: number) => {
  if (!player || !player.seekTo) {
    ElMessage.warning('播放器未就绪')
    return
  }

  console.log(`🎯 跳转到 ${time}s`)
  player.seekTo(time, true)

  try {
    if (player.getPlayerState() !== 1) {
      player.playVideo()
    }
  } catch (error) {
    console.error('⚠️ 播放视频失败:', error)
  }
}

const handleAddVocab = (data: { word: string; definition: string }) => {
  if (!vocabulary.value.find(v => v.word === data.word)) {
    vocabulary.value.push({ ...data })
    saveVocab()
    ElMessage.success(`"${data.word}" 已加入生词本`)
  } else {
    ElMessage.info('该单词已在生词本中')
  }
}

// ==========================================
// YouTube 搜索
// ==========================================
const searchYouTube = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索内容')
    return
  }

  if (!YOUTUBE_API_KEY) {
    ElMessage.warning('请先配置 YouTube API Key')
    return
  }

  isSearching.value = true
  console.log('🔍 搜索:', searchQuery.value)

  try {
    const url = `https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=10&q=${encodeURIComponent(searchQuery.value)}&type=video&key=${YOUTUBE_API_KEY}`
    const response = await fetch(url)
    const data = await response.json()

    if (data.error) {
      ElMessage.error(`API 错误: ${data.error.message}`)
      return
    }

    if (data.items && data.items.length > 0) {
      videos.value = data.items.map((item: any) => ({
        id: item.id.videoId,
        title: item.snippet.title,
        channel: item.snippet.channelTitle,
        thumbnail: item.snippet.thumbnails.medium.url
      }))

      if (videos.value.length > 0) {
        await switchVideo(videos.value[0])
      }
    } else {
      ElMessage.warning('未找到相关视频')
    }
  } catch (error) {
    ElMessage.error('搜索失败')
  } finally {
    isSearching.value = false
  }
}

// ==========================================
// 切换视频
// ==========================================
const switchVideo = async (video: any) => {
  console.log('📺 切换视频:', video.title)

  currentVideo.value = video
  activeLineIndex.value = -1
  wordResults.value = []
  lastScore.value = null
  activeSentenceText.value = ''

  // 加载字幕
  await fetchTranscript(video.id)

  // 加载视频到播放器
  if (player && player.loadVideoById) {
    try {
      player.loadVideoById(video.id)
      console.log('✅ 视频加载成功')
    } catch (error) {
      console.error('❌ 视频加载失败:', error)
      ElMessage.error('视频加载失败')
    }
  } else {
    console.warn('⚠️ 播放器未就绪，等待初始化...')
    setTimeout(() => {
      if (player && player.loadVideoById) {
        player.loadVideoById(video.id)
      }
    }, 1000)
  }
}

// ==========================================
// 获取字幕
// ==========================================
const fetchTranscript = async (videoId: string) => {
  console.log('📝 正在获取字幕:', videoId)

  try {
    const response = await fetch(`${API_BASE_URL}/transcript?video_id=${videoId}`)
    const data = await response.json()

    if (data.transcript && data.transcript.length > 0) {
      currentTranscript.value = data.transcript
      console.log(`✅ 字幕加载成功 (${data.source}): ${data.transcript.length} 条`)
      ElMessage.success(`字幕加载成功 (${data.transcript.length} 条，来源: ${data.source})`)
      activeSentenceText.value = data.transcript[0].text
    } else {
      currentTranscript.value = []
      ElMessage.warning('未获取到字幕')
    }
  } catch (error) {
    console.error('❌ 获取字幕失败:', error)
    ElMessage.error(`获取字幕失败，请确保后端服务运行在 ${API_BASE_URL}`)
    currentTranscript.value = []
  }
}

// ==========================================
// 录音与评分
// ==========================================
const isRecording = ref(false)
const recordingTime = ref(0)
const recordedAudioUrl = ref<string | null>(null)
const lastScore = ref<number | null>(null)
const lastFluency = ref<number | null>(null)
const lastAccuracy = ref<number | null>(null)
const wordResults = ref<any[]>([])

let timer: any = null
let audioContext: AudioContext | null = null
let scriptProcessor: ScriptProcessorNode | null = null
let audioInput: MediaStreamAudioSourceNode | null = null
let audioData: Float32Array[] = []
let stream: MediaStream | null = null

const startRecording = async () => {
  if (activeLineIndex.value === -1) {
    ElMessage.warning('请先选择一句台词')
    return
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
    audioInput = audioContext.createMediaStreamSource(stream)
    scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1)
    audioData = []

    scriptProcessor.onaudioprocess = (e) => {
      if (!isRecording.value) return
      audioData.push(new Float32Array(e.inputBuffer.getChannelData(0)))
    }

    audioInput.connect(scriptProcessor)
    scriptProcessor.connect(audioContext.destination)
    isRecording.value = true
    recordingTime.value = 0

    if (player && player.pauseVideo) {
      player.pauseVideo()
    }

    timer = setInterval(() => {
      recordingTime.value++
      if (recordingTime.value >= 30) stopRecording()
    }, 1000)

    ElMessage.info('开始录音...')
  } catch (err) {
    ElMessage.error('无法开启麦克风')
  }
}

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
  }
}

const sendToBackend = async (blob: Blob) => {
  const formData = new FormData()
  formData.append('file', blob, 'recording.wav')

  const targetSentence = activeSentenceText.value
  if (!targetSentence) {
    ElMessage.warning('未找到参考文本')
    return
  }

  formData.append('reference_text', targetSentence)
  ElMessage.info('AI 正在评分...')

  try {
    const response = await fetch(`${API_BASE_URL}/assess`, { method: 'POST', body: formData })
    const result = await response.json()

    if (result.status === 'success') {
      lastScore.value = result.score
      lastFluency.value = result.fluency
      lastAccuracy.value = result.score
      wordResults.value = result.words

      saveHistory({
        date: new Date().toLocaleString(),
        videoTitle: currentVideo.value.title,
        score: result.score,
        fluency: result.fluency
      })

      ElMessage.success(`评分成功！得分: ${result.score}`)
    } else {
      ElMessage.warning(`评分失败: ${result.details}`)
    }
  } catch (error) {
    ElMessage.error('连接后端失败')
  }
}

const playRecording = () => {
  if (recordedAudioUrl.value) new Audio(recordedAudioUrl.value).play()
}

const encodeWAV = (buffers: Float32Array[], sampleRate: number) => {
  let totalLength = 0
  for (let b of buffers) totalLength += b.length
  const result = new Float32Array(totalLength)
  let offset = 0
  for (let b of buffers) { result.set(b, offset); offset += b.length }
  const buffer = new ArrayBuffer(44 + result.length * 2)
  const view = new DataView(buffer)
  const writeString = (v: DataView, o: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i))
  }
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + result.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, result.length * 2, true)
  let p = 44
  for (let i = 0; i < result.length; i++) {
    let s = Math.max(-1, Math.min(1, result[i]))
    view.setInt16(p, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
    p += 2
  }
  return new Blob([view], { type: 'audio/wav' })
}

// ==========================================
// 持久化
// ==========================================
const studyHistory = ref<any[]>(JSON.parse(localStorage.getItem('studyHistory') || '[]'))
const vocabulary = ref<any[]>(JSON.parse(localStorage.getItem('vocabulary') || '[]'))
const maxScore = computed(() => studyHistory.value.length ? Math.max(...studyHistory.value.map(h => h.score)) : 0)
const selectedVocab = ref<any[]>([])
const showVocabDrawer = ref(false)

const saveHistory = (record: any) => {
  studyHistory.value.unshift(record)
  localStorage.setItem('studyHistory', JSON.stringify(studyHistory.value))
}

const saveVocab = () => {
  localStorage.setItem('vocabulary', JSON.stringify(vocabulary.value))
}

const batchRemoveVocab = () => {
  const count = selectedVocab.value.length
  vocabulary.value = vocabulary.value.filter(item => !selectedVocab.value.find(s => s.word === item.word))
  saveVocab()
  selectedVocab.value = []
  ElMessage.success(`已标记 ${count} 个单词为已学会`)
}

const handleSelectionChange = (val: any[]) => {
  selectedVocab.value = val
}

const playWordAudio = (word: string) => {
  const u = new SpeechSynthesisUtterance(word)
  u.lang = 'en-US'
  window.speechSynthesis.speak(u)
}
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  width: 100%;
  background-color: #0f0f0f;
  color: #f1f1f1;
  display: flex;
  flex-direction: column;
}

/* 顶部导航栏 */
.header {
  background: #0f0f0f;
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid #303030;
  padding: 0 16px;
  height: 56px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.menu-btn {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #f1f1f1;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.menu-btn:hover {
  background: #272727;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: #c9a962;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: color 0.2s;
}

.logo-text:hover {
  color: #dbc88a;
}

.header-search {
  flex: 1;
  max-width: 720px;
  margin: 0 auto;
}

.search-input :deep(.el-input__wrapper) {
  background: #121212;
  border: 1px solid #303030;
  box-shadow: none;
  border-radius: 24px;
  padding: 0 16px;
}

.search-input :deep(.el-input__wrapper:hover),
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: #1c62b9;
  box-shadow: inset 0 0 0 1px #1c62b9;
}

.search-input :deep(.el-input__inner) {
  color: #f1f1f1;
  height: 40px;
}

.search-input :deep(.el-input__inner::placeholder) {
  color: #aaa;
}

.search-icon {
  cursor: pointer;
  font-size: 16px;
  color: #aaa;
  user-select: none;
  display: flex;
  align-items: center;
  padding-right: 4px;
}

.search-icon:hover {
  color: #f1f1f1;
}

.nav-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.nav-right :deep(.el-button) {
  background: #272727;
  border-color: #272727;
  color: #f1f1f1;
}

.nav-right :deep(.el-button:hover) {
  background: #3f3f3f;
  border-color: #3f3f3f;
}

/* 主体内容区 */
.home-container {
  flex: 1;
  display: flex;
  justify-content: center;
  width: 100%;
  padding: 16px 24px 80px;
}

.practice-layout {
  display: flex;
  align-items: flex-start;
  width: 100%;
  max-width: 1720px;
  gap: 16px;
}

.aside {
  flex: 0 0 32%;
  width: 32%;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 12px;
  flex-shrink: 0;
}

.chip {
  padding: 6px 12px;
  border-radius: 8px;
  border: none;
  background: #272727;
  color: #f1f1f1;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.chip:hover {
  background: #3f3f3f;
}

.chip.active {
  background: #f1f1f1;
  color: #0f0f0f;
}

.video-list-scroll {
  flex: 1;
  overflow-y: auto;
  max-height: calc(100vh - 140px);
}

.main-content {
  flex: 1;
  min-width: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  background: transparent;
}

/* 底部操作栏 */
.control-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #181818;
  border-top: 1px solid #303030;
  padding: 12px 24px;
  z-index: 100;
}

.control-panel {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 16px;
  max-width: 1720px;
  margin: 0 auto;
}

.score-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.empty-tip {
  text-align: center;
  color: #aaa;
  padding: 40px 0;
}

/* 视频列表项 - YouTube 风格 */
.video-item {
  display: flex;
  gap: 8px;
  padding: 8px;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.video-item:hover {
  background: #272727;
}

.video-item.active {
  background: #272727;
}

.video-thumb-wrap {
  position: relative;
  flex-shrink: 0;
}

.video-thumb {
  width: 168px;
  height: 94px;
  border-radius: 8px;
  display: block;
}

.video-info {
  flex: 1;
  overflow: hidden;
  min-width: 0;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  line-height: 1.4;
  margin-bottom: 6px;
  color: #f1f1f1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.video-meta {
  font-size: 12px;
  color: #aaa;
  line-height: 1.4;
}

/* 学习大厅 */
.history-container {
  background: #0f0f0f;
  flex: 1;
  overflow-y: auto;
  padding-bottom: 24px;
}

.history-container :deep(.el-card) {
  background: #181818;
  border-color: #303030;
  color: #f1f1f1;
}

.history-container :deep(.el-table) {
  background: transparent;
  color: #f1f1f1;
  --el-table-bg-color: #181818;
  --el-table-tr-bg-color: #181818;
  --el-table-header-bg-color: #212121;
  --el-table-row-hover-bg-color: #272727;
  --el-table-border-color: #303030;
  --el-table-text-color: #f1f1f1;
  --el-table-header-text-color: #aaa;
}

.history-header {
  padding: 20px;
}

.history-header h1 {
  color: #f1f1f1;
}

.stat-card {
  text-align: center;
}

.stat-card h3 {
  margin: 10px 0;
  color: #aaa;
}

.stat-num {
  font-size: 32px;
  font-weight: bold;
  color: #3ea6ff;
}

.high-score {
  color: #2ecc71;
}

.vocab-actions {
  margin-bottom: 20px;
}

.speaker-icon-small {
  cursor: pointer;
  color: #3ea6ff;
  transition: 0.2s;
}

.speaker-icon-small:hover {
  transform: scale(1.2);
}

@media (max-width: 1024px) {
  .practice-layout {
    flex-direction: column;
  }

  .aside {
    flex: 0 0 auto;
    width: 100%;
  }

  .header-search {
    max-width: 360px;
  }
}

@media (max-width: 768px) {
  .header {
    gap: 8px;
    padding: 0 8px;
  }

  .header-search {
    max-width: none;
    flex: 1;
  }
}
</style>
