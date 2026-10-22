/**
 * English (source) message catalog.
 *
 * This file is the source of truth for translation keys: every other locale
 * is type-checked against it. Keys are grouped by UI area with dot notation.
 * Placeholders use `{name}` syntax and are filled in by `t(key, { name })`.
 */
export const en = {
  // Language names are shown in their own language, so they are not translated
  'language.label': 'Language',
  'language.description': 'Display language for the AutoForge interface',

  // Sidebar
  'sidebar.views': 'Views',
  'sidebar.tools': 'Tools',
  'sidebar.dashboard': 'Dashboard',
  'sidebar.kanban': 'Kanban',
  'sidebar.graph': 'Graph',
  'sidebar.browsers': 'Browsers',
  'sidebar.terminal': 'Terminal',
  'sidebar.logs': 'Logs',
  'sidebar.assistant': 'Assistant',
  'sidebar.selectProject': 'Select a project to get started',
  'sidebar.settings': 'Settings',
  'sidebar.lightMode': 'Light mode',
  'sidebar.darkMode': 'Dark mode',
  'sidebar.docs': 'Docs',
  'sidebar.expand': 'Expand sidebar',
  'sidebar.collapse': 'Collapse',

  // Settings
  'settings.title': 'Settings',
  'settings.loading': 'Loading settings...',
  'settings.loadFailed': 'Failed to load settings',
  'settings.retry': 'Retry',
  'settings.saveFailed': 'Failed to save settings. Please try again.',
  'settings.save': 'Save',
  'settings.set': 'Set',
  'settings.change': 'Change',
  'settings.configured': 'Configured',

  'settings.appearance': 'Appearance',
  'settings.theme': 'Theme',
  'settings.darkMode': 'Dark Mode',
  'settings.darkModeDescription': 'Switch between light and dark appearance',
  'settings.light': 'Light',
  'settings.dark': 'Dark',

  'theme.twitter.description': 'Clean and modern blue design',
  'theme.claude.description': 'Warm beige tones with orange accents',
  'theme.neo-brutalism.description': 'Bold colors with hard shadows',
  'theme.retro-arcade.description': 'Vibrant pink and teal pixel vibes',
  'theme.aurora.description': 'Deep violet and teal, like northern lights',
  'theme.business.description': 'Deep navy (#000e4e) and gray monochrome',

  'settings.apiConfiguration': 'API Configuration',
  'settings.apiProvider': 'API Provider',
  'settings.provider.claude': 'Default provider. Uses Claude CLI credentials. API key auth is recommended.',
  'settings.provider.kimi': 'Get an API key at kimi.com',
  'settings.provider.glm': 'Get an API key at open.bigmodel.cn',
  'settings.provider.ollama': 'Run models locally. Install from ollama.com',
  'settings.provider.custom': 'Connect to any OpenAI-compatible API endpoint.',
  'settings.claudeAuthWarning':
    "Anthropic's policy may not permit using subscription-based auth ({loginCommand}) with third-party agents. " +
    'Consider using an API key provider or setting the {envVar} environment variable to avoid potential account issues.',
  'settings.apiKey': 'API Key',
  'settings.apiKeyPlaceholder': 'Enter API key...',
  'settings.baseUrl': 'Base URL',
  'settings.model': 'Model',
  'settings.customModelPlaceholder': 'Custom model name...',

  'settings.agentConfiguration': 'Agent Configuration',
  'settings.yoloMode': 'YOLO Mode',
  'settings.yoloModeDescription': 'Skip testing for rapid prototyping',
  'settings.effort': 'Reasoning Effort',
  'settings.effortDescription': 'How deeply Claude thinks before responding. xhigh is recommended for autonomous coding.',
  'settings.regressionAgents': 'Regression Agents',
  'settings.regressionAgentsDescription': 'Number of regression testing agents (0 = disabled)',
  'settings.codingBatchSize': 'Features per Coding Agent',
  'settings.codingBatchSizeDescription': 'Number of features assigned to each coding agent session',
  'settings.testingBatchSize': 'Features per Testing Agent',
  'settings.testingBatchSizeDescription': 'Number of features assigned to each testing agent session',
}

export type TranslationKey = keyof typeof en
export type Messages = Record<TranslationKey, string>
