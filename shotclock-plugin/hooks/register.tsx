import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { ClaudeStatus, GameMessage, GameProps } from '../types'

const PANE = 'shotclock'
const TITLE = 'Shot Clock'
const OPEN_AFTER_MS = 5000
const PANE_ROWS = 24
const BEST_KEY = 'best'

const status = atom({ plugin: 'shotclock', key: 'status' } as const, 'idle' as ClaudeStatus)
const busySince = atom({ plugin: 'shotclock', key: 'busySince' } as const, 0)
const best = atom({ plugin: 'shotclock', key: 'best' } as const, 0)

async function isEnabled($: EngineInterface) {
  const flag = (await $.env.get('SHOTCLOCK'))?.toLowerCase()
  return flag !== 'off' && flag !== '0'
}

async function setStatus($: EngineInterface, next: ClaudeStatus) {
  await update($, status, () => next)
}

export const register: Register = on => {
  // Cancels the pending "open after Claude has been busy a while" timer
  let cancelOpen: (() => void) | undefined

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'shotclock',
      description: 'Open Shot Clock, a basketball game to play while Claude works',
    })
    const saved = await $.store.get(BEST_KEY)
    if (typeof saved === 'number') await update($, best, () => saved)

    return next(e)
  })

  on('command.run', { command: 'shotclock' }, async $ => {
    const opened = await $.ui.open({ id: PANE, title: TITLE, rows: PANE_ROWS })
    if (!opened.isPlaced) return { text: `Shot Clock could not open: ${opened.reason}` }

    return { text: 'Shot Clock is open. Click the court to play; Esc goes back to the prompt.' }
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId) return next(e)

    await setStatus($, 'busy')
    await update($, busySince, () => Date.now())

    // Open the pane only once Claude has been working for a while, so quick
    // answers never pop it. Unasked, the engine places it on wide terminals only.
    cancelOpen?.()
    if (await isEnabled($)) {
      const timer = $.clock.after(OPEN_AFTER_MS, () => {
        void (async () => {
          if ((await read($, status)) === 'busy') {
            await $.ui.open({ id: PANE, title: TITLE, rows: PANE_ROWS })
          }
        })()
      })
      cancelOpen = () => timer.cancel()
    }

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId) return next(e)

    cancelOpen?.()
    cancelOpen = undefined
    await setStatus($, 'idle')

    return next(e)
  })

  // A permission prompt (or any question) while Claude works: the game pauses
  // so it never hides it
  on('classic.Notification', async ($, e, next) => {
    if ((await read($, status)) === 'busy') await setStatus($, 'needs_input')

    return next(e)
  })

  // A tool ran, so whatever Claude was waiting on was answered
  on('tool.call', async ($, e, next) => {
    const result = await next(e)
    if ((await read($, status)) === 'needs_input') await setStatus($, 'busy')

    return result
  })

  on('ui.message', { requestId: PANE }, async ($, e, next) => {
    const message = e.data as GameMessage
    if (message?.type !== 'over') return next(e)

    const previous = await read($, best)
    if (message.score > previous) {
      await update($, best, () => message.score)
      await $.store.set(BEST_KEY, message.score)
      $.ui.toast(`Shot Clock: new best, ${message.score} pts`)
    }

    return {}
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const elements = $.ui.resolve(e)
    if (!('Client' in elements)) {
      const { Text } = elements
      return <Text dimColor>Shot Clock plays in the terminal; this surface can't run it.</Text>
    }
    const { Box, Client } = elements

    const props: GameProps = {
      claude: await read($, status),
      busySince: await read($, busySince),
      best: await read($, best),
    }

    return (
      <Box flexDirection="column">
        <Client
          key="game"
          module="./game.tsx"
          props={props}
          width={e.props.bodyColumns}
          height={Math.max(12, e.props.scroll.bodyRows)}
        />
      </Box>
    )
  })
}
