import type { ClientKeyEvent, ClientModule, ClientSurface } from 'claude-code'

import type { ClaudeStatus, GameMessage, GameProps } from '../types'

// Timing
const TICK_MS = 33
const ANIM_RATE = 30 // Animation counters are in 1/30 s steps
const FLIGHT_TIME = 1.2 // Seconds from release until the ball drops onto its target line

// Rules
const MAX_LIVES = 5
const POINTS = 2
const DEFENDER_AT = 50
const SPEED_UP_AT = 75
const DEPTH_AT = 100
const BOMB_AT = 150
const BOMB_CHANCE = 0.25
const HEATING_UP = 3
const ON_FIRE = 5

// Hoop geometry, in columns from the rim's centre
const SWISH_HALF = 0.6
const RIM_HALF = 2.0
const RIM_EDGE = 3.5

// Columns per second
const HOOP_SPEED = 5
const DEFENDER_SPEED = 4

const MIN_W = 30
const MIN_H = 12

const BALL = '🏀'
const BOMB = '💣'

const MILESTONES: [number, string][] = [
  [500, '👑 LEGENDARY'],
  [300, '👑 CHAMPION'],
  [200, '🔥 ON FIRE'],
  [150, '🥅 BOMB SQUAD'],
  [100, '🥈 3D MASTER'],
  [50, '🥉 DEFENDER BEAT'],
]

// ------------------------------------------------------------------- styles

type TextStyle = { color?: string; bold?: boolean; inverse?: boolean }

const STYLES = {
  plain: {},
  label: { color: '#8a8a8a' },
  value: { bold: true },
  title: { color: '#ff8c1a', bold: true, inverse: true },
  rim: { color: '#ff8c1a', bold: true },
  net: { color: '#e6e6e6' },
  board: { color: '#9a9a9a' },
  player: { color: '#ffffff', bold: true },
  defender: { color: '#ff4d4d', bold: true },
  trash: { color: '#ffd23f', bold: true },
  trashBlink: { color: '#ffd23f', bold: true, inverse: true },
  preview: { color: '#4fd1e8', bold: true },
  good: { color: '#3ddc84', bold: true },
  bad: { color: '#ff4d4d', bold: true },
  warn: { color: '#ffd23f', bold: true },
  dim: { color: '#6b6b6b' },
  trail: { color: '#b86a1f' },
  fire: { color: '#ff6a00', bold: true },
  panel: { color: '#ff8c1a' },
  busy: { color: '#4fd1e8', bold: true },
} satisfies Record<string, TextStyle>

type Style = keyof typeof STYLES

// ------------------------------------------------------------------- grid

const TAIL = '\u0000' // Second cell of a wide (emoji) character

function isWide(c: string | undefined) {
  return (c?.codePointAt(0) ?? 0) >= 0x1f300
}

/** A screen of cells the game draws into, then turns into Text rows */
class Grid {
  ch: string[][]
  st: Style[][]
  shakeDx = 0
  shakeTop = 0
  shakeBottom = 0

  readonly w: number
  readonly h: number

  constructor(cols: number, rows: number) {
    this.w = cols
    this.h = rows
    this.ch = Array.from({ length: rows }, () => Array<string>(cols).fill(' '))
    this.st = Array.from({ length: rows }, () => Array<Style>(cols).fill('plain'))
  }

  private clear(y: number, x: number) {
    const row = this.ch[y]!
    if (row[x] === TAIL && x > 0) row[x - 1] = ' '
    if (isWide(row[x]) && x + 1 < this.w) row[x + 1] = ' '
    row[x] = ' '
  }

  put(y: number, x: number, text: string, st: Style = 'plain') {
    y = Math.round(y)
    x = Math.round(x)
    if (y < 0 || y >= this.h || !text) return
    if (this.shakeDx && y >= this.shakeTop && y <= this.shakeBottom) x += this.shakeDx
    const chRow = this.ch[y]!
    const stRow = this.st[y]!
    for (const c of Array.from(text)) {
      const wide = isWide(c)
      if (x >= 0 && x + (wide ? 1 : 0) < this.w) {
        this.clear(y, x)
        if (wide) this.clear(y, x + 1)
        chRow[x] = c
        stRow[x] = st
        if (wide) {
          chRow[x + 1] = TAIL
          stRow[x + 1] = st
        }
      }
      x += wide ? 2 : 1
    }
  }
}

// Braille dot bits by [sub-row][sub-column]; each cell holds 2 x 4 dots
const BRAILLE_BITS = [
  [0x01, 0x08],
  [0x02, 0x10],
  [0x04, 0x20],
  [0x40, 0x80],
]

