/** What Claude is doing, as the game shows it */
export type ClaudeStatus = 'busy' | 'idle' | 'needs_input'

/** Props the hooks module hands the game's Client */
export type GameProps = {
  claude: ClaudeStatus
  /** Epoch ms when Claude last started working; 0 when it never has */
  busySince: number
  best: number
}

/** What the game posts back to the hooks module */
export type GameMessage = { type: 'over'; score: number; streak: number }

declare module 'claude-code' {
  interface PluginState {
    shotclock: {
      status: ClaudeStatus
      busySince: number
      best: number
    }
  }
}
