// ─── CONFIG ──────────────────────────────────────────────────────────────────
// API_BASE is set by config.js (auto-detects local vs production)
const API_BASE = window.RAID_API || 'http://localhost:8000'

// ─── RANK DEFINITIONS ────────────────────────────────────────────────────────
const RANKS = [
  { name: 'ANON',     min: 0,    max: 99   },
  { name: 'SIGNAL',   min: 100,  max: 499  },
  { name: 'RAIDER',   min: 500,  max: 1999 },
  { name: 'BASED',    min: 2000, max: 9999 },
  { name: 'GIGACHAD', min: 10000,max: Infinity }
]

// ─── STATE ────────────────────────────────────────────────────────────────────
let currentUser       = null
let currentBalance    = 0
let ws                = null
let wsReconnectDelay  = 1000
let countdownInterval = null
let pollInterval      = null
let tickerMessages    = [
  'gm anon. raid season is open.',
  'keep grinding ser.',
  'raid-fun // idol64'
]

// ─── AUDIO ENGINE ────────────────────────────────────────────────────────────
let _audioCtx = null

function getAudioContext() {
  if (!_audioCtx) {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  }
  return _audioCtx
}

function initAudio() {
  // Resume context on first user interaction (autoplay policy)
  try {
    const ctx = getAudioContext()
    if (ctx.state === 'suspended') ctx.resume()
  } catch (e) {}
}

function playGrindPing() {
  try {
    const ctx = getAudioContext();
    [220, 440].forEach((freq, i) => {
      const osc  = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = freq
      osc.type = 'sine'
      gain.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.09)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.09 + 0.12)
      osc.start(ctx.currentTime + i * 0.09)
      osc.stop(ctx.currentTime + i * 0.09 + 0.12)
    })
  } catch (e) {}
}

function playBonusPing() {
  try {
    const ctx = getAudioContext();
    [220, 440, 880].forEach((freq, i) => {
      const osc  = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = freq
      osc.type = 'sine'
      gain.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.07)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.07 + 0.1)
      osc.start(ctx.currentTime + i * 0.07)
      osc.stop(ctx.currentTime + i * 0.07 + 0.1)
    })
  } catch (e) {}
}

function playMutualPing() {
  try {
    const ctx = getAudioContext();
    [440, 440].forEach((freq, i) => {
      const osc  = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = freq
      osc.type = 'square'
      gain.gain.setValueAtTime(0.08, ctx.currentTime + i * 0.1)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.1 + 0.08)
      osc.start(ctx.currentTime + i * 0.1)
      osc.stop(ctx.currentTime + i * 0.1 + 0.08)
    })
  } catch (e) {}
}

function playNewRaidSound() {
  try {
    const ctx  = getAudioContext()
    const osc  = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 110
    osc.type = 'sine'
    gain.gain.setValueAtTime(0.1, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.15)
  } catch (e) {}
}

// ─── API HELPERS ─────────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem('raidfun_token')
}

async function api(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(API_BASE + path, {
    ...options,
    headers
  })

  if (resp.status === 401) {
    logout()
    throw new Error('Unauthorized')
  }

  return resp
}

// ─── AUTH ─────────────────────────────────────────────────────────────────────
function loginWithDiscord() {
  window.location.href = API_BASE + '/auth/discord'
}

function loginWithX() {
  window.location.href = API_BASE + '/auth/x'
}

function handleOAuthCallback() {
  // Both Discord and X callbacks redirect back with ?token=<jwt>
  const params = new URLSearchParams(window.location.search)
  const token  = params.get('token')
  if (token) {
    localStorage.setItem('raidfun_token', token)
    // Clean URL without reload
    const url = window.location.pathname
    window.history.replaceState({}, '', url)
  }
}

/** @deprecated kept for backwards compat — forwards to handleOAuthCallback */
function handleDiscordCallback() {
  handleOAuthCallback()
}

async function checkAuth() {
  const token = getToken()
  if (!token) return false

  try {
    const resp = await api('/auth/me')
    if (!resp.ok) return false
    const data = await resp.json()
    currentUser = data
    currentBalance = data.grind_balance || 0
    return true
  } catch (e) {
    return false
  }
}