/** Plot (x, y) points, in cell units, as braille characters keyed by "row,col" */
function brailleCells(points: [number, number][]) {
  const bits = new Map<string, number>()
  for (const [x, y] of points) {
    const sx = Math.floor((x + 0.5) * 2)
    const sy = Math.floor((y + 0.5) * 4)
    const key = `${Math.floor(sy / 4)},${Math.floor(sx / 2)}`
    bits.set(key, (bits.get(key) ?? 0) | BRAILLE_BITS[((sy % 4) + 4) % 4]![((sx % 2) + 2) % 2]!)
  }
  return [...bits].map(([key, b]) => {
    const [row = 0, col = 0] = key.split(',').map(Number)
    return { row, col, char: String.fromCharCode(0x2800 + b) }
  })
}

function displayWidth(text: string) {
  return Array.from(text).reduce((n, c) => n + (isWide(c) ? 2 : 1), 0)
}

// ------------------------------------------------------------------- state

type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  text: string
  st: Style
  gravity: number
}

type Ball = {
  x: number
  y: number
  vx: number
  vy: number
  g: number
  isBomb: boolean
  inFlight: boolean
  live: boolean
  sinking: boolean
  trail: [number, number][]
}

type PauseReason = 'pause' | 'bomb' | 'claude_done' | 'claude_needs'
type CrowdMood = 'idle' | 'cheer' | 'groan' | 'wave'

type Game = {
  w: number
  h: number
  top: number
  floor: number
  left: number
  right: number
  playerX: number
  releaseY: number
  arcHeight: number
  rimY: number
  defenderY: number
  trashY: number

  state: 'splash' | 'playing' | 'paused' | 'over'
  pauseReason: PauseReason
  claude: ClaudeStatus
  busySince: number

  score: number
  lives: number
  streak: number
  bestStreak: number
  baskets: number
  best: number
  newBest: boolean

  ball: Ball
  hoop: { x: number; vx: number }
  defender: { x: number; vx: number }
  trash: { x: number; active: boolean }
  aimDx: number
  aimDistance: number
  shownBombTutorial: boolean

  hoopShake: number
  netFlash: number
  defenderFlash: number
  feedback: { text: string; st: Style; frames: number }
  explosion: { x: number; y: number; frames: number } | null
  particles: Particle[]
  popups: Particle[]
  crowd: { mood: CrowdMood; time: number; elapsed: number }
  screenShake: number
  shakeDx: number

  tick: number
  lastTime: number
  post: (message: GameMessage) => void
}

function newGame(props: GameProps, post: (message: GameMessage) => void): Game {
  return {
    w: 0,
    h: 0,
    top: 2,
    floor: 0,
    left: 0,
    right: 0,
    playerX: 0,
    releaseY: 0,
    arcHeight: 2,
    rimY: 0,
    defenderY: 0,
    trashY: 0,
    state: 'splash',
    pauseReason: 'pause',
    claude: props.claude,
    busySince: props.busySince,
    score: 0,
    lives: MAX_LIVES,
    streak: 0,
    bestStreak: 0,
    baskets: 0,
    best: props.best,
    newBest: false,
    ball: emptyBall(),
    hoop: { x: -1, vx: HOOP_SPEED },
    defender: { x: -1, vx: DEFENDER_SPEED },
    trash: { x: 0, active: false },
    aimDx: 0,
    aimDistance: 5,
    shownBombTutorial: false,
    hoopShake: 0,
    netFlash: 0,
    defenderFlash: 0,
    feedback: { text: '', st: 'good', frames: 0 },
    explosion: null,
    particles: [],
    popups: [],
    crowd: { mood: 'idle', time: 0, elapsed: 0 },
    screenShake: 0,
    shakeDx: 0,
    tick: 0,
    lastTime: Date.now(),
    post,
  }
}

function emptyBall(): Ball {
  return { x: 0, y: 0, vx: 0, vy: 0, g: 0, isBomb: false, inFlight: false, live: false, sinking: false, trail: [] }
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)
const pick = <T,>(items: readonly T[]) => items[Math.floor(Math.random() * items.length)]!
const rand = (lo: number, hi: number) => lo + Math.random() * (hi - lo)

// ------------------------------------------------------------------- layout

function hoopBounds(g: Game): [number, number] {
  return [g.left + 5, g.right - 5]
}
function defenderBounds(g: Game): [number, number] {
  return [g.left + 2, g.right - 3]
}
function trashBounds(g: Game): [number, number] {
  const lo = g.left + 1
  return [lo, Math.max(lo, Math.floor(g.w * 0.25) - 4)]
}

/** Row 0 is the HUD, row 1 the crowd, the court runs to h-2, row h-1 is the bar */
function layout(g: Game, cols: number, rows: number) {
  const w = cols
  g.w = cols
  g.h = rows
  g.top = 2
  g.floor = rows - 2
  g.left = 0
  g.right = w - 1
  g.playerX = Math.floor(w / 2)
  g.releaseY = g.floor - 2
  g.arcHeight = Math.max(2, Math.round((g.floor - g.top) * 0.12))
  g.rimY = g.top + g.arcHeight + 1
  const span = g.releaseY - g.rimY
  g.defenderY = g.rimY + Math.max(3, Math.round(span * 0.45))
  g.trashY = g.rimY + Math.max(4, Math.round(span * 0.75))

  if (g.hoop.x < 0) g.hoop.x = w / 2
  if (g.defender.x < 0) g.defender.x = w / 2 - 1
  g.hoop.x = clamp(g.hoop.x, ...hoopBounds(g))
  g.defender.x = clamp(g.defender.x, ...defenderBounds(g))
  g.trash.x = clamp(g.trash.x, ...trashBounds(g))
  clampAim(g)
}

