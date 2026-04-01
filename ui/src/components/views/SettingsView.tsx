/**
 * Settings View
 *
 * Full-page settings view with the same controls as SettingsModal,
 * rendered in a scrollable centered layout with Card-based section
 * groupings instead of inside a Dialog.
 */

import { useState } from 'react'
import { Loader2, AlertCircle, AlertTriangle, Check, Moon, Sun, Eye, EyeOff, ShieldCheck, Settings } from 'lucide-react'
import { useSettings, useUpdateSettings, useAvailableModels, useAvailableProviders } from '@/hooks/useProjects'
import { useTheme, THEMES } from '@/hooks/useTheme'
import type { ProviderInfo } from '@/lib/types'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const PROVIDER_INFO_TEXT: Record<string, string> = {
  claude: 'Default provider. Uses Claude CLI credentials. API key auth is recommended.',
  kimi: 'Get an API key at kimi.com',
  glm: 'Get an API key at open.bigmodel.cn',
  ollama: 'Run models locally. Install from ollama.com',
  custom: 'Connect to any OpenAI-compatible API endpoint.',
}

export function SettingsView() {
  const { data: settings, isLoading, isError, refetch } = useSettings()
  const { data: modelsData } = useAvailableModels()
  const { data: providersData } = useAvailableProviders()
  const updateSettings = useUpdateSettings()
  const { theme, setTheme, darkMode, toggleDarkMode } = useTheme()

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
          <h1 className="text-2xl font-bold">Settings</h1>
          {isSaving && <Loader2 className="animate-spin" size={16} />}
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin" size={24} />
            <span className="ml-2">Loading settings...</span>
          </div>
        )}

        {/* Error State */}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Failed to load settings
              <Button
                variant="link"
                onClick={() => refetch()}
                className="ml-2 p-0 h-auto"
              >
                Retry
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
                <CardTitle>Appearance</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Theme Selection */}
                <div className="space-y-3">
                  <Label className="font-medium">Theme</Label>
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
                            {themeOption.description}
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
                      Dark Mode
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Switch between light and dark appearance
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
                    {darkMode ? 'Light' : 'Dark'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* API Configuration Card */}
            <Card>
              <CardHeader>
                <CardTitle>API Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* API Provider Selection */}
                <div className="space-y-3">
                  <Label className="font-medium">API Provider</Label>
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
                    {PROVIDER_INFO_TEXT[currentProvider] ?? ''}
                  </p>

                  {currentProvider === 'claude' && (
                    <Alert className="border-amber-500/50 bg-amber-50 dark:bg-amber-950/20 mt-2">
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                      <AlertDescription className="text-xs text-amber-700 dark:text-amber-300">
                        Anthropic's policy may not permit using subscription-based auth (<code className="text-xs">claude login</code>) with third-party agents. Consider using an API key provider or setting the <code className="text-xs">ANTHROPIC_API_KEY</code> environment variable to avoid potential account issues.
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Auth Token Field */}
                  {showAuthField && (
                    <div className="space-y-2 pt-1">
                      <Label className="text-sm">API Key</Label>
                      {settings.api_has_auth_token && !authTokenInput && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <ShieldCheck size={14} className="text-green-500" />
                          <span>Configured</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto py-0.5 px-2 text-xs"
                            onClick={() => setAuthTokenInput(' ')}
                          >
                            Change
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
                              placeholder="Enter API key..."
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
                            Save
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Custom Base URL Field */}
                  {showBaseUrlField && (
                    <div className="space-y-2 pt-1">
                      <Label className="text-sm">Base URL</Label>
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
                            Change
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
                            Save
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Model Selection */}
                <div className="space-y-2">
                  <Label className="font-medium">Model</Label>
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
                        placeholder="Custom model name..."
                        className="flex-1 py-1.5 px-3 text-sm border rounded-md bg-background"
                        onKeyDown={(e) => e.key === 'Enter' && handleSaveCustomModel()}
                      />
                      <Button
                        size="sm"
                        onClick={handleSaveCustomModel}
                        disabled={!customModelInput.trim() || isSaving}
                      >
                        Set
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Agent Configuration Card */}
            <Card>
              <CardHeader>
                <CardTitle>Agent Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* YOLO Mode Toggle */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="yolo-mode" className="font-medium">
                      YOLO Mode
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Skip testing for rapid prototyping
                    </p>
                  </div>
                  <Switch
                    id="yolo-mode"
                    checked={settings.yolo_mode}
                    onCheckedChange={handleYoloToggle}
                    disabled={isSaving}
                  />
                </div>

                {/* Regression Agents */}
                <div className="space-y-2">
                  <Label className="font-medium">Regression Agents</Label>
                  <p className="text-sm text-muted-foreground">
                    Number of regression testing agents (0 = disabled)
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
                  <Label className="font-medium">Features per Coding Agent</Label>
                  <p className="text-sm text-muted-foreground">
                    Number of features assigned to each coding agent session
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
                  <Label className="font-medium">Features per Testing Agent</Label>
                  <p className="text-sm text-muted-foreground">
                    Number of features assigned to each testing agent session
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
                  Failed to save settings. Please try again.
                </AlertDescription>
              </Alert>
            )}
          </>
        )}
      </div>
    </div>
  )
}
