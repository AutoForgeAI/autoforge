import { useAppContext } from '@/contexts/AppContext'
import { AddFeatureForm } from '../AddFeatureForm'
import { FeatureModal } from '../FeatureModal'
import { ExpandProjectModal } from '../ExpandProjectModal'
import { SpecCreationChat } from '../SpecCreationChat'
import { KeyboardShortcutsHelp } from '../KeyboardShortcutsHelp'
import { ResetProjectModal } from '../ResetProjectModal'
import { AssistantFAB } from '../AssistantFAB'
import { AssistantPanel } from '../AssistantPanel'
import { CelebrationOverlay } from '../CelebrationOverlay'
import { startAgent } from '@/lib/api'

/**
 * Renders all modal dialogs, overlays, and floating UI elements.
 *
 * Extracted from App.tsx so the main shell remains focused on layout while
 * this component owns the conditional rendering of every overlay surface.
 * All state is read from AppContext -- no props required.
 */
export function Modals() {
  const {
    selectedProject,
    selectedFeature, setSelectedFeature,
    showAddFeature, setShowAddFeature,
    showExpandProject, setShowExpandProject,
    showSpecChat, setShowSpecChat,
    showKeyboardHelp, setShowKeyboardHelp,
    showResetModal, setShowResetModal,
    assistantOpen, setAssistantOpen,
    isSpecCreating,
    hasSpec,
    specInitializerStatus, setSpecInitializerStatus,
    specInitializerError, setSpecInitializerError,
    wsState,
    queryClient,
  } = useAppContext()

  return (
    <>
      {/* Add Feature Modal */}
      {showAddFeature && selectedProject && (
        <AddFeatureForm
          projectName={selectedProject}
          onClose={() => setShowAddFeature(false)}
        />
      )}

      {/* Feature Detail Modal */}
      {selectedFeature && selectedProject && (
        <FeatureModal
          feature={selectedFeature}
          projectName={selectedProject}
          onClose={() => setSelectedFeature(null)}
        />
      )}

      {/* Expand Project Modal */}
      {showExpandProject && selectedProject && hasSpec && (
        <ExpandProjectModal
          isOpen={showExpandProject}
          projectName={selectedProject}
          onClose={() => setShowExpandProject(false)}
          onFeaturesAdded={() => {
            queryClient.invalidateQueries({ queryKey: ['features', selectedProject] })
          }}
        />
      )}

      {/* Spec Creation Chat - full screen overlay */}
      {showSpecChat && selectedProject && (
        <div className="fixed inset-0 z-50 bg-background">
          <SpecCreationChat
            projectName={selectedProject}
            onComplete={async (_specPath, yoloMode) => {
              setSpecInitializerStatus('starting')
              try {
                await startAgent(selectedProject, {
                  yoloMode: yoloMode ?? false,
                  maxConcurrency: 3,
                })
                setShowSpecChat(false)
                setSpecInitializerStatus('idle')
                queryClient.invalidateQueries({ queryKey: ['projects'] })
                queryClient.invalidateQueries({ queryKey: ['features', selectedProject] })
              } catch (err) {
                setSpecInitializerStatus('error')
                setSpecInitializerError(err instanceof Error ? err.message : 'Failed to start agent')
              }
            }}
            onCancel={() => { setShowSpecChat(false); setSpecInitializerStatus('idle') }}
            onExitToProject={() => { setShowSpecChat(false); setSpecInitializerStatus('idle') }}
            initializerStatus={specInitializerStatus}
            initializerError={specInitializerError}
            onRetryInitializer={() => {
              setSpecInitializerError(null)
              setSpecInitializerStatus('idle')
            }}
          />
        </div>
      )}

      {/* Assistant FAB and Panel - hide when expand modal or spec creation is open */}
      {selectedProject && !showExpandProject && !isSpecCreating && !showSpecChat && (
        <>
          <AssistantFAB
            onClick={() => setAssistantOpen(!assistantOpen)}
            isOpen={assistantOpen}
          />
          <AssistantPanel
            projectName={selectedProject}
            isOpen={assistantOpen}
            onClose={() => setAssistantOpen(false)}
          />
        </>
      )}

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsHelp isOpen={showKeyboardHelp} onClose={() => setShowKeyboardHelp(false)} />

      {/* Reset Project Modal */}
      {showResetModal && selectedProject && (
        <ResetProjectModal
          isOpen={showResetModal}
          projectName={selectedProject}
          onClose={() => setShowResetModal(false)}
          onResetComplete={(wasFullReset) => {
            if (wasFullReset) {
              setShowSpecChat(true)
            }
          }}
        />
      )}

      {/* Celebration Overlay - shows when a feature is completed by an agent */}
      {wsState.celebration && (
        <CelebrationOverlay
          agentName={wsState.celebration.agentName}
          featureName={wsState.celebration.featureName}
          onComplete={wsState.clearCelebration}
        />
      )}
    </>
  )
}