function clampAim(g: Game) {
  g.aimDx = clamp(g.aimDx, g.left + 1 - g.playerX, g.right - 1 - g.playerX)
}

// ------------------------------------------------------------------- physics

const targetY = (g: Game) => (g.ball.isBomb ? g.trashY : g.rimY)
const targetX = (g: Game) => g.playerX + g.aimDx
const defenderActive = (g: Game) => g.score >= DEFENDER_AT
const onFire = (g: Game) => g.streak >= ON_FIRE
const speedSteps = (g: Game) => Math.max(0, Math.floor((g.score - DEPTH_AT) / 25))

/** Velocity that peaks arcHeight rows above ty and drops onto it after FLIGHT_TIME */
function launchVelocity(g: Game, tx: number, ty: number) {
  const rise = g.releaseY - (ty - g.arcHeight)
  const drop = g.arcHeight
  const gravity = (2 * (Math.sqrt(rise) + Math.sqrt(drop)) ** 2) / FLIGHT_TIME ** 2
  return { vx: (tx - g.playerX) / FLIGHT_TIME, vy: -Math.sqrt(2 * gravity * rise), gravity }
}

function aimAngle(g: Game) {
  const { vx, vy } = launchVelocity(g, targetX(g), targetY(g))
  return Math.round((Math.atan2(-vy * 2, vx) * 180) / Math.PI) // Rows are about twice as tall as columns
}

function crossed(prevY: number, y: number, row: number) {
  return (prevY > row && row >= y) || (prevY < row && row <= y)
}

function xAtRow(px: number, py: number, x: number, y: number, row: number) {
  return y === py ? x : px + ((x - px) * (row - py)) / (y - py)
}

function loadNextBall(g: Game) {
  g.ball.inFlight = false
  g.ball.isBomb = g.score >= BOMB_AT && Math.random() < BOMB_CHANCE
  g.trash.active = g.ball.isBomb
  if (g.ball.isBomb) {
    const [lo, hi] = trashBounds(g)
    g.trash.x = lo + Math.floor(Math.random() * (hi - lo + 1))
    if (!g.shownBombTutorial && g.state === 'playing') {
      g.shownBombTutorial = true
      g.pauseReason = 'bomb'
      g.state = 'paused'
    }
  }
}

function shoot(g: Game) {
  const b = g.ball
  if (b.inFlight) return
  const { vx, vy, gravity } = launchVelocity(g, targetX(g), targetY(g))
  Object.assign(b, { vx, vy, g: gravity, x: g.playerX, y: g.releaseY, inFlight: true, live: true, sinking: false, trail: [] })
}

function flash(g: Game, text: string, st: Style, frames = 36) {
  g.feedback = { text, st, frames }
}

function scoreBasket(g: Game, text: string, x: number, y: number) {
  g.score += POINTS
  g.streak += 1
  g.bestStreak = Math.max(g.bestStreak, g.streak)
  g.baskets += 1
  flash(g, text, 'good')
  popup(g, x, y - 1, `+${POINTS}`, 'good')

  if (g.streak === HEATING_UP) {
    announce(g, 'HEATING UP!', 'warn')
    setCrowd(g, 'cheer', 1.5)
  } else if (g.streak === ON_FIRE) {
    announce(g, "YOU'RE ON FIRE!", 'bad')
    setCrowd(g, 'wave', 3)
  } else if (g.streak > ON_FIRE && g.streak % 5 === 0) {
    announce(g, `UNSTOPPABLE x${g.streak}`, 'bad')
    setCrowd(g, 'wave', 3)
  } else {
    setCrowd(g, 'cheer', 1.2)
  }
}

function loseLives(g: Game, count: number, text: string) {
  g.lives = Math.max(0, g.lives - count)
  g.streak = 0
  flash(g, text, 'bad')
  if (g.lives === 0) gameOver(g)
  else setCrowd(g, 'groan', 0.9)
}

function gameOver(g: Game) {
  g.state = 'over'
  g.newBest = g.score > g.best
  g.best = Math.max(g.best, g.score)
  g.post({ type: 'over', score: g.score, streak: g.bestStreak })
}

function resetGame(g: Game) {
  Object.assign(g, {
    score: 0,
    lives: MAX_LIVES,
    streak: 0,
    newBest: false,
    explosion: null,
    particles: [],
    popups: [],
    screenShake: 0,
    state: 'playing',
  })
  g.feedback.frames = 0
  loadNextBall(g)
}

