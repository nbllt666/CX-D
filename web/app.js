'use strict';

const MOODS = {
  calm: { valence: 0.05, arousal: 0.2 },
  joy: { valence: 0.6, arousal: 0.4 },
  low: { valence: -0.6, arousal: 0.3 },
  anxious: { valence: -0.3, arousal: 0.8 },
};

const MODE_LABELS = {
  memory: '记忆梦',
  wild: '天马行空',
  dreamless: '一夜无梦',
};

const SPEAKER_LABELS = {
  director: '潜意识导演',
  dreamer: '梦者',
  awakened: '醒者',
};

const state = {
  session: null,
  turns: [],
  recall: null,
  busy: false,
};

const $ = (id) => document.getElementById(id);

function showView(name) {
  ['setup', 'dream', 'wake', 'dreamless', 'archive'].forEach((view) => {
    $(`view-${view}`).classList.toggle('hidden', view !== name);
  });
  const stage = document.querySelector('.stage');
  if (stage) {
    stage.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (error) {
    throw new Error('无法连接梦境服务，请确认服务已启动。');
  }
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : `请求失败（${response.status}）`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

let toastTimer = null;

function toast(message) {
  const node = $('toast');
  node.textContent = message;
  node.classList.remove('hidden');
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => node.classList.add('hidden'), 4200);
}

function setBusy(busy) {
  state.busy = busy;
  ['sleep-btn', 'wake-btn', 'continue-btn', 'speak-input'].forEach((id) => {
    const node = $(id);
    if (node) {
      node.disabled = busy;
    }
  });
  document.querySelectorAll('#sleep-form textarea, #sleep-form input, #sleep-form select, #speak-form button').forEach(
    (node) => {
      node.disabled = busy;
    }
  );
  $('typing').classList.toggle('hidden', !busy);
  $('sleep-btn').textContent = busy ? '正在沉入…' : '入睡';
}

function splitLines(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitEntities(text) {
  return text
    .split(/[,，、;；]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatDate(iso) {
  if (!iso) {
    return '';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const pad = (value) => String(value).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function renderTurns(container, turns) {
  container.replaceChildren();
  (turns || []).forEach((turn) => {
    const article = document.createElement('article');
    article.className = `turn ${turn.speaker}`;

    const head = document.createElement('div');
    head.className = 'turn-head';

    const speaker = document.createElement('span');
    speaker.className = 'speaker';
    speaker.textContent = SPEAKER_LABELS[turn.speaker] || turn.speaker;

    const seq = document.createElement('span');
    seq.className = 'turn-seq';
    seq.textContent = `#${String(turn.seq || 0).padStart(2, '0')}`;

    head.append(speaker, seq);

    if (turn.flagged) {
      const flag = document.createElement('span');
      flag.className = 'turn-flag';
      flag.textContent = '梦的边界';
      head.append(flag);
    }

    const body = document.createElement('p');
    body.className = 'turn-body';
    body.textContent = turn.content || '';

    article.append(head, body);
    container.append(article);
  });
}

function scrollTurnsToBottom(container) {
  requestAnimationFrame(() => {
    const last = container.lastElementChild;
    if (last) {
      last.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });
}

function setModeBadge(node, session) {
  node.textContent = session.mode_label || MODE_LABELS[session.mode] || session.mode;
  node.className = `badge badge-${session.mode}`;
}

function renderDream() {
  const session = state.session;
  if (!session) {
    showView('setup');
    return;
  }
  setModeBadge($('dream-mode'), session);
  $('dream-reason').textContent = session.mode_reason || '';
  renderTurns($('turns'), state.turns);
  showView('dream');
  scrollTurnsToBottom($('turns'));
}

function renderWake() {
  const session = state.session || {};
  const recall = state.recall || {};
  $('wake-title').textContent = session.title || recall.title || '无名之梦';
  $('wake-summary').textContent = session.summary || recall.summary || '梦醒时只剩下一点潮湿的光。';

  const residue = session.emotion_residue || recall.emotion_residue || {};
  const container = $('wake-emotion');
  container.replaceChildren();
  const valence = Number(residue.valence || 0);
  const arousal = Number(residue.arousal || 0);
  [
    ['情绪效价', `${valence >= 0 ? '+' : ''}${valence.toFixed(2)}`],
    ['唤醒度', arousal.toFixed(2)],
    ['模式', session.mode_label || MODE_LABELS[session.mode] || '梦'],
  ].forEach(([label, value]) => {
    const chip = document.createElement('span');
    chip.className = 'residue-chip';
    chip.textContent = `${label} ${value}`;
    container.append(chip);
  });

  showView('wake');
}

function renderDreamless() {
  const session = state.session || {};
  $('dreamless-reason').textContent =
    session.mode_reason || '潜意识按下了静音键，今夜没有梦。';
  showView('dreamless');
}

function renderArchive() {
  const session = state.session || {};
  $('archive-reason').textContent = `${session.mode_label || MODE_LABELS[session.mode] || ''} · ${
    session.mode_reason || ''
  }`;
  renderTurns($('archive-turns'), state.turns);
  showView('archive');
}

function renderResult(payload, { refreshHistory = true } = {}) {
  state.session = payload.session || null;
  state.turns = payload.turns || [];
  state.recall = payload.recall || null;

  if (!state.session) {
    showView('setup');
    return;
  }
  if (state.session.mode === 'dreamless') {
    renderDreamless();
  } else if (state.session.status === 'ended') {
    renderWake();
  } else {
    renderDream();
  }
  if (refreshHistory) {
    loadHistory();
  }
}

async function loadHistory() {
  try {
    const data = await api('/api/sessions');
    const items = data.items || [];
    $('history-count').textContent = String(items.length);
    const list = $('history-list');
    list.replaceChildren();

    items.forEach((session) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'history-item';
      if (state.session && state.session.id === session.id) {
        button.classList.add('active');
      }

      const title = document.createElement('div');
      title.className = 'history-title';

      if (session.status === 'active') {
        const dot = document.createElement('span');
        dot.className = 'dot';
        title.append(dot);
      }

      const titleText = document.createElement('span');
      titleText.textContent =
        session.title || (session.status === 'active' ? '未醒的梦' : '无题之梦');
      title.append(titleText);

      const meta = document.createElement('div');
      meta.className = 'history-meta';

      const mode = document.createElement('span');
      mode.textContent = session.mode_label || MODE_LABELS[session.mode] || session.mode;

      const time = document.createElement('span');
      time.textContent = formatDate(session.created_at);

      meta.append(mode, time);
      button.append(title, meta);
      button.addEventListener('click', () => loadSession(session.id));
      list.append(button);
    });
  } catch (error) {
    $('history-count').textContent = '—';
  }
}

async function loadSession(sessionId) {
  if (state.busy) {
    return;
  }
  setBusy(true);
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
    renderResult(data);
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(false);
  }
}

async function startDream(event) {
  event.preventDefault();
  if (state.busy) {
    return;
  }
  const moodNode = document.querySelector('input[name="mood"]:checked');
  const payload = {
    day_memories: splitLines($('memories').value),
    entities: splitEntities($('entities').value),
    emotion: MOODS[moodNode ? moodNode.value : 'calm'] || MOODS.calm,
    mode: $('mode').value,
  };
  setBusy(true);
  try {
    const data = await api('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    renderResult(data);
    $('speak-input').value = '';
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(false);
  }
}

async function sendMessage(content) {
  if (state.busy || !state.session) {
    return;
  }
  setBusy(true);
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(state.session.id)}/message`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
    $('speak-input').value = '';
    renderResult(data);
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(false);
  }
}

async function wakeUp() {
  if (state.busy || !state.session) {
    return;
  }
  setBusy(true);
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(state.session.id)}/wake`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    renderResult(data);
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(false);
  }
}

function newDream() {
  state.session = null;
  state.turns = [];
  state.recall = null;
  $('memories').value = '';
  $('entities').value = '';
  $('mode').value = 'auto';
  const calm = document.querySelector('input[name="mood"][value="calm"]');
  if (calm) {
    calm.checked = true;
  }
  showView('setup');
  loadHistory();
  $('memories').focus();
}

function bind() {
  $('sleep-form').addEventListener('submit', startDream);
  $('speak-form').addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage($('speak-input').value.trim());
  });
  $('continue-btn').addEventListener('click', () => sendMessage(''));
  $('wake-btn').addEventListener('click', wakeUp);
  $('archive-btn').addEventListener('click', renderArchive);
  $('back-wake').addEventListener('click', renderWake);
  $('new-dream').addEventListener('click', newDream);
  $('again-btn').addEventListener('click', newDream);
  $('dreamless-again').addEventListener('click', newDream);
}

bind();
loadHistory();
showView('setup');