function logout() {
  localStorage.removeItem('raidfun_token')
  currentUser = null
  ws && ws.close()
  ws = null
  showView('view-login')
  document.getElementById('top-bar').classList.add('hidden')
  document.getElementById('live-ticker').classList.add('hidden')
  document.getElementById('bottom-nav').classList.add('hidden')
}

// ─── NAVIGATION ──────────────────────────────────────────────────────────────
function showView(viewId) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'))
  const target = document.getElementById(viewId)
  if (target) target.classList.add('active')

  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewId)
  })

  // On-demand data loading
  if (viewId === 'view-feed')           loadFeed()
  if (viewId === 'view-profile')        loadProfile()
  if (viewId === 'view-notifications')  loadNotifications()
  if (viewId === 'view-post-raid')      { updatePostRaidCost(); syncPostBalance() }
}

function navTo(viewId) {
  initAudio()
  showView(viewId)
}

// ─── RANK HELPERS ─────────────────────────────────────────────────────────────
function getRankForBalance(balance) {
  for (let i = RANKS.length - 1; i >= 0; i--) {
    if (balance >= RANKS[i].min) return RANKS[i]
  }
  return RANKS[0]
}

function rankBadgeHTML(rankName) {
  const safe = rankName || 'ANON'
  return `<span class="rank-badge rank-${safe}">${safe}</span>`
}

function avatarInitial(handle) {
  if (!handle) return '?'
  return handle.replace('@', '').charAt(0).toUpperCase()
}

// ─── BALANCE BAR ─────────────────────────────────────────────────────────────
function loadBalanceBar() {
  if (!currentUser) return
  const rank = getRankForBalance(currentBalance)
  document.getElementById('balance-amount').textContent = currentBalance
  const badge = document.getElementById('top-rank-badge')
  badge.textContent  = rank.name
  badge.className    = `rank-badge rank-${rank.name}`
}

function animateBalanceUpdate(newBalance) {
  const el      = document.getElementById('balance-amount')
  const start   = currentBalance
  const end     = newBalance
  const dur     = 600
  const startTs = performance.now()

  function step(ts) {
    const progress = Math.min((ts - startTs) / dur, 1)
    const eased    = 1 - Math.pow(1 - progress, 3)
    const val      = Math.round(start + (end - start) * eased)
    el.textContent = val
    if (progress < 1) requestAnimationFrame(step)
    else {
      el.textContent = end
      currentBalance = end
      loadBalanceBar()
    }
  }

  flashBalance()
  requestAnimationFrame(step)
}

function flashBalance() {
  const el = document.getElementById('balance-display')
  el.classList.add('flash')
  setTimeout(() => el.classList.remove('flash'), 600)
}

// ─── FEED ─────────────────────────────────────────────────────────────────────
async function loadFeed() {
  const list     = document.getElementById('feed-list')
  const subtitle = document.getElementById('feed-subtitle')
  list.innerHTML = '<div class="feed-loading">loading raids...</div>'

  try {
    const resp = await api('/raids')
    if (!resp.ok) throw new Error('Failed to load raids')
    const raids = await resp.json()

    if (!raids.length) {
      list.innerHTML  = '<div class="feed-empty">no active raids right now.<br>be the first to post one.</div>'
      subtitle.textContent = '0 active raids'
      return
    }

    subtitle.textContent = `${raids.length} active raid${raids.length !== 1 ? 's' : ''}`
    list.innerHTML = raids.map(r => renderRaidCard(r)).join('')

    // Attach event listeners
    raids.forEach(r => attachRaidCardListeners(r))

    startCountdowns()
  } catch (e) {
    list.innerHTML = `<div class="error-msg">failed to load raids. is the backend running?</div>`
    subtitle.textContent = 'error'
  }
}

function getClaimedRaids() {
  try {
    return JSON.parse(localStorage.getItem('claimed_raids') || '[]')
  } catch { return [] }
}

function addClaimedRaid(raidId) {
  const claimed = getClaimedRaids()
  if (!claimed.includes(raidId)) {
    claimed.push(raidId)
    localStorage.setItem('claimed_raids', JSON.stringify(claimed))
  }
}