function endFlight(g: Game) {
  if (g.state === 'over') g.ball.inFlight = false
  else loadNextBall(g)
}

function updateBall(g: Game, dt: number) {
  const b = g.ball
  if (!b.inFlight) return

  b.trail.push([b.x, b.y])
  if (b.trail.length > 8) b.trail.shift()
  const px = b.x
  const py = b.y
  b.x += b.vx * dt
  b.y += b.vy * dt + 0.5 * b.g * dt * dt
  b.vy += b.g * dt

  if (b.sinking) {
    b.x = g.hoop.x // Ride down through the net, then disappear
    if (b.y >= g.rimY + 2.5) loadNextBall(g)
    return
  }

  if (b.live && b.isBomb) {
    // The trash can's line is the fuse
    if (b.vy > 0 && crossed(py, b.y, g.trashY)) {
      const cx = xAtRow(px, py, b.x, b.y, g.trashY)
      if (Math.abs(cx - (g.trash.x + 1.5)) <= 2) {
        scoreBasket(g, 'IN THE CAN!', g.trash.x + 1.5, g.trashY)
        burst(g, g.trash.x + 1.5, g.trashY - 1, 8, '·•°', ['trash', 'dim'], 5, 4)
      } else {
        g.explosion = { x: cx, y: g.trashY, frames: 18 }
        g.screenShake = 0.45
        burst(g, cx, g.trashY, 26, '*#%@·', ['bad', 'warn', 'rim'], 18, 10, 1.1)
        loseLives(g, 2, 'BOOM! -2 LIVES')
      }
      endFlight(g)
      return
    }
  } else if (b.live) {
    if (defenderActive(g) && crossed(py, b.y, g.defenderY)) {
      const cx = xAtRow(px, py, b.x, b.y, g.defenderY)
      if (g.defender.x - 1 <= cx && cx <= g.defender.x + 2) {
        b.live = false
        b.vx *= -0.3
        b.vy = Math.abs(b.vy) * 0.3
        g.defenderFlash = 12
        loseLives(g, 1, 'BLOCKED!')
      }
    }

    if (b.live && b.vy > 0 && crossed(py, b.y, g.rimY)) {
      const dx = xAtRow(px, py, b.x, b.y, g.rimY) - g.hoop.x
      const spark = () => burst(g, g.hoop.x + dx, g.rimY, 6, "'`,", ['warn'], 6, 3, 0.4)
      if (Math.abs(dx) <= SWISH_HALF) {
        b.live = false
        b.sinking = true
        g.netFlash = 12
        scoreBasket(g, 'SWISH!', g.hoop.x, g.rimY)
        burst(g, g.hoop.x, g.rimY - 1, 22, '*+•·✦', ['good', 'warn', 'rim', 'preview'], 12, 8, 1.2)
      } else if (Math.abs(dx) <= RIM_HALF) {
        b.live = false
        b.sinking = true
        g.hoopShake = 8
        scoreBasket(g, 'CLANK! ...IN', g.hoop.x, g.rimY)
        spark()
      } else if (Math.abs(dx) <= RIM_EDGE) {
        b.live = false
        b.vx = Math.sign(dx) * 10
        b.vy = -Math.abs(b.vy) * 0.35
        g.hoopShake = 8
        spark()
        loseLives(g, 1, 'OFF THE RIM')
      } else {
        b.live = false
        loseLives(g, 1, 'AIRBALL')
      }
    }
  }

  if (b.y > g.floor || b.x < g.left || b.x > g.right) {
    if (b.live) loseLives(g, 1, 'AIRBALL')
    endFlight(g)
  }
}

function moveBouncing(obj: { x: number; vx: number }, speed: number, [lo, hi]: [number, number], dt: number) {
  obj.vx = Math.sign(obj.vx || 1) * speed
  obj.x += obj.vx * dt
  if (obj.x <= lo) {
    obj.x = lo
    obj.vx = Math.abs(obj.vx)
  } else if (obj.x >= hi) {
    obj.x = hi
    obj.vx = -Math.abs(obj.vx)
  }
}

function updateMovers(g: Game, dt: number) {
  const bump = 1 + 0.1 * speedSteps(g)
  moveBouncing(g.hoop, HOOP_SPEED * (g.score >= SPEED_UP_AT ? 1.5 : 1) * bump, hoopBounds(g), dt)
  if (defenderActive(g)) moveBouncing(g.defender, DEFENDER_SPEED * bump, defenderBounds(g), dt)
}

// ------------------------------------------------------------------- effects

function burst(
  g: Game,
  x: number,
  y: number,
  count: number,
  chars: string,
  styles: Style[],
  speed = 10,
  up = 8,
  life = 0.9,
  gravity = 25,
) {
  const glyphs = Array.from(chars)
  for (let i = 0; i < count; i++) {
    const angle = rand(0, Math.PI)
    const v = rand(0.4, 1) * speed
    g.particles.push({
      x,
      y,
      vx: Math.cos(angle) * v * 1.6,
      vy: -Math.sin(angle) * v * 0.8 - up * Math.random(),
      life: rand(0.5, 1) * life,
      text: pick(glyphs),
      st: pick(styles),
      gravity,
    })
  }
}

