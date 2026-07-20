/**
 * 红墨剪藏 - popup 逻辑
 *
 * 打开 popup 时：读取设置 → 向当前标签页注入 content.js 提取内容 → 展示预览；
 * 点击「发送到 RedInk」：POST http://127.0.0.1:<端口>/api/clips。
 * 设置（端口 / 访问令牌）存 chrome.storage.local。
 */

/** 默认 RedInk 端口（与后端 FLASK_PORT 默认值一致） */
const DEFAULT_PORT = 12398;

const SOURCE_LABELS = {
  xiaohongshu: '小红书',
  douyin: '抖音',
  other: '其他',
};

// 当前提取结果（发送时用）
let extracted = null;

const el = {
  preview: document.getElementById('preview'),
  sourceBadge: document.getElementById('source-badge'),
  previewAuthor: document.getElementById('preview-author'),
  previewTitle: document.getElementById('preview-title'),
  previewContent: document.getElementById('preview-content'),
  previewTags: document.getElementById('preview-tags'),
  status: document.getElementById('status'),
  sendBtn: document.getElementById('send-btn'),
  portInput: document.getElementById('port-input'),
  tokenInput: document.getElementById('token-input'),
  saveSettingsBtn: document.getElementById('save-settings-btn'),
  settingsSaved: document.getElementById('settings-saved'),
};

// ==================== 设置 ====================

async function loadSettings() {
  const stored = await chrome.storage.local.get({ port: DEFAULT_PORT, token: '' });
  const port = Number(stored.port) || DEFAULT_PORT;
  return { port: port, token: String(stored.token || '') };
}

async function saveSettings() {
  let port = parseInt(el.portInput.value, 10);
  if (!port || port < 1 || port > 65535) port = DEFAULT_PORT;
  const token = el.tokenInput.value.trim();
  await chrome.storage.local.set({ port: port, token: token });
  el.portInput.value = String(port);

  el.settingsSaved.classList.remove('hidden');
  setTimeout(() => el.settingsSaved.classList.add('hidden'), 1500);
}

// ==================== 状态展示 ====================

function setStatus(text, kind) {
  el.status.textContent = text;
  el.status.classList.remove('error', 'success');
  if (kind) el.status.classList.add(kind);
}

function renderPreview(result) {
  const source = SOURCE_LABELS[result.source] ? result.source : 'other';
  el.sourceBadge.textContent = SOURCE_LABELS[source];
  el.sourceBadge.className = 'badge ' + source;
  el.previewAuthor.textContent = result.author ? '@' + result.author : '';
  el.previewTitle.textContent = result.title || '（无标题）';
  el.previewContent.textContent = result.content || '（未提取到正文）';

  if (result.tags && result.tags.length > 0) {
    el.previewTags.textContent = result.tags.map((t) => '#' + t).join(' ');
    el.previewTags.classList.remove('hidden');
  } else {
    el.previewTags.classList.add('hidden');
  }

  el.preview.classList.remove('hidden');
}

// ==================== 提取 ====================

async function extractFromActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) {
    throw new Error('未找到当前标签页');
  }
  // 浏览器内部页面无法注入脚本
  const url = tab.url || '';
  if (!/^https?:/.test(url)) {
    throw new Error('当前页面不支持剪藏（请在小红书/抖音笔记页使用）');
  }

  // content.js 的完成值（末尾 IIFE 的返回值）即提取结果
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ['content.js'],
  });
  const result = results && results[0] ? results[0].result : null;
  if (!result) {
    throw new Error('页面内容提取失败（脚本无返回）');
  }
  return result;
}

async function initExtraction() {
  setStatus('正在提取当前页面内容…');
  try {
    const result = await extractFromActiveTab();
    if (!result.ok) {
      extracted = null;
      setStatus(result.error || '提取失败', 'error');
      return;
    }
    extracted = result;
    renderPreview(result);
    setStatus('已提取，确认无误后发送');
    el.sendBtn.disabled = false;
  } catch (e) {
    extracted = null;
    setStatus(e && e.message ? e.message : '页面内容提取失败', 'error');
  }
}

// ==================== 发送 ====================

async function sendToRedInk() {
  if (!extracted) return;

  el.sendBtn.disabled = true;
  setStatus('正在发送…');

  const settings = await loadSettings();
  const endpoint = 'http://127.0.0.1:' + settings.port + '/api/clips';

  const headers = { 'Content-Type': 'application/json' };
  // 用户启用 REDINK_ACCESS_TOKEN 鉴权时随请求携带令牌
  if (settings.token) {
    headers['X-Access-Token'] = settings.token;
  }

  const body = {
    source: extracted.source,
    url: extracted.url,
    title: extracted.title,
    author: extracted.author,
    content: extracted.content,
    tags: extracted.tags || [],
  };
  if (extracted.stats) {
    body.stats = extracted.stats;
  }

  let response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body),
    });
  } catch (e) {
    // fetch 抛 TypeError = 连接失败：RedInk 大概率没启动
    setStatus(
      'RedInk 未启动（连接失败）：请先在本机启动 RedInk（端口 ' + settings.port + '）后重试',
      'error'
    );
    el.sendBtn.disabled = false;
    return;
  }

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    data = null;
  }

  if (response.ok && data && data.success) {
    setStatus('已剪藏，去 RedInk 对标拆解查看', 'success');
    el.sendBtn.textContent = '已发送 ✓';
    return;
  }

  // 其他错误：区分鉴权失败与后端返回的结构化错误
  if (response.status === 401) {
    setStatus('访问未授权：RedInk 启用了访问令牌，请在下方设置中填写令牌后重试', 'error');
  } else {
    const detail =
      (data && data.error && (data.error.detail || data.error.title))
      || ('发送失败（HTTP ' + response.status + '）');
    setStatus(String(detail), 'error');
  }
  el.sendBtn.disabled = false;
}

// ==================== 初始化 ====================

async function init() {
  const settings = await loadSettings();
  el.portInput.value = String(settings.port);
  el.tokenInput.value = settings.token;

  el.sendBtn.addEventListener('click', sendToRedInk);
  el.saveSettingsBtn.addEventListener('click', saveSettings);

  await initExtraction();
}

init();