function renderRaidCard(raid) {
  const claimed       = getClaimedRaids()
  const hasClaimed    = claimed.includes(raid.id)
  const isHost        = currentUser && raid.host_id === currentUser.id
  const expiresAt     = new Date(raid.expires_at).toISOString()
  const tweetUrl      = raid.tweet_url || ''
  const shortUrl      = tweetUrl.replace('https://', '').replace('http://', '').slice(0, 48) + (tweetUrl.length > 48 ? '…' : '')
  const rank          = raid.host_rank || 'ANON'
  const handle        = raid.host_handle || raid.host_discord || 'anon'
  const reward        = raid.reward_per_raider || 15
  const maxRaiders    = raid.max_raiders || 0
  const claimsCount   = raid.claims_count || 0
  const instructions  = raid.instructions ? `<div style="font-size:12px;color:var(--muted);margin-bottom:10px;">${escapeHtml(raid.instructions)}</div>` : ''

  // Determine pending mutual claims this user can act on (host perspective)
  const mutualClaims  = (isHost && raid.claims) 
    ? raid.claims.filter(c => c.reply_verified && !c.mutual_verified)
    : []

  // Build action area
  let actionHTML = ''
  if (isHost) {
    actionHTML = `<div class="verified-badge">✓ YOUR RAID</div>`
    if (mutualClaims.length > 0) {
      mutualClaims.forEach(c => {
        actionHTML += `<button class="mutual-btn" data-claim-id="${c.id}" data-raid-id="${raid.id}">
          👀 GIVE MUTUAL to @${escapeHtml(c.raider_handle || 'anon')}
        </button>`
      })
    }
  } else if (hasClaimed) {
    // Check if verified in claims
    const myClaim = raid.claims && currentUser
      ? raid.claims.find(c => c.raider_id === currentUser.id)
      : null
    if (myClaim && myClaim.reply_verified) {
      actionHTML = `<div class="verified-badge">✓ RAIDED +${reward} $GRIND</div>`
    } else {
      actionHTML = `<div class="pending-badge">⏳ VERIFYING...</div>`
    }
  } else {
    const expired  = new Date(raid.expires_at) < new Date()
    const full     = maxRaiders > 0 && claimsCount >= maxRaiders
    const disabled = expired || full ? 'disabled' : ''
    const btnLabel = expired ? 'EXPIRED' : full ? 'FULL' : `RAID &rarr; +${reward} $GRIND`
    actionHTML = `<button class="raid-btn" data-raid-id="${raid.id}" ${disabled}>${btnLabel}</button>`
  }

  // Extend link (host only)
  const extendHTML = isHost 
    ? `<div class="raid-divider"></div><span class="extend-link" data-raid-id="${raid.id}">+ extend 1h (10 $GRIND)</span>`
    : ''

  return `
    <div class="raid-card" data-raid-id="${raid.id}">
      <div class="host-info">
        <div class="host-avatar">${avatarInitial(handle)}</div>
        <div class="host-meta">
          <div class="host-handle"><span class="host-handle-prefix">@</span>${escapeHtml(handle)}</div>
        </div>
        ${rankBadgeHTML(rank)}
      </div>
      ${instructions}
      <a class="tweet-link" href="${escapeHtml(tweetUrl)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(tweetUrl)}">
        ↗ ${escapeHtml(shortUrl)}
      </a>
      <div class="raid-meta">
        <span class="raid-reward">+${reward} $GRIND per raid</span>
        <span class="raid-slots">${maxRaiders > 0 ? `${claimsCount}/${maxRaiders} raiders` : `${claimsCount} raiders`}</span>
        <span class="countdown" data-expires="${expiresAt}">${formatTimeLeft(Math.floor((new Date(raid.expires_at) - Date.now()) / 1000))}</span>
      </div>
      <div class="raid-card-actions">
        ${actionHTML}
      </div>
      ${extendHTML}
    </div>
  `
}