function popup(g: Game, x: number, y: number, text: string, st: Style, life = 0.9) {
  g.popups.push({ x, y, vx: 0, vy: -4, life, text, st, gravity: 0 })
}

function announce(g: Game, text: string, st: Style) {
  const y = Math.floor((g.rimY + g.defenderY) / 2) + 1
  g.popups.push({ x: g.w / 2, y, vx: 0, vy: -1.5, life: 1.8, text, st, gravity: 0 })
}

function setCrowd(g: Game, mood: CrowdMood, seconds: number) {
  if (g.crowd.mood === 'wave' && g.crowd.time > 0 && mood !== 'wave') return // Let the wave finish
  g.crowd = { mood, time: seconds, elapsed: 0 }
}

function updateEffects(g: Game, dt: number) {
  for (const p of [...g.particles, ...g.popups]) {
    p.x += p.vx * dt
    p.y += p.vy * dt
    p.vy += p.gravity * dt
    p.life -= dt
  }
  g.particles = g.particles.filter(p => p.life > 0 && p.y < g.floor + 1)
  g.popups = g.popups.filter(p => p.life > 0)

  g.crowd.time -= dt
  g.crowd.elapsed += dt
  if (g.crowd.time <= 0) g.crowd.mood = 'idle'

  g.screenShake = Math.max(0, g.screenShake - dt)
  g.shakeDx = g.screenShake > 0 ? pick([-1, 1]) : 0

  // Flames off a ball that's on fire
  const b = g.ball
  if (onFire(g) && b.inFlight && !b.isBomb && g.particles.length < 80) {
    for (let i = 0; i < 2; i++) {
      g.particles.push({
        x: b.x + rand(-0.6, 0.6),
        y: b.y,
        vx: rand(-2, 2),
        vy: rand(-4, -1),
        life: rand(0.15, 0.35),
        text: pick(["^", '*', "'", '`']),
        st: pick<Style>(['bad', 'warn', 'fire']),
        gravity: -4,
      })
    }
  }
}

function tickAnimations(g: Game, dt: number) {
  const step = dt * ANIM_RATE
  g.hoopShake = Math.max(0, g.hoopShake - step)
  g.netFlash = Math.max(0, g.netFlash - step)
  g.defenderFlash = Math.max(0, g.defenderFlash - step)
  g.feedback.frames = Math.max(0, g.feedback.frames - step)
  if (g.explosion) {
    g.explosion.frames -= step
    if (g.explosion.frames <= 0) g.explosion = null
  }
}

function step(g: Game, now: number) {
  const dt = Math.min((now - g.lastTime) / 1000, 0.1) // No big jumps after a stall
  g.lastTime = now
  if (g.w < MIN_W || g.h < MIN_H) return

  if (g.state === 'playing') {
    updateBall(g, dt)
    updateMovers(g, dt)
    tickAnimations(g, dt)
    updateEffects(g, dt)
  } else if (g.state === 'over') {
    tickAnimations(g, dt)
    updateEffects(g, dt)
  }
  g.tick += dt * ANIM_RATE
}

// ------------------------------------------------------------------- input

function handleKey(g: Game, { key, shift }: ClientKeyEvent) {
  if (g.state === 'splash') {
    g.state = 'playing'
    return
  }
  if (g.state === 'over') {
    if (key === 'r' || key === ' ' || key === 'space' || key === 'return') resetGame(g)
    return
  }
  if (g.state === 'paused') {
    if (g.pauseReason !== 'pause' || key === 'p') g.state = 'playing'
    return
  }

  const stepSize = shift ? 3 : 1
  if (key === 'left') g.aimDx -= stepSize
  else if (key === 'right') g.aimDx += stepSize
  else if (key === 'up' && g.score >= DEPTH_AT && !g.ball.isBomb) g.aimDistance = Math.min(9, g.aimDistance + 1)
  else if (key === 'down' && g.score >= DEPTH_AT && !g.ball.isBomb) g.aimDistance = Math.max(0, g.aimDistance - 1)
  else if (key === ' ' || key === 'space' || key === 'return') shoot(g)
  else if (key === 'p') {
    g.pauseReason = 'pause'
    g.state = 'paused'
  } else if (key === 'r') resetGame(g)
  clampAim(g)
}

/** Pause when Claude finishes or needs the person; resume when it works again */
function syncClaude(g: Game, props: GameProps) {
  g.best = Math.max(g.best, props.best)
  g.busySince = props.busySince
  if (props.claude === g.claude) return

  const was = g.claude
  g.claude = props.claude
  if (props.claude === 'busy') {
    if (g.state === 'paused' && g.pauseReason.startsWith('claude')) g.state = 'playing'
  } else if (was === 'busy' && g.state === 'playing') {
    g.state = 'paused'
    g.pauseReason = props.claude === 'idle' ? 'claude_done' : 'claude_needs'
  }
}

