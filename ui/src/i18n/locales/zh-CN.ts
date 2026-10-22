import type { Messages } from './en'

/**
 * Simplified Chinese message catalog.
 *
 * Missing keys fall back to English at runtime, but typing this as a
 * `Partial<Messages>` would hide gaps — keep it complete.
 */
export const zhCN: Messages = {
  'language.label': '语言',
  'language.description': 'AutoForge 界面的显示语言',

  'sidebar.views': '视图',
  'sidebar.tools': '工具',
  'sidebar.dashboard': '仪表盘',
  'sidebar.kanban': '看板',
  'sidebar.graph': '依赖图',
  'sidebar.browsers': '浏览器',
  'sidebar.terminal': '终端',
  'sidebar.logs': '日志',
  'sidebar.assistant': '助手',
  'sidebar.selectProject': '选择一个项目以开始',
  'sidebar.settings': '设置',
  'sidebar.lightMode': '浅色模式',
  'sidebar.darkMode': '深色模式',
  'sidebar.docs': '文档',
  'sidebar.expand': '展开侧边栏',
  'sidebar.collapse': '收起',

  'settings.title': '设置',
  'settings.loading': '正在加载设置...',
  'settings.loadFailed': '加载设置失败',
  'settings.retry': '重试',
  'settings.saveFailed': '保存设置失败，请重试。',
  'settings.save': '保存',
  'settings.set': '设置',
  'settings.change': '更改',
  'settings.configured': '已配置',

  'settings.appearance': '外观',
  'settings.theme': '主题',
  'settings.darkMode': '深色模式',
  'settings.darkModeDescription': '在浅色和深色外观之间切换',
  'settings.light': '浅色',
  'settings.dark': '深色',

  'theme.twitter.description': '简洁现代的蓝色设计',
  'theme.claude.description': '温暖的米色调搭配橙色点缀',
  'theme.neo-brutalism.description': '大胆的配色与硬朗的阴影',
  'theme.retro-arcade.description': '鲜艳的粉色与青色像素风',
  'theme.aurora.description': '深紫与青绿，如北极光一般',
  'theme.business.description': '深海军蓝 (#000e4e) 与灰色单色调',

  'settings.apiConfiguration': 'API 配置',
  'settings.apiProvider': 'API 提供商',
  'settings.provider.claude': '默认提供商。使用 Claude CLI 凭据，推荐使用 API 密钥认证。',
  'settings.provider.kimi': '在 kimi.com 获取 API 密钥',
  'settings.provider.glm': '在 open.bigmodel.cn 获取 API 密钥',
  'settings.provider.ollama': '在本地运行模型。从 ollama.com 安装',
  'settings.provider.custom': '连接任意兼容 OpenAI 的 API 端点。',
  'settings.claudeAuthWarning':
    'Anthropic 的政策可能不允许第三方代理使用基于订阅的认证（{loginCommand}）。' +
    '建议使用 API 密钥提供商，或设置 {envVar} 环境变量，以避免潜在的账户问题。',
  'settings.apiKey': 'API 密钥',
  'settings.apiKeyPlaceholder': '输入 API 密钥...',
  'settings.baseUrl': 'Base URL',
  'settings.model': '模型',
  'settings.customModelPlaceholder': '自定义模型名称...',

  'settings.agentConfiguration': '代理配置',
  'settings.yoloMode': 'YOLO 模式',
  'settings.yoloModeDescription': '跳过测试以快速构建原型',
  'settings.effort': '推理强度',
  'settings.effortDescription': 'Claude 在回复前思考的深度。自主编码推荐使用 xhigh。',
  'settings.regressionAgents': '回归测试代理',
  'settings.regressionAgentsDescription': '回归测试代理的数量（0 = 禁用）',
  'settings.codingBatchSize': '每个编码代理的功能数',
  'settings.codingBatchSizeDescription': '每个编码代理会话分配的功能数量',
  'settings.testingBatchSize': '每个测试代理的功能数',
  'settings.testingBatchSizeDescription': '每个测试代理会话分配的功能数量',
}