function attachRaidCardListeners(raid) {
  // Raid button
  const raidBtn = document.querySelector(`.raid-card[data-raid-id="${raid.id}"] .raid-btn`)
  if (raidBtn) {
    raidBtn.addEventListener('click', () => claimRaid(raid.id))
  }

  // Mutual buttons
  document.querySelectorAll(`.raid-card[data-raid-id="${raid.id}"] .mutual-btn`).forEach(btn => {
    btn.addEventListener('click', () => claimMutual(raid.id, btn.dataset.claimId))
  })

  // Extend link
  const extLink = document.querySelector(`.raid-card[data-raid-id="${raid.id}"] .extend-link`)
  if (extLink) {
    extLink.addEventListener('click', () => extendRaid(raid.id))
  }
}

function formatTimeLeft(seconds) {
  if (seconds <= 0) return 'EXPIRED'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function startCountdowns() {
  if (countdownInterval) clearInterval(countdownInterval)
  countdownInterval = setInterval(() => {
    document.querySelectorAll('[data-expires]').forEach(el => {
      const secsLeft = Math.floor((new Date(el.dataset.expires) - Date.now()) / 1000)
      el.textContent = formatTimeLeft(secsLeft)
      el.className = 'countdown'
      if (secsLeft <= 0)                      el.classList.add('expired')
      else if (secsLeft < 600)               el.classList.add('danger')
      else if (secsLeft < 1800)              el.classList.add('warn')
      else                                   el.classList.add('ok')
    })
  }, 1000)
}

// ─── RAID ACTIONS ────────────────────────────────────────────────────────────
async function claimRaid(raidId) {
  initAudio()
  const card   = document.querySelector(`.raid-card[data-raid-id="${raidId}"]`)
  const btn    = card ? card.querySelector('.raid-btn') : null
  if (btn) { btn.disabled = true; btn.textContent = 'CLAIMING...' }

  try {
    const resp = await api(`/raids/${raidId}/claim`, { method: 'POST' })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(err.detail || 'Failed to claim')
    }

    addClaimedRaid(raidId)

    // Optimistically update button to pending
    if (card) {
      const actions = card.querySelector('.raid-card-actions')
      if (actions) actions.innerHTML = `<div class="pending-badge">⏳ VERIFYING...</div>`
    }

    playGrindPing()
    showToast('+15 $GRIND (pending verification)', 'grind')

  } catch (e) {
    if (btn) {
      btn.disabled  = false
      btn.innerHTML = 'RAID &rarr;'
    }
    showToast(e.message || 'Claim failed', 'error')
  }
}

async function claimMutual(raidId, claimId) {
  initAudio()
  const btn = document.querySelector(`.mutual-btn[data-claim-id="${claimId}"]`)
  if (btn) { btn.disabled = true; btn.textContent = 'SENDING MUTUAL...' }

  try {
    const resp = await api(`/raids/${raidId}/mutual/${claimId}`, { method: 'POST' })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(err.detail || 'Failed')
    }

    if (btn) btn.closest('.raid-card-actions').removeChild(btn)
    playMutualPing()
    showToast('+5 $GRIND MUTUAL', 'mutual')

  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '👀 GIVE MUTUAL' }
    showToast(e.message || 'Mutual failed', 'error')
  }
}