// ------------------------------------------------------------------- drawing

function drawCourt(g: Game, grid: Grid) {
  drawCrowd(g, grid)
  const aiming = g.state === 'playing' && !g.ball.inFlight
  if (aiming) drawPreview(g, grid)
  if (g.trash.active) {
    const blink = !g.ball.inFlight && Math.floor(g.tick) % 20 < 10
    grid.put(g.trashY, g.trash.x, '[▄▄]', blink ? 'trashBlink' : 'trash')
  }
  if (defenderActive(g)) {
    grid.put(g.defenderY, Math.round(g.defender.x) - 1, g.defenderFlash > 0 ? '╲░░╱' : '╲██╱', 'defender')
  }
  drawHoop(g, grid)
  if (aiming) grid.put(targetY(g), targetX(g), '×', 'warn')
  drawPlayer(g, grid)
  if (g.ball.inFlight) drawBall(g, grid)
  if (g.explosion) drawExplosion(g, grid)
  for (const p of g.particles) grid.put(p.y, p.x, p.text, p.st)
  for (const p of g.popups) grid.put(p.y, Math.round(p.x) - Math.floor(displayWidth(p.text) / 2), p.text, p.st)
}

function drawCrowd(g: Game, grid: Grid) {
  const { mood, elapsed } = g.crowd
  const waveAt = (elapsed * 45) / 4 // Seat index the wave has reached
  let i = 0
  for (let x = g.left + 2; x < g.right - 3; x += 4, i++) {
    const seed = (i * 7919 + 3) % 17
    if (seed % 6 === 0) continue // Empty seat
    const up =
      mood === 'cheer'
        ? Math.floor(g.tick / 3 + seed) % 2 === 0
        : mood === 'wave'
          ? Math.abs(i - waveAt) < 1.5 || Math.abs(i - (waveAt - 12)) < 1.5
          : false
    if (up) grid.put(1, x, '╲o╱', seed % 2 ? 'warn' : 'rim')
    else grid.put(1, x, mood === 'groan' ? '╭o╮' : ' o ', 'dim')
  }
}

function drawPreview(g: Game, grid: Grid) {
  const { vx, vy, gravity } = launchVelocity(g, targetX(g), targetY(g))
  const points: [number, number][] = []
  for (let i = 0; i <= 400; i++) {
    const t = (FLIGHT_TIME * i) / 400
    const y = g.releaseY + vy * t + 0.5 * gravity * t * t
    if (y > g.releaseY - 1) continue // Keep the start of the arc off the ball in hand
    points.push([g.playerX + vx * t, y])
  }
  for (const { row, col, char } of brailleCells(points)) {
    if (row >= g.top) grid.put(row, col, char, 'preview')
  }
}

function drawHoop(g: Game, grid: Grid) {
  const cx = Math.round(g.hoop.x)
  const r = g.rimY
  const shake = g.hoopShake > 0 ? pick([-1, 1]) : 0
  const net: Style = g.netFlash > 0 ? 'good' : 'net'
  grid.put(r - 1, cx - 4, '▄▄▄▄▄▄▄▄▄', 'board')
  grid.put(r, cx - 3 + shake, 'o━━━━━o', 'rim')
  grid.put(r + 1, cx - 2, '╲│││╱', net)
  grid.put(r + 2, cx - 1, '╲│╱', net)
}

/** The emoji is two cells wide; this puts its centre on x */
function putBall(grid: Grid, x: number, y: number, isBomb: boolean) {
  grid.put(y, Math.round(x - 0.5), isBomb ? BOMB : BALL)
}

function drawPlayer(g: Game, grid: Grid) {
  const x = g.playerX
  grid.put(g.floor - 1, x - 1, '╲O╱', 'player')
  grid.put(g.floor, x - 1, '╱ ╲', 'player')
  if (!g.ball.inFlight && g.state !== 'over') putBall(grid, x, g.releaseY, g.ball.isBomb)
}

function drawBall(g: Game, grid: Grid) {
  const b = g.ball
  // Trail: a fine line through recent positions, stopping short of the ball
  const path = [...b.trail, [b.x, b.y] as [number, number]]
  const points: [number, number][] = []
  for (let i = 0; i + 1 < path.length; i++) {
    const [x0, y0] = path[i]!
    const [x1, y1] = path[i + 1]!
    for (let k = 0; k < 8; k++) points.push([x0 + ((x1 - x0) * k) / 8, y0 + ((y1 - y0) * k) / 8])
  }
  const row = Math.round(b.y)
  const col = Math.round(b.x - 0.5)
  for (const cell of brailleCells(points)) {
    if (cell.row === row && (cell.col === col || cell.col === col + 1)) continue
    grid.put(cell.row, cell.col, cell.char, onFire(g) ? 'fire' : 'trail')
  }
  putBall(grid, b.x, b.y, b.isBomb)
  if (b.isBomb) grid.put(row - 1, col + 2, Math.floor(g.tick) % 4 < 2 ? '*' : "'", 'warn')
}

