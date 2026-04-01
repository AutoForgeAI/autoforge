/**
 * Browsers View
 *
 * Full-page live browser screenshots from each agent's browser session.
 * BrowserViewPanel handles subscribe/unsubscribe internally via useEffect.
 */

import { useAppContext } from '@/contexts/AppContext'
import { BrowserViewPanel } from '../BrowserViewPanel'

export function BrowsersView() {
  const { wsState } = useAppContext()

  return (
    <div className="flex-1 overflow-hidden">
      <BrowserViewPanel
        screenshots={wsState.browserScreenshots}
        onSubscribe={wsState.subscribeBrowserView}
        onUnsubscribe={wsState.unsubscribeBrowserView}
      />
    </div>
  )
}