async function extendRaid(raidId) {
  initAudio()
  const link = document.querySelector(`.extend-link[data-raid-id="${raidId}"]`)
  if (link) { link.style.opacity = '0.5'; link.style.pointerEvents = 'none' }

  try {
    const resp = await api(`/raids/${raidId}/extend`, {
      method: 'POST',
      body: JSON.stringify({ hours: 1 })
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(err.detail || 'Failed to extend')
    }
    showToast('Raid extended +1h (-10 $GRIND)', 'grind')
    loadFeed()
  } catch (e) {
    if (link) { link.style.opacity = ''; link.style.pointerEvents = '' }
    showToast(e.message || 'Extend failed', 'error')
  }
}

// ─── POST RAID ────────────────────────────────────────────────────────────────
const COST_PER_HOUR = 10

function updatePostRaidCost() {
  const hours    = parseInt(document.getElementById('raid-duration').value) || 1
  const base     = COST_PER_HOUR
  const extra    = (hours - 1) * COST_PER_HOUR
  const total    = base + extra

  document.getElementById('cost-base').textContent  = `${base} $GRIND`
  document.getElementById('cost-total').textContent = `${total} $GRIND`

  const extraRow = document.getElementById('cost-extra-row')
  if (extra > 0) {
    extraRow.style.display = 'flex'
    document.getElementById('cost-extra').textContent = `+${extra} $GRIND`
  } else {
    extraRow.style.display = 'none'
  }
}

function syncPostBalance() {
  const el = document.getElementById('post-balance-display')
  if (el) el.textContent = `${currentBalance} $GRIND`
}

async function submitRaid(e) {
  e.preventDefault()
  initAudio()

  const tweetUrl    = document.getElementById('raid-tweet-url').value.trim()
  const instructions= document.getElementById('raid-instructions').value.trim()
  const duration    = parseInt(document.getElementById('raid-duration').value)
  const maxRaiders  = parseInt(document.getElementById('raid-max-raiders').value) || 0
  const errEl       = document.getElementById('post-error')
  const okEl        = document.getElementById('post-success')
  const btn         = document.getElementById('btn-submit-raid')

  errEl.classList.add('hidden')
  okEl.classList.add('hidden')

  if (!tweetUrl) {
    errEl.textContent = 'Tweet URL is required.'
    errEl.classList.remove('hidden')
    return
  }

  btn.disabled    = true
  btn.textContent = 'POSTING...'

  try {
    const resp = await api('/raids', {
      method: 'POST',
      body: JSON.stringify({
        tweet_url:    tweetUrl,
        instructions: instructions || null,
        duration_hours: duration,
        max_raiders:  maxRaiders
      })
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(err.detail || 'Failed to post raid')
    }

    const raid = await resp.json()
    okEl.textContent = `Raid posted! (-${COST_PER_HOUR * duration} $GRIND)`
    okEl.classList.remove('hidden')
    document.getElementById('post-raid-form').reset()
    updatePostRaidCost()

    // Deduct from balance
    const newBal = currentBalance - COST_PER_HOUR * duration
    animateBalanceUpdate(newBal)

    setTimeout(() => navTo('view-feed'), 1200)

  } catch (e) {
    errEl.textContent = e.message || 'Failed to post raid'
    errEl.classList.remove('hidden')
  } finally {
    btn.disabled    = false
    btn.textContent = 'Post Raid'
  }
}

// ─── PROFILE ─────────────────────────────────────────────────────────────────
async function loadProfile() {
  const container = document.getElementById('profile-content')
  container.innerHTML = '<div class="feed-loading">loading profile...</div>'

  try {
    const [meResp, txResp, balResp] = await Promise.all([
      api('/auth/me'),
      api('/grind/transactions'),
      api('/grind/balance')
    ])

    if (!meResp.ok) throw new Error('Failed to load profile')
    const user = await meResp.json()
    currentUser = user

    let txns = []
    if (txResp.ok) txns = await txResp.json()

    let balData = null
    if (balResp.ok) balData = await balResp.json()
    if (balData && typeof balData.balance === 'number') {
      currentBalance = balData.balance
      loadBalanceBar()
    }

    const rank = getRankForBalance(currentBalance)
    container.innerHTML = renderProfileHTML(user, rank, txns)

    // Animate rank progress bar
    setTimeout(() => {
      const fill = document.getElementById('rank-progress-fill')
      if (fill) fill.style.width = fill.dataset.target
    }, 100)

  } catch (e) {
    container.innerHTML = `<div class="error-msg">failed to load profile</div>`
  }
}

function renderProfileHTML(user, rank, txns) {
  const handle      = user.x_handle || user.discord_username || 'anon'
  const discord     = user.discord_username || ''
  const raids       = user.raids_hosted || 0
  const raidsDone   = user.raids_completed || 0
  const totalEarned = user.total_earned || 0

  // Rank progress
  const nextRankIdx = RANKS.findIndex(r => r.name === rank.name) + 1
  const nextRank    = RANKS[nextRankIdx] || null
  let progressPct   = 100
  let progressLabel = 'MAX RANK'
  if (nextRank && nextRank.min !== Infinity) {
    const span    = nextRank.min - rank.min
    const done    = currentBalance - rank.min
    progressPct   = Math.min(100, Math.round((done / span) * 100))
    progressLabel = `${currentBalance} / ${nextRank.min} for ${nextRank.name}`
  }

  return `
    <div class="profile-header">
      <div class="profile-avatar">${avatarInitial(handle)}</div>
      <div class="profile-info">
        <div class="profile-handle">@${escapeHtml(handle)}
          ${rankBadgeHTML(rank.name)}
        </div>
        ${discord ? `<div class="profile-discord">${escapeHtml(discord)} via Discord</div>` : ''}
      </div>
    </div>

    <div class="profile-stats">
      <div class="stat-cell">
        <div class="stat-value">${currentBalance}</div>
        <div class="stat-label">$GRIND</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">${raidsDone}</div>
        <div class="stat-label">Raided</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">${raids}</div>
        <div class="stat-label">Posted</div>
      </div>
    </div>

    <div class="rank-progress-section">
      <div class="rank-progress-header">
        <span class="rank-progress-title">rank progress</span>
        ${rankBadgeHTML(rank.name)}
      </div>
      <div class="rank-progress-bar">
        <div class="rank-progress-fill" id="rank-progress-fill"
          style="width:0%; background:${rankColor(rank.name)};"
          data-target="${progressPct}%">
        </div>
      </div>
      <div class="rank-progress-labels">
        <span>${rank.name}</span>
        <span>${progressLabel}</span>
        ${nextRank ? `<span>${nextRank.name}</span>` : ''}
      </div>
    </div>

    <div class="section-title">recent transactions</div>
    <div class="tx-list">
      ${txns.length ? txns.slice(0, 20).map(tx => renderTxItem(tx)).join('') : '<div class="feed-empty">no transactions yet</div>'}
    </div>

    <div class="section-sep"></div>
    <button class="btn-outline" onclick="logout()">Logout</button>
  `
}

function rankColor(rankName) {
  const map = {
    ANON:     'var(--muted)',
    SIGNAL:   'var(--cyan)',
    RAIDER:   'var(--purple)',
    BASED:    'var(--gold)',
    GIGACHAD: 'var(--red)'
  }
  return map[rankName] || 'var(--cyan)'
}

function renderTxItem(tx) {
  const amount   = tx.amount || 0
  const positive = amount >= 0
  const typeClass = tx.type === 'mutual' ? 'mutual'
    : tx.type === 'bonus' ? 'bonus'
    : positive ? 'positive' : 'negative'
  const sign     = positive ? '+' : ''
  const desc     = tx.description || tx.type || 'transaction'
  const time     = tx.created_at ? formatRelTime(new Date(tx.created_at)) : ''

  return `
    <div class="tx-item">
      <div>
        <div class="tx-desc">${escapeHtml(desc)}</div>
        <div class="tx-meta">${time}</div>
      </div>
      <div class="tx-amount ${typeClass}">${sign}${amount} $GRIND</div>
    </div>
  `
}

function formatRelTime(date) {
  const diff = Math.floor((Date.now() - date) / 1000)
  if (diff < 60)   return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`
  if (diff < 86400)return `${Math.floor(diff/3600)}h ago`
  return `${Math.floor(diff/86400)}d ago`
}

// ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
async function loadNotifications() {
  const list = document.getElementById('notif-list')
  if (!list) return
  list.innerHTML = '<div class="feed-loading">loading...</div>'

  try {
    const resp = await api('/grind/transactions')
    if (!resp.ok) throw new Error('Failed')
    const txns = await resp.json()

    if (!txns.length) {
      list.innerHTML = '<div class="feed-empty">no notifications yet</div>'
      return
    }

    list.innerHTML = txns.slice(0, 30).map(tx => {
      const icon   = tx.type === 'mutual' ? '🤝' : tx.type === 'bonus' ? '⚡' : tx.amount > 0 ? '💰' : '📤'
      const amount = tx.amount >= 0 ? `+${tx.amount}` : `${tx.amount}`
      const time   = tx.created_at ? formatRelTime(new Date(tx.created_at)) : ''
      return `
        <div class="notif-item">
          <div class="notif-icon">${icon}</div>
          <div>
            <div class="notif-text">${escapeHtml(tx.description || tx.type || 'transaction')}</div>
            <div class="notif-time">${time}</div>
          </div>
          <div class="notif-amount">${amount} $GRIND</div>
        </div>
      `
    }).join('')
  } catch (e) {
    list.innerHTML = '<div class="error-msg">failed to load</div>'
  }
}

// ─── HANDLE SETUP ─────────────────────────────────────────────────────────────
async function submitHandle() {
  const input  = document.getElementById('handle-input')
  const errEl  = document.getElementById('handle-error')
  const btn    = document.getElementById('btn-submit-handle')
  const handle = input.value.trim().replace(/^@/, '')

  errEl.classList.add('hidden')

  if (!handle) {
    errEl.textContent = 'Please enter your X handle.'
    errEl.classList.remove('hidden')
    return
  }

  btn.disabled    = true
  btn.textContent = 'Submitting...'

  try {
    const resp = await api('/auth/set-handle', {
      method: 'POST',
      body: JSON.stringify({ x_handle: handle })
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(err.detail || 'Failed')
    }

    const data = await resp.json()

    // Show verification instructions
    const verifyCode = data.verify_code || `raid-fun-verify-${handle}`
    const tweetText  = `verifying my @idol64 raid-fun account. code: ${verifyCode}`
    const tweetUrl   = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}`

    document.getElementById('verify-tweet-text').textContent = tweetText
    document.getElementById('verify-tweet-link').href = tweetUrl
    document.getElementById('verify-instructions').classList.add('visible')

    btn.textContent = 'Waiting...'

    pollHandleVerification()

  } catch (e) {
    errEl.textContent = e.message || 'Failed to set handle'
    errEl.classList.remove('hidden')
    btn.disabled    = false
    btn.textContent = 'Continue'
  }
}

function pollHandleVerification() {
  if (pollInterval) clearInterval(pollInterval)
  let attempts = 0
  pollInterval = setInterval(async () => {
    attempts++
    if (attempts > 60) {
      clearInterval(pollInterval)
      return
    }
    try {
      const resp = await api('/auth/me')
      if (!resp.ok) return
      const user = await resp.json()
      if (user.x_handle_verified) {
        clearInterval(pollInterval)
        currentUser = user
        document.getElementById('verify-polling').textContent = '✓ verified!'
        setTimeout(() => {
          connectWS()
          showView('view-feed')
          loadFeed()
          loadBalanceBar()
          document.getElementById('top-bar').classList.remove('hidden')
          document.getElementById('live-ticker').classList.remove('hidden')
          document.getElementById('bottom-nav').classList.remove('hidden')
        }, 800)
      }
    } catch (e) {}
  }, 10000)
}

// ─── TOAST ────────────────────────────────────────────────────────────────────
function showToast(message, type = 'grind') {
  const container = document.getElementById('toast-container')
  const toast     = document.createElement('div')
  toast.className = `toast ${type === 'error' ? 'grind' : type}`
  toast.textContent = message
  container.appendChild(toast)
  setTimeout(() => {
    if (toast.parentNode) toast.parentNode.removeChild(toast)
  }, 1600)
}

// ─── LIVE TICKER ─────────────────────────────────────────────────────────────
function addTickerMessage(msg) {
  tickerMessages.unshift(msg)
  if (tickerMessages.length > 20) tickerMessages.pop()
  renderTicker()
}

function renderTicker() {
  const inner = document.getElementById('ticker-inner')
  if (!inner) return
  inner.textContent = tickerMessages.join(' · ') + ' · '
}

function startTicker() {
  renderTicker()
}

// ─── WEBSOCKET ────────────────────────────────────────────────────────────────
function connectWS() {
  const token = getToken()
  if (!token) return

  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

  const wsUrl = API_BASE.replace(/^http/, 'ws') + `/ws?token=${token}`
  try {
    ws = new WebSocket(wsUrl)
  } catch (e) {
    scheduleWSReconnect()
    return
  }

  ws.onopen = () => {
    wsReconnectDelay = 1000
    addTickerMessage('connected to raid stream')
  }

  ws.onmessage = handleWSMessage

  ws.onclose = () => {
    ws = null
    scheduleWSReconnect()
  }

  ws.onerror = () => {
    ws && ws.close()
  }
}

function scheduleWSReconnect() {
  setTimeout(connectWS, wsReconnectDelay)
  wsReconnectDelay = Math.min(wsReconnectDelay * 2, 30000)
}

function handleWSMessage(event) {
  let data
  try { data = JSON.parse(event.data) } catch (e) { return }

  switch (data.type) {
    case 'grind_earned':     handleGrindEarned(data);    break
    case 'mutual_available': handleMutualAvailable(data); break
    case 'live_feed':        handleLiveFeed(data);        break
    case 'new_raid':         handleNewRaid(data);         break
    case 'raid_claimed':     handleRaidClaimed(data);     break
    default:                 break
  }
}

function handleGrindEarned(data) {
  const amount   = data.amount || 0
  const newBal   = (currentBalance || 0) + amount
  const isMutual = data.reason === 'mutual'
  const isBonus  = data.reason === 'bonus' || data.reason === 'signal_boost'

  animateBalanceUpdate(newBal)

  if (isBonus) {
    showToast(`⚡ SIGNAL BOOST +${amount} $GRIND`, 'bonus')
    playBonusPing()
  } else if (isMutual) {
    showToast(`+${amount} $GRIND MUTUAL`, 'mutual')
    playMutualPing()
  } else {
    showToast(`+${amount} $GRIND`, 'grind')
    playGrindPing()
  }
}

function handleMutualAvailable(data) {
  // Refresh feed to show mutual CTA
  const activeView = document.querySelector('.view.active')
  if (activeView && activeView.id === 'view-feed') {
    loadFeed()
  }
  addTickerMessage(`mutual available on raid ${data.raid_id}`)
}

function handleLiveFeed(data) {
  const msg = data.message || data.text
  if (msg) addTickerMessage(msg)
}

function handleNewRaid(data) {
  const handle = data.host_handle || 'anon'
  addTickerMessage(`new raid from @${handle}`)
  playNewRaidSound()

  // If user is on feed, reload
  const activeView = document.querySelector('.view.active')
  if (activeView && activeView.id === 'view-feed') {
    loadFeed()
  }
}

function handleRaidClaimed(data) {
  const handle = data.raider_handle || 'anon'
  addTickerMessage(`@${handle} just raided`)
  // Update claim count on card if visible
  const countEl = document.querySelector(`.raid-card[data-raid-id="${data.raid_id}"] .raid-slots`)
  if (countEl) {
    const text = countEl.textContent
    const match = text.match(/(\d+)/)
    if (match) {
      const n = parseInt(match[1]) + 1
      countEl.textContent = countEl.textContent.replace(/^\d+/, n)
    }
  }
}

// ─── UTILS ───────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  if (!str) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // 1. Handle OAuth callback (Discord or X)
  handleOAuthCallback()

  // 2. Check auth
  const authed = await checkAuth()

  if (authed && currentUser) {
    if (!currentUser.x_handle_verified) {
      // Need to set handle
      document.getElementById('top-bar').classList.add('hidden')
      document.getElementById('live-ticker').classList.add('hidden')
      document.getElementById('bottom-nav').classList.add('hidden')
      showView('view-set-handle')
    } else {
      // Fully authenticated
      document.getElementById('top-bar').classList.remove('hidden')
      document.getElementById('live-ticker').classList.remove('hidden')
      document.getElementById('bottom-nav').classList.remove('hidden')
      loadBalanceBar()
      connectWS()
      showView('view-feed')
      loadFeed()
    }
  } else {
    showView('view-login')
  }

  // 3. Start ticker
  startTicker()

  // 4. Wire up cost preview
  updatePostRaidCost()

  // 5. Init audio on any interaction
  document.addEventListener('click', initAudio, { once: true })
})