function drawExplosion(g: Game, grid: Grid) {
  if (!g.explosion) return
  const { x, y, frames } = g.explosion
  const st: Style = Math.floor(frames) % 4 < 2 ? 'bad' : 'warn'
  const art = frames > 6 ? [' ╲ │ ╱ ', '── ✷ ──', ' ╱ │ ╲ '] : ['  · ', ' ·✷· ', '  · ']
  art.forEach((line, i) => grid.put(y - 1 + i, Math.round(x) - Math.floor(line.length / 2), line, st))
}

function drawHud(g: Game, grid: Grid) {
  const segments: [string, Style][] = []
  segments.push(g.w >= 56 ? [' SHOT CLOCK ', 'title'] : ['', 'plain'], [' ', 'plain'])
  segments.push(['SCORE ', 'label'], [String(g.score).padStart(3, '0'), 'value'], ['  ', 'plain'])
  segments.push(['●'.repeat(g.lives), 'bad'], ['○'.repeat(MAX_LIVES - g.lives), 'dim'])
  if (onFire(g)) segments.push(['  ', 'plain'], [`ON FIRE x${g.streak}`, Math.floor(g.tick / 4) % 2 ? 'bad' : 'warn'])
  else if (g.streak >= 2) segments.push(['  ', 'plain'], [`STREAK x${g.streak}`, 'warn'])

  let x = 0
  for (const [text, st] of segments) {
    grid.put(0, x, text, st)
    x += displayWidth(text)
  }
  const best = String(Math.max(g.best, g.score)).padStart(3, '0')
  if (x + best.length + 7 < g.w) {
    grid.put(0, g.w - best.length - 6, 'BEST ', 'label')
    grid.put(0, g.w - best.length - 1, best, 'value')
  }

  // Shot feedback over the middle of the crowd row
  if (g.feedback.frames > 0 && g.state !== 'over') {
    const label = ` ${g.feedback.text} `
    grid.put(1, Math.floor((g.w - label.length) / 2), label, g.feedback.st)
  }
}

