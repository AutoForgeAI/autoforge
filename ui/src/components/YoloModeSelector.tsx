import { useState } from 'react'
import { Zap, Shield, Eye, GitBranch, TrendingUp, ChevronDown, Check } from 'lucide-react'

export type YoloMode = 'standard' | 'yolo' | 'yolo_review' | 'yolo_parallel' | 'yolo_staged'

interface YoloModeOption {
  value: YoloMode
  label: string
  description: string
  icon: React.ReactNode
  skipTesting: boolean
  hasReview: boolean
  parallel: boolean
}

const YOLO_MODES: YoloModeOption[] = [
  {
    value: 'standard',
    label: 'Standard',
    description: 'Full testing with browser verification',
    icon: <Shield size={16} />,
    skipTesting: false,
    hasReview: false,
    parallel: false,
  },
  {
    value: 'yolo',
    label: 'YOLO',
    description: 'Skip testing for rapid prototyping',
    icon: <Zap size={16} />,
    skipTesting: true,
    hasReview: false,
    parallel: false,
  },
  {
    value: 'yolo_review',
    label: 'YOLO + Review',
    description: 'Skip testing but add periodic code reviews',
    icon: <Eye size={16} />,
    skipTesting: true,
    hasReview: true,
    parallel: false,
  },
  {
    value: 'yolo_parallel',
    label: 'Parallel YOLO',
    description: 'Multiple YOLO agents on independent features',
    icon: <GitBranch size={16} />,
    skipTesting: true,
    hasReview: false,
    parallel: true,
  },
  {
    value: 'yolo_staged',
    label: 'Staged YOLO',
    description: 'YOLO for early phases, testing for late phases',
    icon: <TrendingUp size={16} />,
    skipTesting: true,
    hasReview: false,
    parallel: false,
  },
]

interface YoloModeSelectorProps {
  value: YoloMode
  onChange: (mode: YoloMode) => void
  disabled?: boolean
  compact?: boolean
}

export function YoloModeSelector({
  value,
  onChange,
  disabled = false,
  compact = false,
}: YoloModeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)

  const selectedMode = YOLO_MODES.find(m => m.value === value) || YOLO_MODES[0]

  const handleSelect = (mode: YoloMode) => {
    onChange(mode)
    setIsOpen(false)
  }

  if (compact) {
    return (
      <div className="relative">
        <button
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          className={`
            neo-button flex items-center gap-2 px-3 py-2
            ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
            ${selectedMode.skipTesting ? 'bg-yellow-100 border-yellow-500' : ''}
          `}
          title={selectedMode.description}
        >
          <span className={selectedMode.skipTesting ? 'text-yellow-600' : ''}>
            {selectedMode.icon}
          </span>
          <span className="font-bold text-sm">{selectedMode.label}</span>
          <ChevronDown size={14} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute top-full left-0 mt-1 z-50 neo-card p-1 min-w-[200px] shadow-lg">
              {YOLO_MODES.map(mode => (
                <button
                  key={mode.value}
                  onClick={() => handleSelect(mode.value)}
                  className={`
                    w-full flex items-center gap-2 px-3 py-2 rounded text-left
                    hover:bg-[var(--color-neo-bg)]
                    ${mode.value === value ? 'bg-[var(--color-neo-bg)]' : ''}
                  `}
                >
                  <span className={mode.skipTesting ? 'text-yellow-600' : ''}>
                    {mode.icon}
                  </span>
                  <div className="flex-1">
                    <div className="font-bold text-sm">{mode.label}</div>
                    <div className="text-xs text-[var(--color-neo-text-secondary)]">
                      {mode.description}
                    </div>
                  </div>
                  {mode.value === value && (
                    <Check size={14} className="text-[var(--color-neo-done)]" />
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <label className="block font-bold text-sm">Agent Mode</label>
      <div className="grid gap-2">
        {YOLO_MODES.map(mode => (
          <button
            key={mode.value}
            onClick={() => !disabled && handleSelect(mode.value)}
            disabled={disabled}
            className={`
              neo-card p-3 text-left flex items-start gap-3
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-[var(--color-neo-accent)]'}
              ${mode.value === value ? 'border-[var(--color-neo-accent)] border-2' : ''}
              ${mode.skipTesting && mode.value === value ? 'bg-yellow-50' : ''}
            `}
          >
            <div className={`
              p-2 rounded-lg
              ${mode.skipTesting ? 'bg-yellow-100 text-yellow-600' : 'bg-gray-100'}
            `}>
              {mode.icon}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-bold">{mode.label}</span>
                {mode.skipTesting && (
                  <span className="neo-badge bg-yellow-500 text-white text-xs">
                    Skip Tests
                  </span>
                )}
                {mode.hasReview && (
                  <span className="neo-badge bg-blue-500 text-white text-xs">
                    +Review
                  </span>
                )}
                {mode.parallel && (
                  <span className="neo-badge bg-purple-500 text-white text-xs">
                    Parallel
                  </span>
                )}
              </div>
              <p className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
                {mode.description}
              </p>
            </div>
            {mode.value === value && (
              <Check size={20} className="text-[var(--color-neo-done)] flex-shrink-0" />
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
