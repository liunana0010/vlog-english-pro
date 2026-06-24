import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

// 引入 Element Plus 框架及其全套样式
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')