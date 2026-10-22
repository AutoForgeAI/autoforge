/**
 * Settings View
 *
 * Full-page settings view with the same controls as SettingsModal,
 * rendered in a scrollable centered layout with Card-based section
 * groupings instead of inside a Dialog.
 */

import { useState } from 'react'
import { Loader2, AlertCircle, AlertTriangle, Check, Moon, Sun, Eye, EyeOff, ShieldCheck, Settings, Languages } from 'lucide-react'
import { useSettings, useUpdateSettings, useAvailableModels, useAvailableProviders } from '@/hooks/useProjects'
import { useTheme, THEMES } from '@/hooks/useTheme'
import type { EffortLevel, ProviderInfo } from '@/lib/types'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useI18n, LOCALES, type TranslationKey } from '@/i18n'

const PROVIDER_INFO_KEYS: Record<string, TranslationKey> = {
  claude: 'settings.provider.claude',
  kimi: 'settings.provider.kimi',
  glm: 'settings.provider.glm',
  ollama: 'settings.provider.ollama',
  custom: 'settings.provider.custom',
}

export function SettingsView() {
  const { data: settings, isLoading, isError, refetch } = useSettings()
  const { data: modelsData } = useAvailableModels()
  const { data: providersData } = useAvailableProviders()
  const updateSettings = useUpdateSettings()
  const { theme, setTheme, darkMode, toggleDarkMode } = useTheme()
  const { t, tRich, locale, setLocale } = useI18n()

  const [showAuthToken, setShowAuthToken] = useState(false)
  const [authTokenInput, setAuthTokenInput] = useState('')
  const [customModelInput, setCustomModelInput] = useState('')
  const [customBaseUrlInput, setCustomBaseUrlInput] = useState('')

  const handleYoloToggle = () => {
    if (settings && !updateSettings.isPending) {
      updateSettings.mutate({ yolo_mode: !settings.yolo_mode })
    }
  }

  const handleModelChange = (modelId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ api_model: modelId })
    }
  }

  const handleTestingRatioChange = (ratio: number) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ testing_agent_ratio: ratio })
    }
  }

  const handleBatchSizeChange = (size: number) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ batch_size: size })
    }
  }

  const handleTestingBatchSizeChange = (size: number) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ testing_batch_size: size })
    }
  }

  const handleEffortChange = (level: EffortLevel) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ effort: level })
    }
  }

  const handleProviderChange = (providerId: string) => {
    if (!updateSettings.isPending) {
      updateSettings.mutate({ api_provider: providerId })
      setAuthTokenInput('')
      setShowAuthToken(false)
      setCustomModelInput('')
      setCustomBaseUrlInput('')
    }
  }

  const handleSaveAuthToken = () => {
    if (authTokenInput.trim() && !updateSettings.isPending) {
      updateSettings.mutate({ api_auth_token: authTokenInput.trim() })
      setAuthTokenInput('')
      setShowAuthToken(false)
    }
  }

  const handleSaveCustomBaseUrl = () => {
    if (customBaseUrlInput.trim() && !updateSettings.isPending) {
      updateSettings.mutate({ api_base_url: customBaseUrlInput.trim() })
      setCustomBaseUrlInput('')
    }
  }

  const handleSaveCustomModel = () => {
    if (customModelInput.trim() && !updateSettings.isPending) {
      updateSettings.mutate({ api_model: customModelInput.trim() })
      setCustomModelInput('')
    }
  }

  const providers = providersData?.providers ?? []
  const models = modelsData?.models ?? []
  const isSaving = updateSettings.isPending
  const currentProvider = settings?.api_provider ?? 'claude'
  const currentProviderInfo: ProviderInfo | undefined = providers.find(p => p.id === currentProvider)
  const isAlternativeProvider = currentProvider !== 'claude'
  const showAuthField = isAlternativeProvider && currentProviderInfo?.requires_auth
  const showBaseUrlField = currentProvider === 'custom' || currentProvider === 'azure'
  const showCustomModelInput = currentProvider === 'custom' || currentProvider === 'ollama'

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Settings size={24} className="text-primary" />
          <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
          {isSaving && <Loader2 className="animate-spin" size={16} />}
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin" size={24} />
            <span className="ml-2">{t('settings.loading')}</span>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {t('settings.loadFailed')}
              <Button
                variant="link"
                onClick={() => refetch()}
                className="ml-2 p-0 h-auto"
              >
                {t('settings.retry')}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Settings Content */}
        {settings && !isLoading && (
          <>
            {/* Appearance Card */}
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.appearance')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Theme Selection */}
                <div className="space-y-3">
                  <Label className="font-medium">{t('settings.theme')}</Label>
                  <div className="grid gap-2">
                    {THEMES.map((themeOption) => (
                      <button
                        key={themeOption.id}
                        onClick={() => setTheme(themeOption.id)}
                        className={`flex items-center gap-3 p-3 rounded-lg border-2 transition-colors text-left ${
                          theme === themeOption.id
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50 hover:bg-muted/50'
                        }`}
                      >
                        {/* Color swatches */}
                        <div className="flex gap-0.5 shrink-0">
                          <div
                            className="w-5 h-5 rounded-sm border border-border/50"
                            style={{ backgroundColor: themeOption.previewColors.background }}
                          />
                          <div
                            className="w-5 h-5 rounded-sm border border-border/50"
                            style={{ backgroundColor: themeOption.previewColors.primary }}
                          />
                          <div
                            className="w-5 h-5 rounded-sm border border-border/50"
                            style={{ backgroundColor: themeOption.previewColors.accent }}
                          />
                        </div>

                        {/* Theme info */}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-sm">{themeOption.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {t(`theme.${themeOption.id}.description`)}
                          </div>
                        </div>

                        {/* Checkmark */}
                        {theme === themeOption.id && (
                          <Check size={18} className="text-primary shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Dark Mode Toggle */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="dark-mode" className="font-medium">
                      {t('settings.darkMode')}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t('settings.darkModeDescription')}
                    </p>
                  </div>
                  <Button
                    id="dark-mode"
                    variant="outline"
                    size="sm"
                    onClick={toggleDarkMode}
                    className="gap-2"
                  >
                    {darkMode ? <Sun size={16} /> : <Moon size={16} />}
                    {darkMode ? t('settings.light') : t('settings.dark')}
                  </Button>
                </div>

                {/* Language Selection */}
                <div className="space-y-2">
                  <div className="space-y-0.5">
                    <Label className="font-medium flex items-center gap-1.5">
                      <Languages size={14} />
                      {t('language.label')}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t('language.description')}
                    </p>
                  </div>
                  <div className="flex rounded-lg border overflow-hidden" role="radiogroup" aria-label={t('language.label')}>
                    {LOCALES.map((option) => (
                      <button
                        key={option.id}
                        role="radio"
                        aria-checked={locale === option.id}
                        lang={option.id}
                        onClick={() => setLocale(option.id)}
                        className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                          locale === option.id
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-background text-foreground hover:bg-muted'
                        }`}
                      >
                        {option.nativeName}
                      </button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* API Configuration Card */}
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.apiConfiguration')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* API Provider Selection */}
                <div className="space-y-3">
                  <Label className="font-medium">{t('settings.apiProvider')}</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {providers.map((provider) => (
                      <button
                        key={provider.id}
                        onClick={() => handleProviderChange(provider.id)}
                        disabled={isSaving}
                        className={`py-1.5 px-3 text-sm font-medium rounded-md border transition-colors ${
                          currentProvider === provider.id
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'bg-background text-foreground border-border hover:bg-muted'
                        } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {provider.name.split(' (')[0]}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {PROVIDER_INFO_KEYS[currentProvider] ? t(PROVIDER_INFO_KEYS[currentProvider]) : ''}
                  </p>

                  {currentProvider === 'claude' && (
                    <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/20 mt-2">
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                      <AlertDescription className="text-xs text-amber-700 dark:text-amber-300">
                        <span>
                          {tRich('settings.claudeAuthWarning', {
                            loginCommand: <code className="text-xs">claude login</code>,
                            envVar: <code className="text-xs">ANTHROPIC_API_KEY</code>,
                          })}
                        </span>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Auth Token Field */}
                  {showAuthField && (
                    <div className="space-y-2 pt-1">
                      <Label className="text-sm">{t('settings.apiKey')}</Label>
                      {settings.api_has_auth_token && !authTokenInput && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <ShieldCheck size={14} className="text-green-500" />
                          <span>{t('settings.configured')}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto py-0.5 px-2 text-xs"
                            onClick={() => setAuthTokenInput(' ')}
                          >
                            {t('settings.change')}
                          </Button>
                        </div>
                      )}
                      {(!settings.api_has_auth_token || authTokenInput) && (
                        <div className="flex gap-2">
                          <div className="relative flex-1">
                            <input
                              type={showAuthToken ? 'text' : 'password'}
                              value={authTokenInput.trim()}
                              onChange={(e) => setAuthTokenInput(e.target.value)}
                              placeholder={t('settings.apiKeyPlaceholder')}
                              className="w-full py-1.5 px-3 pe-9 text-sm border rounded-md bg-background"
                            />
                            <button
                              type="button"
                              onClick={() => setShowAuthToken(!showAuthToken)}
                              className="absolute end-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            >
                              {showAuthToken ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                          </div>
                          <Button
                            size="sm"
                            onClick={handleSaveAuthToken}
                            disabled={!authTokenInput.trim() || isSaving}
                          >
                            {t('settings.save')}
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Custom Base URL Field */}
                  {showBaseUrlField && (
                    <div className="space-y-2 pt-1">
                      <Label className="text-sm">{t('settings.baseUrl')}</Label>
                      {settings.api_base_url && !customBaseUrlInput && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <ShieldCheck size={14} className="text-green-500" />
                          <span className="truncate">{settings.api_base_url}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto py-0.5 px-2 text-xs shrink-0"
                            onClick={() => setCustomBaseUrlInput(settings.api_base_url || '')}
                          >
                            {t('settings.change')}
                          </Button>
                        </div>
                      )}
                      {(!settings.api_base_url || customBaseUrlInput) && (
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={customBaseUrlInput}
                            onChange={(e) => setCustomBaseUrlInput(e.target.value)}
                            placeholder={currentProvider === 'azure' ? 'https://your-resource.services.ai.azure.com/anthropic' : 'https://api.example.com/v1'}
                            className="flex-1 py-1.5 px-3 text-sm border rounded-md bg-background"
                          />
                          <Button
                            size="sm"
                            onClick={handleSaveCustomBaseUrl}
                            disabled={!customBaseUrlInput.trim() || isSaving}
                          >
                            {t('settings.save')}
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Model Selection */}
                <div className="space-y-2">
                  <Label className="font-medium">{t('settings.model')}</Label>
                  {models.length > 0 && (
                    <div className="flex rounded-lg border overflow-hidden">
                      {models.map((model) => (
                        <button
                          key={model.id}
                          onClick={() => handleModelChange(model.id)}
                          disabled={isSaving}
                          className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                            (settings.api_model ?? settings.model) === model.id
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-background text-foreground hover:bg-muted'
                          } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                          <span className="block">{model.name}</span>
                          <span className="block text-xs opacity-60">{model.id}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  {/* Custom model input for Ollama/Custom */}
                  {showCustomModelInput && (
                    <div className="flex gap-2 pt-1">
                      <input
                        type="text"
                        value={customModelInput}
                        onChange={(e) => setCustomModelInput(e.target.value)}
                        placeholder={t('settings.customModelPlaceholder')}
                        className="flex-1 py-1.5 px-3 text-sm border rounded-md bg-background"
                        onKeyDown={(e) => e.key === 'Enter' && handleSaveCustomModel()}
                      />
                      <Button
                        size="sm"
                        onClick={handleSaveCustomModel}
                        disabled={!customModelInput.trim() || isSaving}
                      >
                        {t('settings.set')}
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Agent Configuration Card */}
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.agentConfiguration')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* YOLO Mode Toggle */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="yolo-mode" className="font-medium">
                      {t('settings.yoloMode')}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {t('settings.yoloModeDescription')}
                    </p>
                  </div>
                  <Switch
                    id="yolo-mode"
                    checked={settings.yolo_mode}
                    onCheckedChange={handleYoloToggle}
                    disabled={isSaving}
                  />
                </div>

                {/* Reasoning Effort */}
                <div className="space-y-2">
                  <Label className="font-medium">{t('settings.effort')}</Label>
                  <p className="text-sm text-muted-foreground">
                    {t('settings.effortDescription')}
                  </p>
                  <div className="flex rounded-lg border overflow-hidden">
                    {(['low', 'medium', 'high', 'xhigh', 'max'] as EffortLevel[]).map((level) => (
                      <button
                        key={level}
                        onClick={() => handleEffortChange(level)}
                        disabled={isSaving}
                        className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                          (settings.effort ?? 'xhigh') === level
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-background text-foreground hover:bg-muted'
                        } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Regression Agents */}
                <div className="space-y-2">
                  <Label className="font-medium">{t('settings.regressionAgents')}</Label>
                  <p className="text-sm text-muted-foreground">
                    {t('settings.regressionAgentsDescription')}
                  </p>
                  <div className="flex rounded-lg border overflow-hidden">
                    {[0, 1, 2, 3].map((ratio) => (
                      <button
                        key={ratio}
                        onClick={() => handleTestingRatioChange(ratio)}
                        disabled={isSaving}
                        className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
                          settings.testing_agent_ratio === ratio
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-background text-foreground hover:bg-muted'
                        } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {ratio}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Features per Coding Agent */}
                <div className="space-y-2">
                  <Label className="font-medium">{t('settings.codingBatchSize')}</Label>
                  <p className="text-sm text-muted-foreground">
                    {t('settings.codingBatchSizeDescription')}
                  </p>
                  <Slider
                    min={1}
                    max={15}
                    value={settings.batch_size ?? 3}
                    onChange={handleBatchSizeChange}
                    disabled={isSaving}
                  />
                </div>

                {/* Features per Testing Agent */}
                <div className="space-y-2">
                  <Label className="font-medium">{t('settings.testingBatchSize')}</Label>
                  <p className="text-sm text-muted-foreground">
                    {t('settings.testingBatchSizeDescription')}
                  </p>
                  <Slider
                    min={1}
                    max={15}
                    value={settings.testing_batch_size ?? 3}
                    onChange={handleTestingBatchSizeChange}
                    disabled={isSaving}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Update Error */}
            {updateSettings.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  {t('settings.saveFailed')}
                </AlertDescription>
              </Alert>
            )}
          </>
        )}
      </div>
    </div>
  )
}