function formatElapsed(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function drawBar(g: Game, grid: Grid) {
  const y = g.h - 1
  let text: string
  let st: Style
  if (g.claude === 'busy') {
    const dots = '.'.repeat(1 + (Math.floor(g.tick / 10) % 3))
    text = `● Claude is working ${g.busySince ? formatElapsed(Date.now() - g.busySince) : ''}${dots}`
    st = 'busy'
  } else if (g.claude === 'needs_input') {
    text = '! Claude needs you: press Esc'
    st = Math.floor(g.tick / 6) % 2 ? 'bad' : 'warn'
  } else {
    text = '✓ Claude is idle'
    st = 'good'
  }
  grid.put(y, 1, text, st)
  let x = 1 + text.length + 2

  if (g.ball.isBomb && g.state === 'playing' && x + 20 < g.w) {
    grid.put(y, x, 'BOMB! → TRASH CAN', 'bad')
    x += 19
  } else if (g.score >= DEPTH_AT && !g.ball.isBomb && x + 18 < g.w) {
    const bars = '▮'.repeat(g.aimDistance + 1) + '▯'.repeat(9 - g.aimDistance)
    grid.put(y, x, `DIST ${bars}`, 'value')
    x += 17
  }

  const hints = [`AIM ${aimAngle(g)}°  ←→ aim  SPACE shoot  P pause`, '←→ aim  SPACE shoot', 'SPACE shoot', '']
  const hint = hints.find(option => x + option.length + 2 <= g.w) ?? ''
  grid.put(y, g.w - hint.length - 1, hint, 'label')
}

function drawPanel(g: Game, grid: Grid, lines: [string, Style][]) {
  const inner = Math.max(...lines.map(([t]) => displayWidth(t))) + 6
  const bw = Math.min(inner, g.w - 2)
  const bh = lines.length + 4
  const y0 = Math.max(1, Math.floor((g.h - bh) / 2))
  const x0 = Math.floor((g.w - bw) / 2)
  grid.put(y0, x0, '╭' + '─'.repeat(bw - 2) + '╮', 'panel')
  for (let i = 1; i < bh - 1; i++) {
    grid.put(y0 + i, x0, '│' + ' '.repeat(bw - 2) + '│', 'panel')
  }
  grid.put(y0 + bh - 1, x0, '╰' + '─'.repeat(bw - 2) + '╯', 'panel')
  lines.forEach(([text, st], i) => {
    grid.put(y0 + 2 + i, x0 + Math.max(1, Math.floor((bw - displayWidth(text)) / 2)), text, st)
  })
}

function drawOverlay(g: Game, grid: Grid) {
  if (g.state === 'splash') {
    drawPanel(g, grid, [
      ['S H O T   C L O C K', 'rim'],
      ['', 'plain'],
      ['Sink baskets while Claude works.', 'plain'],
      ['', 'plain'],
      ['←/→ aim   SPACE shoot   P pause', 'value'],
      ['Lead the hoop: it keeps moving.', 'label'],
      ['5 misses and you are out.', 'label'],
      ['', 'plain'],
      ['click here, then any key', 'warn'],
      ['Esc goes back to Claude', 'label'],
    ])
  } else if (g.state === 'paused') {
    const panels: Record<PauseReason, [string, Style][]> = {
      pause: [
        ['PAUSED', 'value'],
        ['', 'plain'],
        ['P resume', 'label'],
      ],
      bomb: [
        ['BOMB!', 'bad'],
        ['', 'plain'],
        ["Don't shoot this one at the hoop.", 'plain'],
        ['Drop it in the trash can  [▄▄]', 'trash'],
        ['', 'plain'],
        ["Past the can's line anywhere else", 'label'],
        ['it blows up: that costs 2 lives.', 'label'],
        ['', 'plain'],
        ['any key to continue', 'warn'],
      ],
      claude_done: [
        ["✓ Claude's done", 'good'],
        ['', 'plain'],
        ['Your run is saved.', 'plain'],
        ['Esc to go back to Claude,', 'label'],
        ['or any key to keep playing.', 'label'],
      ],
      claude_needs: [
        ['! Claude needs you', 'bad'],
        ['', 'plain'],
        ['Press Esc to answer it.', 'plain'],
        ['Your run is paused.', 'label'],
      ],
    }
    drawPanel(g, grid, panels[g.pauseReason])
  } else if (g.state === 'over') {
    const milestone = MILESTONES.find(([pts]) => g.score >= pts)?.[1]
    drawPanel(g, grid, [
      ['GAME OVER', 'bad'],
      ['', 'plain'],
      [`Score  ${g.score}`, 'value'],
      g.newBest ? ['NEW BEST!', 'good'] : [`Best   ${g.best}`, 'label'],
      [`Longest streak  ${g.bestStreak}`, 'label'],
      ...(milestone ? ([['', 'plain'], [milestone, 'warn']] as [string, Style][]) : []),
      ['', 'plain'],
      ['R or SPACE to play again', 'value'],
    ])
  }
}

function render(g: Game): Grid {
  const grid = new Grid(g.w, g.h)
  grid.shakeDx = g.shakeDx
  grid.shakeTop = g.top
  grid.shakeBottom = g.floor
  drawCourt(g, grid)
  grid.shakeDx = 0
  drawHud(g, grid)
  drawBar(g, grid)
  drawOverlay(g, grid)
  return grid
}

// ------------------------------------------------------------------- module

type Holder = { game: Game; frame: number }

/** Turn a grid row into runs of same-styled text */
function rowRuns(grid: Grid, y: number) {
  const runs: { text: string; st: Style }[] = []
  for (let x = 0; x < grid.w; x++) {
    const c = grid.ch[y]![x]!
    const cellStyle = grid.st[y]![x]!
    if (c === TAIL) continue
    // Plain spaces join whatever run they sit in, so a row stays a few runs
    const st = c === ' ' && !('inverse' in STYLES[cellStyle]) ? 'plain' : cellStyle
    const last = runs[runs.length - 1]
    if (last && (last.st === st || (st === 'plain' && c === ' '))) last.text += c
    else runs.push({ text: c, st })
  }
  return runs
}

const ShotClockGame: ClientModule<GameProps, Holder> = (props, surface: ClientSurface<Holder>) => {
  const { Box, Text } = surface.elements
  let holder = surface.state
  if (!holder) {
    const game = newGame(props, message => surface.post(message))
    holder = { game, frame: 0 }
    let frame = 0
    surface.every(TICK_MS, () => {
      step(game, Date.now())
      surface.setState({ game, frame: ++frame })
    })
    surface.onKey(event => {
      handleKey(game, event)
      surface.setState({ game, frame: ++frame })
    })
    surface.setState(holder)
  }

  const g = holder.game
  syncClaude(g, props)
  const w = surface.columns
  const rows = surface.rows
  if (w < MIN_W || rows < MIN_H) {
    return <Text color="#8a8a8a">{`Shot Clock needs ${MIN_W}×${MIN_H}, has ${w}×${rows}. Make the pane bigger.`}</Text>
  }
  if (w !== g.w || rows !== g.h) layout(g, w, rows)

  const grid = render(g)
  return (
    <Box flexDirection="column" width={w} height={rows}>
      {grid.ch.map((_, y) => (
        <Text wrap="truncate">
          {rowRuns(grid, y).map(({ text, st }) => (st === 'plain' ? text : <Text {...STYLES[st]}>{text}</Text>))}
        </Text>
      ))}
    </Box>
  )
}

export default ShotClockGame
