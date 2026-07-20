/**
 * 红墨剪藏 - 页面内容提取脚本
 *
 * 由 popup 通过 chrome.scripting.executeScript 注入到当前标签页执行，
 * 最后一个表达式（IIFE 的返回值）即提取结果，回传给 popup。
 *
 * ⚠️ 重要：小红书/抖音均为频繁改版的 SPA，DOM 选择器必然易碎。
 * 平台改版导致提取失败时，需要更新下方 XHS_SELECTORS / DOUYIN_SELECTORS
 * 中的候选选择器（每个字段按顺序尝试多组候选，全部失败再走兜底）。
 * 兜底链：候选选择器 → meta 标签（og:title/description）→ document.title 清洗。
 *
 * 提取结果结构（与 RedInk /api/clips 请求体对齐）：
 * { ok, error?, source, url, title, author, content, tags[], stats|null }
 */
(() => {
  // ==================== 通用工具 ====================

  /** 依次尝试候选选择器，返回第一个有非空文本的元素文本 */
  function pickText(selectors, root) {
    const scope = root || document;
    for (const selector of selectors) {
      let el = null;
      try {
        el = scope.querySelector(selector);
      } catch (e) {
        continue; // 个别选择器语法在旧内核不支持时跳过
      }
      if (!el) continue;
      const text = (el.innerText || el.textContent || '').trim();
      if (text) return text;
    }
    return '';
  }

  /** 依次尝试候选选择器，返回第一个命中的元素 */
  function pickElement(selectors, root) {
    const scope = root || document;
    for (const selector of selectors) {
      try {
        const el = scope.querySelector(selector);
        if (el) return el;
      } catch (e) {
        continue;
      }
    }
    return null;
  }

  /** 读取 meta 标签内容（同时兼容 name 与 property 两种写法） */
  function metaContent(key) {
    const el = document.querySelector(
      'meta[name="' + key + '"], meta[property="' + key + '"]'
    );
    return el ? (el.getAttribute('content') || '').trim() : '';
  }

  /** document.title 清洗：去掉平台后缀（「xxx - 小红书」/「xxx - 抖音」等） */
  function cleanDocTitle() {
    return (document.title || '')
      .replace(/\s*[-|–—_·]\s*(小红书|抖音|小红书 - 你的生活兴趣社区|抖音短视频|Douyin).*$/i, '')
      .trim();
  }

  /**
   * 中文计数文本解析：「1.2万」→ 12000、「3亿」→ 300000000、「1,234」→ 1234。
   * 解析不出（如「点赞」「10万+」里的加号会被忽略）返回 null。
   */
  function parseCount(text) {
    if (!text) return null;
    const match = String(text).replace(/\s/g, '').match(/([\d,.]+)(万|亿|[wW])?/);
    if (!match) return null;
    const base = parseFloat(match[1].replace(/,/g, ''));
    if (isNaN(base)) return null;
    const unit = match[2] || '';
    let value = base;
    if (unit === '万' || unit === 'w' || unit === 'W') value = base * 10000;
    if (unit === '亿') value = base * 100000000;
    return Math.round(value);
  }

  /** 从容器内的话题链接收集标签：去 # 前缀、去重、上限 20 个 */
  function collectTags(container, anchorSelectors) {
    if (!container) return [];
    const tags = [];
    const seen = new Set();
    for (const selector of anchorSelectors) {
      let anchors = [];
      try {
        anchors = container.querySelectorAll(selector);
      } catch (e) {
        continue;
      }
      for (const a of anchors) {
        let text = (a.innerText || a.textContent || '').trim();
        text = text.replace(/^#/, '').replace(/\[话题\]/g, '').replace(/#$/, '').trim();
        if (text && !seen.has(text) && text.length <= 60) {
          seen.add(text);
          tags.push(text);
        }
        if (tags.length >= 20) return tags;
      }
    }
    return tags;
  }

  /** 正文轻度清洗：去掉小红书的「[话题]」标记与多余空行 */
  function cleanContent(text) {
    return (text || '')
      .replace(/\[话题\]/g, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  /** stats 对象收尾：三项全为 null 时返回 null（后端按「未采集到」处理） */
  function finalizeStats(likes, collects, comments) {
    if (likes === null && collects === null && comments === null) return null;
    const stats = {};
    if (likes !== null) stats.likes = likes;
    if (collects !== null) stats.collects = collects;
    if (comments !== null) stats.comments = comments;
    return stats;
  }

  // ==================== 小红书笔记页 ====================
  // 适配 /explore/<id>、/discovery/item/<id> 等笔记详情页
  // ⚠️ 平台改版需更新这里的候选选择器
  const XHS_SELECTORS = {
    title: ['#detail-title', '.note-content .title', '.note-detail-mask .title'],
    desc: ['#detail-desc .note-text', '#detail-desc', '.note-content .desc'],
    author: [
      '.author-wrapper .username',
      '.author-container .username',
      '.info .name .username',
      '.user-info .name',
    ],
    likes: [
      '.engage-bar-style .like-wrapper .count',
      '.engage-bar .like-wrapper .count',
      '.interact-container .like-wrapper .count',
    ],
    collects: [
      '.engage-bar-style .collect-wrapper .count',
      '.engage-bar .collect-wrapper .count',
      '.interact-container .collect-wrapper .count',
    ],
    comments: [
      '.engage-bar-style .chat-wrapper .count',
      '.engage-bar .chat-wrapper .count',
      '.interact-container .chat-wrapper .count',
    ],
    tagAnchors: ['a.tag', 'a[href*="search_result"]', 'a[href*="/search?"]'],
  };

  function extractXiaohongshu() {
    const title = pickText(XHS_SELECTORS.title)
      || metaContent('og:title').replace(/\s*-\s*小红书.*$/, '').trim()
      || cleanDocTitle();

    const descEl = pickElement(XHS_SELECTORS.desc);
    const content = cleanContent(
      (descEl && (descEl.innerText || descEl.textContent))
      || metaContent('description')
      || metaContent('og:description')
    );

    const author = pickText(XHS_SELECTORS.author);

    // 互动数：优先 DOM 计数元素；小红书 SSR 页还带有 og:xhs:note_* meta 可兜底
    const likes = parseCount(pickText(XHS_SELECTORS.likes))
      ?? parseCount(metaContent('og:xhs:note_like'));
    const collects = parseCount(pickText(XHS_SELECTORS.collects))
      ?? parseCount(metaContent('og:xhs:note_collect'));
    const comments = parseCount(pickText(XHS_SELECTORS.comments))
      ?? parseCount(metaContent('og:xhs:note_comment'));

    const tags = collectTags(descEl || document, XHS_SELECTORS.tagAnchors);
    // meta keywords 兜底（SSR 页有「关键词1,关键词2」）
    if (tags.length === 0) {
      const keywords = metaContent('keywords');
      if (keywords) {
        for (const k of keywords.split(/[,，]/)) {
          const t = k.trim();
          if (t && tags.length < 20) tags.push(t);
        }
      }
    }

    return {
      source: 'xiaohongshu',
      title: title,
      author: author,
      content: content,
      tags: tags,
      stats: finalizeStats(likes, collects, comments),
    };
  }

  // ==================== 抖音视频/图文页 ====================
  // 适配 /video/<id>、/note/<id> 及个人页弹层
  // ⚠️ 平台改版需更新这里的候选选择器（data-e2e 属性相对稳定，优先使用）
  const DOUYIN_SELECTORS = {
    desc: [
      '[data-e2e="video-desc"]',
      '[data-e2e="detail-video-desc"]',
      '#video-info-wrap .video-info-detail',
      '.video-info-detail .desc',
    ],
    author: [
      '[data-e2e="video-author-name"]',
      '[data-e2e="detail-video-author-name"]',
      '[data-e2e="user-info"] .account-name',
      '.author-card-user-name',
      '.account-name',
    ],
    likes: [
      '[data-e2e="video-player-digg"] span',
      '[data-e2e="detail-video-like"] span',
      '.video-info-detail .digg-count',
    ],
    collects: [
      '[data-e2e="video-player-collect"] span',
      '[data-e2e="detail-video-collect"] span',
    ],
    comments: [
      '[data-e2e="video-player-comment"] span',
      '[data-e2e="detail-video-comment"] span',
      '[data-e2e="comment-count"]',
    ],
    tagAnchors: ['a[href*="/search/"]', 'a.hashtag', 'a[data-e2e="video-tag"]'],
  };

  function extractDouyin() {
    const descEl = pickElement(DOUYIN_SELECTORS.desc);
    const rawDesc = cleanContent(
      (descEl && (descEl.innerText || descEl.textContent))
      || metaContent('og:description')
      || metaContent('description')
    );

    // 抖音通常只有一段文案：标题取 og:title 清洗，取不到用文案首行
    let title = metaContent('og:title')
      .replace(/\s*[-|–]\s*抖音.*$/, '').trim()
      || cleanDocTitle();
    if (!title && rawDesc) {
      title = rawDesc.split('\n')[0].slice(0, 80);
    }

    const author = pickText(DOUYIN_SELECTORS.author);

    const likes = parseCount(pickText(DOUYIN_SELECTORS.likes));
    const collects = parseCount(pickText(DOUYIN_SELECTORS.collects));
    const comments = parseCount(pickText(DOUYIN_SELECTORS.comments));

    const tags = collectTags(descEl || document, DOUYIN_SELECTORS.tagAnchors);

    return {
      source: 'douyin',
      title: title,
      author: author,
      content: rawDesc,
      tags: tags,
      stats: finalizeStats(likes, collects, comments),
    };
  }

  // ==================== 其他站点兜底 ====================

  function extractGeneric() {
    return {
      source: 'other',
      title: metaContent('og:title') || cleanDocTitle(),
      author: metaContent('author') || '',
      content: cleanContent(
        metaContent('description') || metaContent('og:description')
      ),
      tags: [],
      stats: null,
    };
  }

  // ==================== 主流程 ====================

  try {
    const host = location.hostname;
    let result;
    if (/(^|\.)xiaohongshu\.com$/.test(host)) {
      result = extractXiaohongshu();
    } else if (/(^|\.)douyin\.com$/.test(host)) {
      result = extractDouyin();
    } else {
      result = extractGeneric();
    }

    result.url = location.href;

    if (!result.title && !result.content) {
      // 完全失败：返回带 error 的结果，popup 据此提示用户
      result.ok = false;
      result.error = '未能从页面提取到标题或正文（可能页面还没加载完，或平台改版导致选择器失效）';
    } else {
      result.ok = true;
    }
    return result;
  } catch (e) {
    return {
      ok: false,
      error: '提取脚本执行出错：' + (e && e.message ? e.message : String(e)),
      source: 'other',
      url: location.href,
      title: '',
      author: '',
      content: '',
      tags: [],
      stats: null,
    };
  }
})();
