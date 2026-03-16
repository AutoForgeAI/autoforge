import { type AgentMascot, type AgentState } from '../lib/types'
import {
  AVATAR_COLORS,
  UNKNOWN_COLORS,
  MASCOT_SVGS,
  UnknownMascotSVG,
} from './mascotData'

interface AgentAvatarProps {
  name: AgentMascot | 'Unknown' | 'Orchestrator'
  state: AgentState
  size?: 'sm' | 'md' | 'lg'
  showName?: boolean
}

const SIZES = {
  sm: { svg: 32, font: 'text-xs' },
  md: { svg: 48, font: 'text-sm' },
  lg: { svg: 64, font: 'text-base' },
}

// Animation classes based on state
function getStateAnimation(state: AgentState): string {
  switch (state) {
    case 'idle':
      return 'animate-bounce-gentle'
    case 'thinking':
      return 'animate-thinking'
    case 'working':
      return 'animate-working'
    case 'testing':
      return 'animate-testing'
    case 'success':
      return 'animate-celebrate'
    case 'error':
    case 'struggling':
      return 'animate-shake-gentle'
    case 'waiting_on_rate_limit':
      return 'animate-pulse-slow'
    default:
      return ''
  }
}

// Glow effect based on state
function getStateGlow(state: AgentState): string {
  switch (state) {
    case 'working':
      return 'shadow-[0_0_12px_rgba(0,180,216,0.5)]'
    case 'thinking':
      return 'shadow-[0_0_8px_rgba(255,214,10,0.4)]'
    case 'success':
      return 'shadow-[0_0_16px_rgba(112,224,0,0.6)]'
    case 'error':
    case 'struggling':
      return 'shadow-[0_0_12px_rgba(255,84,0,0.5)]'
    case 'waiting_on_rate_limit':
      return 'shadow-[0_0_8px_rgba(255,165,0,0.3)]'
    default:
      return ''
  }
}

// Get human-readable state description for accessibility
function getStateDescription(state: AgentState): string {
  switch (state) {
    case 'idle':
      return 'waiting'
    case 'thinking':
      return 'analyzing'
    case 'working':
      return 'coding'
    case 'testing':
      return 'running tests'
    case 'success':
      return 'completed successfully'
    case 'error':
      return 'encountered an error'
    case 'struggling':
      return 'having difficulty'
    case 'waiting_on_rate_limit':
      return 'waiting for usage limit to reset'
    default:
      return state
  }
}

export function AgentAvatar({ name, state, size = 'md', showName = false }: AgentAvatarProps) {
  // Handle 'Unknown' and 'Orchestrator' agents (special cases)
  const isUnknown = name === 'Unknown' || name === 'Orchestrator'
  const colors = isUnknown ? UNKNOWN_COLORS : AVATAR_COLORS[name]
  const { svg: svgSize, font } = SIZES[size]
  const SvgComponent = isUnknown ? UnknownMascotSVG : MASCOT_SVGS[name]
  const stateDesc = getStateDescription(state)
  const ariaLabel = `Agent ${name} is ${stateDesc}`

  return (
    <div
      className="flex flex-col items-center gap-1"
      role="status"
      aria-label={ariaLabel}
      aria-live="polite"
    >
      <div
        className={`
          rounded-full p-1 transition-all duration-300
          ${getStateAnimation(state)}
          ${getStateGlow(state)}
        `}
        style={{ backgroundColor: colors.accent }}
        title={ariaLabel}
        role="img"
        aria-hidden="true"
      >
        <SvgComponent colors={colors} size={svgSize} />
      </div>
      {showName && (
        <span className={`${font} font-bold text-foreground`} style={{ color: colors.primary }}>
          {name}
        </span>
      )}
    </div>
  )
}
