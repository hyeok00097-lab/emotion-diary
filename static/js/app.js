/* ─── 감정 정의 ────────────────────────────────────────────────── */
const EMOTIONS = {
  joy:        { label: '기쁨',   color: '#FAC775' },
  excitement: { label: '설렘',   color: '#FF9F6B' },
  neutral:    { label: '평범함', color: '#9DCFB5' },
  surprise:   { label: '놀라움', color: '#85C9EB' },
  disgust:    { label: '불쾌함', color: '#C4A882' },
  fear:       { label: '두려움', color: '#AFA9EC' },
  sadness:    { label: '슬픔',   color: '#85B7EB' },
  anger:      { label: '분노',   color: '#F09595' },
};

/* ─── 명상 음악 파일 목록 (하드코딩) ──────────────────────────── */
const MED_MUSIC_FILES = [
  { filename: 'Rain_On_Rooftop.mp3',
    title: '빗소리' },
  { filename: '594779__messyacousticapocalypse666__ambience-1-crickets-at-night.mp3',
    title: '밤 풀벌레 소리' },
  { filename: '637563__kyles__forest-boreal-light-wind-breeze-through-leaves-close-loud-birds.mp3',
    title: '숲 속 바람 소리' },
  { filename: '729396__heckfricker__campfire-02.mp3',
    title: '모닥불 소리' },
  { filename: '73723__akacie__autumn-forest-wind.mp3',
    title: '가을 바람 소리' },
];

function _randomMedMusic() {
  const pick = MED_MUSIC_FILES[Math.floor(Math.random() * MED_MUSIC_FILES.length)];
  return { url: `/static/Meditation_Music/${pick.filename}`, title: pick.title };
}

let calYear, calMonth, analysisCache = null;
let _sliderIdx = 0, _sliderTotal = 0, _touchStartX = 0;

/* ─── 대화형 모드 상태 ───────────────────────────────────────────── */
let currentMode   = 'chat';   // 'chat' | 'direct'
let chatHistory   = [];       // [{role, content}, ...] — API 전달용 (첫 인사말 제외)
let _typingCount  = 0;        // typing indicator ID 생성용

/* ─── 초기화 ────────────────────────────────────────────────────── */
function init() {
  const now = new Date();
  calYear  = now.getFullYear();
  calMonth = now.getMonth();
  document.getElementById('today-label').textContent =
    now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });

  /* 채팅 입력창 Enter → 전송, Shift+Enter → 줄바꿈 */
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  /* 기본 모드: 대화형 — 첫 인사말 표시 */
  startChat();
}

/* ─── 탭 전환 ───────────────────────────────────────────────────── */
function switchTab(tab) {
  const tabs = ['write', 'calendar', 'stats'];
  document.querySelectorAll('.tab').forEach((t, i) =>
    t.classList.toggle('active', tabs[i] === tab));
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + tab).classList.add('active');
  if (tab === 'calendar') renderCalendar();
  if (tab === 'stats')    renderStats();
}

/* ─── STF 분석 요청 ─────────────────────────────────────────────── */
async function analyzeDiary() {
  const situation = document.getElementById('situation').value.trim();
  const thought   = document.getElementById('thought').value.trim();
  const feeling   = document.getElementById('feeling').value.trim();

  if (!situation && !thought && !feeling) {
    alert('상황, 생각, 감정 중 하나 이상 입력해주세요.');
    return;
  }

  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  document.getElementById('result-area').innerHTML =
    '<div class="loading">감정을 분석하고 있어요 <span class="dot">·</span><span class="dot">·</span><span class="dot">·</span></div>';

  try {
    const res    = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ situation, thought, feeling }),
    });
    const result = await res.json();
    if (result.error) throw new Error(result.error);
    result.situation = situation;
    result.thought   = thought;
    result.feeling   = feeling;
    // DB 저장용: LLM 생성 텍스트 그대로 유지 (STF concat으로 덮어쓰지 않음)
    // 표시용: LLM 텍스트 없으면 STF 폴백
    const displayDiaryText = result.diary_text ||
      [situation, thought, feeling].filter(Boolean).join('\n');
    analysisCache = result;
    showDiaryDisplay(displayDiaryText);
    renderResult(result);
  } catch (e) {
    document.getElementById('result-area').innerHTML =
      `<div class="empty-state">분석 중 오류가 발생했어요.<br>${e.message}</div>`;
  }
  btn.disabled = false;
}

/* ─── 모드 전환 ──────────────────────────────────────────────────── */
function switchMode(mode) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById('btn-mode-' + mode).classList.add('active');
  document.getElementById('chat-section').style.display       = mode === 'chat'   ? '' : 'none';
  document.getElementById('stf-write-section').style.display  = mode === 'direct' ? '' : 'none';

  /* 대화형으로 전환 시 대화 히스토리가 비어있으면 첫 인사말 표시 */
  if (mode === 'chat' && chatHistory.length === 0) {
    startChat();
  }
}

/* ─── 일기 텍스트 표시 / 리셋 ───────────────────────────────────── */
function showDiaryDisplay(text) {
  document.getElementById('write-input-section').style.display = 'none';
  document.getElementById('diary-text-content').textContent    = text;
  document.getElementById('diary-display').style.display       = 'block';
}

function resetToSTF() {
  _pauseMedTimer();
  _medRemaining = 300;
  document.getElementById('write-input-section').style.display = '';
  document.getElementById('diary-display').style.display        = 'none';
  document.getElementById('result-area').innerHTML              = '';
  analysisCache = null;

  /* 대화형 모드였으면 히스토리 초기화 후 재시작 */
  if (currentMode === 'chat') startChat();
}

/* ─── 슬라이더 ──────────────────────────────────────────────────── */
function slideTo(idx) {
  if (idx < 0) idx = 0;
  if (idx >= _sliderTotal) idx = _sliderTotal - 1;
  _sliderIdx = idx;
  const track = document.getElementById('slider-track');
  if (track) track.style.transform = `translateX(-${idx * 100}%)`;
  document.querySelectorAll('.slider-dot').forEach((d, i) =>
    d.classList.toggle('active', i === idx));
  const prev = document.getElementById('slider-prev');
  const next = document.getElementById('slider-next');
  if (prev) prev.style.opacity = idx === 0 ? '0.3' : '1';
  if (next) next.style.opacity = idx === _sliderTotal - 1 ? '0.3' : '1';
}

function slideNav(dir) { slideTo(_sliderIdx + dir); }

/* ─── 분석 결과 렌더링 (슬라이더) ──────────────────────────────── */
function renderResult(r) {
  const color = EMOTIONS[r.dominant]?.color || '#888';

  /* 유사도 콘솔 로그 (UI 미표시) */
  if (r.similarity) {
    const { dominant_match, score_similarity_pct } = r.similarity;
    console.log(`[유사도] dominant_match=${dominant_match} / cosine=${score_similarity_pct}%`);
  }

  /* 배지 */
  let badge = '';
  if (r.via_nlp === true)
    badge = `<span class="badge badge-nlp">KoELECTRA ✓</span><span class="conf-text">${r.nlp_confidence}%</span>`;
  else if (r.nlp_confidence > 0)
    badge = `<span class="badge badge-fix">KoELECTRA 수정</span><span class="conf-text">NLP ${r.nlp_confidence}%</span>`;
  else
    badge = `<span class="badge badge-llm">LLM 분석</span>`;

  /* ── Card 1: 감정 분석 + 공감 메시지 ── */
  const bars = Object.entries(EMOTIONS).map(([k, em]) => `
    <div class="emo-row">
      <span class="emo-name">${em.label}</span>
      <div class="bar-track"><div class="bar-fill" id="bar-${k}" style="background:${em.color}"></div></div>
      <span class="bar-pct">${(Math.round((r[k] || 0) * 10) / 10).toFixed(1)}%</span>
    </div>`).join('');

  const card1 = `
    <div class="slider-card">
      <div class="card-title">감정 분석 ${badge}</div>
      ${r.empathy ? `
      <div class="empathy-box" style="margin-bottom:.85rem">
        <div class="empathy-label">💜 공감 메시지</div>
        <div class="empathy-text">${r.empathy}</div>
      </div>` : ''}
      ${bars}
    </div>`;

  /* ── Card 2: 음악 추천 ── */
  let card2;
  if (r.playlist && r.playlist.length > 0) {
    const t = r.playlist[0];
    card2 = `
      <div class="slider-card">
        <div class="card-title">🎵 오늘의 감정 추천곡</div>
        <div class="rec">
          <div class="playlist-track">
            <div class="track-info">
              <div class="track-title">${t.title}</div>
              <div class="track-artist">${t.artist}</div>
            </div>
            <a class="track-link" href="${t.url}" target="_blank">▶</a>
          </div>
        </div>
      </div>`;
  } else {
    card2 = `
      <div class="slider-card">
        <div class="card-title">🎵 오늘의 감정 추천곡</div>
        <div class="empty-state" style="padding:2rem 0">추천곡을 찾지 못했어요.</div>
      </div>`;
  }

  /* ── Card 3: 명상 가이드 ── */
  let card3;
  if (r.meditation) {
    const m     = r.meditation;
    const steps = m.steps.map(s => `<li>${s}</li>`).join('');
    const music = _randomMedMusic();
    card3 = `
      <div class="slider-card">
        <div class="card-title">🧘 감정 명상 가이드</div>
        <div class="meditation-card">
          <div class="meditation-header">
            <div class="meditation-title">${m.icon || ''} ${m.title}</div>
            <span class="meditation-duration">${m.duration}</span>
          </div>
          <div class="meditation-subtitle">${m.subtitle}</div>
          <ol class="meditation-steps" style="--step-color:${color}">${steps}</ol>
          <div class="meditation-affirmation">"${m.affirmation}"</div>
          <div class="meditation-music">
            <audio id="med-audio" loop preload="none" src="${music.url}"></audio>
            <div class="med-top-row">
              <button class="med-play-btn" id="med-play-btn"
                      onclick="toggleMedAudio()" aria-label="재생">▶</button>
              <div class="med-music-info">
                <div class="med-music-label">명상 배경음악 · 5분 타이머</div>
                <div class="med-music-title">${music.title}</div>
              </div>
              <div class="med-timer" id="med-timer">5:00</div>
            </div>
            <div class="med-bottom-row">
              <span class="med-vol-icon">🔊</span>
              <input class="med-volume" id="med-volume" type="range"
                     min="0" max="1" step="0.05" value="0.5"
                     oninput="setMedVolume(this.value)" aria-label="볼륨">
            </div>
            <div class="med-done-msg" id="med-done-msg">명상이 완료되었습니다 🙏</div>
          </div>
        </div>
      </div>`;
  } else {
    card3 = `
      <div class="slider-card">
        <div class="card-title">🧘 감정 명상 가이드</div>
        <div class="empty-state" style="padding:2rem 0">명상 가이드를 찾지 못했어요.</div>
      </div>`;
  }

  const cards = [card1, card2, card3];
  _sliderTotal  = cards.length;
  _sliderIdx    = 0;
  _medRemaining = 300;

  const dots = cards.map((_, i) =>
    `<span class="slider-dot${i === 0 ? ' active' : ''}" onclick="slideTo(${i})"></span>`
  ).join('');

  document.getElementById('result-area').innerHTML = `
    <div class="result-slider-wrap">
      <button class="slider-arrow" id="slider-prev" onclick="slideNav(-1)"
              style="opacity:.3" aria-label="이전">‹</button>
      <div class="slider-viewport">
        <div class="slider-track" id="slider-track">${cards.join('')}</div>
      </div>
      <button class="slider-arrow" id="slider-next" onclick="slideNav(1)"
              aria-label="다음">›</button>
    </div>
    <div class="slider-dots" id="slider-dots">${dots}</div>
    <button class="btn" onclick="saveEmotion()" style="margin-top:1rem">감정 기록 저장하기</button>`;

  /* 바 애니메이션 */
  setTimeout(() => {
    Object.keys(EMOTIONS).forEach(k => {
      const el = document.getElementById('bar-' + k);
      if (el) el.style.width = Math.round(r[k] || 0) + '%';
    });
  }, 50);

  /* 터치 스와이프 */
  const viewport = document.querySelector('.slider-viewport');
  viewport.addEventListener('touchstart', e => {
    _touchStartX = e.touches[0].clientX;
  }, { passive: true });
  viewport.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - _touchStartX;
    if (Math.abs(dx) > 40) slideNav(dx < 0 ? 1 : -1);
  }, { passive: true });
}

/* ─── 대화형: 채팅 시작 (첫 인사말 표시, 히스토리 초기화) ──────────── */
function startChat() {
  chatHistory = [];
  const container = document.getElementById('chat-messages');
  if (!container) return;
  container.innerHTML = '';
  /* 첫 인사말은 화면에만 표시 — API 히스토리에는 포함하지 않음 */
  _appendBubble('ai', '안녕하세요! 오늘 하루 어떠셨나요? 😊');
}

/* ─── 대화형: 메시지 전송 ────────────────────────────────────────── */
async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text  = input.value.trim();
  if (!text) return;

  /* 사용자 말풍선 */
  _appendBubble('user', text);
  chatHistory.push({ role: 'user', content: text });
  input.value = '';
  input.style.height = '';

  const sendBtn  = document.getElementById('chat-send-btn');
  const typingId = _appendTyping();
  sendBtn.disabled = true;

  try {
    const res  = await fetch('/api/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ messages: chatHistory }),
    });
    const data = await res.json();
    _removeTyping(typingId);

    if (data.error) throw new Error(data.error);

    if (data.done) {
      /* STF 추출 완료 → 분석 파이프라인 호출 */
      _appendBubble('ai', '좋아요! 이제 감정을 분석해볼게요 ✨');
      await _runAnalysisFromChat(data.situation, data.thought, data.feeling);
    } else {
      _appendBubble('ai', data.message);
      chatHistory.push({ role: 'assistant', content: data.message });
    }
  } catch (e) {
    _removeTyping(typingId);
    _appendBubble('ai', `오류가 발생했어요 😢 ${e.message}`);
  }

  sendBtn.disabled = false;
  input.focus();
}

/* ─── 대화형: 분석 파이프라인 실행 (/api/analyze 연결) ────────────── */
async function _runAnalysisFromChat(situation, thought, feeling) {
  document.getElementById('result-area').innerHTML =
    '<div class="loading">감정을 분석하고 있어요 <span class="dot">·</span><span class="dot">·</span><span class="dot">·</span></div>';

  try {
    const res    = await fetch('/api/analyze', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ situation, thought, feeling }),
    });
    const result = await res.json();
    if (result.error) throw new Error(result.error);

    result.situation = situation;
    result.thought   = thought;
    result.feeling   = feeling;

    const displayText = result.diary_text ||
      [situation, thought, feeling].filter(Boolean).join('\n');
    analysisCache = result;
    showDiaryDisplay(displayText);
    renderResult(result);
  } catch (e) {
    document.getElementById('result-area').innerHTML =
      `<div class="empty-state">분석 중 오류가 발생했어요.<br>${e.message}</div>`;
  }
}

/* ─── 대화형: 말풍선 추가 헬퍼 ──────────────────────────────────── */
function _appendBubble(role, text) {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const isUser = role === 'user';
  const wrap   = document.createElement('div');
  wrap.className = `chat-bubble-wrap ${role}`;
  wrap.innerHTML = `
    <div class="chat-avatar">${isUser ? '🙂' : '🤖'}</div>
    <div class="chat-bubble ${role}">${text}</div>`;
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
}

/* ─── 대화형: 타이핑 인디케이터 추가/제거 ────────────────────────── */
function _appendTyping() {
  const container = document.getElementById('chat-messages');
  const id        = 'typing-' + (++_typingCount);
  const wrap      = document.createElement('div');
  wrap.id        = id;
  wrap.className = 'chat-bubble-wrap ai';
  wrap.innerHTML = `
    <div class="chat-avatar">🤖</div>
    <div class="chat-bubble ai">
      <div class="chat-typing"><span></span><span></span><span></span></div>
    </div>`;
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
  return id;
}

function _removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* ─── 감정 저장 ─────────────────────────────────────────────────── */
async function saveEmotion() {
  if (!analysisCache) return;
  const today = new Date().toISOString().slice(0, 10);
  const res   = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date: today, ...analysisCache }),
  });
  const data = await res.json();
  if (data.status === 'ok') {
    const sb = document.querySelector('#result-area .btn');
    if (sb) { sb.textContent = '저장 완료!'; sb.disabled = true; }
  }
}

/* ─── 달력 ──────────────────────────────────────────────────────── */
function changeMonth(dir) {
  calMonth += dir;
  if (calMonth > 11) { calMonth = 0; calYear++; }
  if (calMonth <  0) { calMonth = 11; calYear--; }
  renderCalendar();
}

async function renderCalendar() {
  document.getElementById('cal-title').textContent = `${calYear}년 ${calMonth + 1}월`;
  const res     = await fetch(`/api/calendar/${calYear}/${calMonth + 1}`);
  const records = await res.json();
  const firstDay    = new Date(calYear, calMonth, 1).getDay();
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const today = new Date();

  let html = ['일','월','화','수','목','금','토'].map(d => `<div class="cal-dn">${d}</div>`).join('');
  for (let i = 0; i < firstDay; i++) html += '<div class="cal-cell empty"></div>';
  for (let d = 1; d <= daysInMonth; d++) {
    const key     = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const rec     = records[key];
    const isToday = today.getFullYear() === calYear && today.getMonth() === calMonth && today.getDate() === d;
    const dot     = rec ? `<div class="cal-dot" style="background:${EMOTIONS[rec.dominant]?.color || '#888'}"></div>` : '';
    const click   = rec ? `onclick="openDiaryModal('${key}')"` : '';
    html += `<div class="cal-cell${isToday ? ' today' : ''}${rec ? ' has-record' : ''}" ${click}>${d}${dot}</div>`;
  }
  document.getElementById('cal-grid').innerHTML = html;
  document.getElementById('cal-legend').innerHTML = Object.entries(EMOTIONS).map(([, em]) =>
    `<div class="leg-item"><div class="leg-dot" style="background:${em.color}"></div>${em.label}</div>`
  ).join('');
}

/* ─── 주간 통계 ─────────────────────────────────────────────────── */
async function renderStats() {
  const container = document.getElementById('stats-content');
  container.innerHTML = '<div class="loading">통계를 불러오는 중 <span class="dot">·</span><span class="dot">·</span><span class="dot">·</span></div>';
  try {
    const res  = await fetch('/api/stats/weekly');
    const data = await res.json();
    const { records, filled_count, book_info } = data;

    const bars = records.map(({ weekday, record }) => {
      if (!record) return `
        <div class="w-col">
          <span class="w-score" style="visibility:hidden">0%</span>
          <div class="w-bar-wrap">
            <div class="w-bar" style="height:6px;background:#EEEDE8"></div>
          </div>
          <span class="w-label">${weekday}</span>
        </div>`;
      const domScore = Math.round((record.scores[record.dominant] || 0) * 10) / 10;
      const h        = Math.round(4 + (record.scores[record.dominant] || 50) * 0.82);
      const barColor = EMOTIONS[record.dominant]?.color || '#ccc';
      const tooltipRows = Object.entries(EMOTIONS).map(([k, em]) =>
        `<div class="w-tip-row"><span class="w-tip-dot" style="background:${em.color}"></span>${em.label} <b>${(Math.round((record.scores[k] || 0) * 10) / 10).toFixed(1)}%</b></div>`
      ).join('');
      return `
        <div class="w-col">
          <span class="w-score">${domScore}%</span>
          <div class="w-bar-wrap">
            <div class="w-bar" style="height:${h}px;background:${barColor}"></div>
            <div class="w-tooltip">${tooltipRows}</div>
          </div>
          <span class="w-label">${weekday}</span>
        </div>`;
    }).join('');

    const summaryText = filled_count > 0
      ? `이번 주 <strong>${filled_count}일</strong>의 감정을 기록했어요.`
      : '이번 주 아직 기록된 감정이 없어요.';

    let bookHtml = '';
    if (book_info && book_info.title) {
      const b    = book_info;
      const meta = [b.publisher, b.published ? b.published + '년' : '', b.pages ? b.pages + 'p' : ''].filter(Boolean).join(' · ');
      bookHtml = `
        <div class="book-section">
          <div class="book-section-label">📚 이번 주 감정 기반 추천 도서</div>
          <div class="book-card-stats">
            ${b.thumbnail ? `<img src="${b.thumbnail}" class="book-thumb" onerror="this.style.display='none'">` : ''}
            <div class="book-info">
              <div class="book-title">${b.title}</div>
              <div class="book-author">${b.author || ''}</div>
              ${meta ? `<div class="book-meta">${meta}</div>` : ''}
              ${b.description ? `<div class="book-desc">${b.description}</div>` : ''}
            </div>
          </div>
        </div>`;
    } else if (filled_count < 7) {
      const remain = 7 - filled_count;
      bookHtml = `
        <div class="book-section">
          <div class="book-section-label">📚 이번 주 감정 기반 추천 도서</div>
          <div class="book-pending">앞으로 <strong>${remain}일</strong> 더 기록하면<br>이번 주 감정에 맞는 책을 추천해드려요 📖</div>
        </div>`;
    }

    container.innerHTML = `
      <div class="stats-section">
        <p class="section-label">이번 주 감정 흐름</p>
        <div class="card" style="padding:1rem"><div class="week-bars">${bars}</div></div>
        <div class="week-summary">${summaryText}${bookHtml}</div>
      </div>`;
  } catch (e) {
    container.innerHTML = '<div class="empty-state">통계를 불러오는 중 오류가 발생했어요.</div>';
  }
}

/* ─── 날짜 상세 모달 ────────────────────────────────────────────── */
async function openDiaryModal(date) {
  const res = await fetch(`/api/diary/${date}`);
  if (!res.ok) return;
  const d  = await res.json();
  const em = EMOTIONS[d.dominant] || { label: d.dominant, color: '#888' };

  document.getElementById('modal-date').textContent = date.replace(/-/g, '.');
  document.getElementById('modal-dominant').innerHTML =
    `<span class="modal-dominant" style="background:${em.color}">${em.label}</span>`;

  document.getElementById('modal-stf').innerHTML = buildModalSTF(d);

  const empathyEl = document.getElementById('modal-empathy');
  empathyEl.textContent   = d.empathy || '';
  empathyEl.style.display = d.empathy ? 'block' : 'none';

  document.getElementById('modal-overlay').classList.add('open');
}

function buildModalSTF(d) {
  if (d.situation || d.thought || d.feeling) {
    const row = (badge, label, text) => text ? `
      <div class="stf-modal-section">
        <div class="stf-modal-label"><span class="stf-modal-badge">${badge}</span>${label}</div>
        <div class="stf-modal-text">${text}</div>
      </div>` : '';
    return row('S', '상황', d.situation) +
           row('T', '생각', d.thought)   +
           row('F', '감정', d.feeling);
  }
  return d.diary_text
    ? `<div class="stf-modal-text">${d.diary_text}</div>`
    : '<div class="stf-modal-text" style="color:var(--muted)">(내용 없음)</div>';
}

function closeModal(e) {
  if (e.target === document.getElementById('modal-overlay'))
    document.getElementById('modal-overlay').classList.remove('open');
}

/* ─── 명상 배경음악 + 타이머 ────────────────────────────────────── */
let _medTimerId   = null;
let _medRemaining = 300;   // 5분 = 300초

function toggleMedAudio() {
  const audio = document.getElementById('med-audio');
  const btn   = document.getElementById('med-play-btn');
  if (!audio) return;

  if (audio.paused) {
    audio.volume = parseFloat(document.getElementById('med-volume')?.value ?? 0.5);
    audio.play();
    btn.textContent = '⏸';
    _startMedTimer();
  } else {
    audio.pause();
    btn.textContent = '▶';
    _pauseMedTimer();
  }
}

function setMedVolume(val) {
  const audio = document.getElementById('med-audio');
  if (audio) audio.volume = parseFloat(val);
}

function _startMedTimer() {
  if (_medTimerId) return;
  _medTimerId = setInterval(() => {
    _medRemaining -= 1;
    _updateTimerDisplay();
    if (_medRemaining <= 0) _finishMeditation();
  }, 1000);
}

function _pauseMedTimer() {
  clearInterval(_medTimerId);
  _medTimerId = null;
}

function _updateTimerDisplay() {
  const el = document.getElementById('med-timer');
  if (!el) return;
  const m = Math.floor(_medRemaining / 60);
  const s = _medRemaining % 60;
  el.textContent = `${m}:${String(s).padStart(2, '0')}`;
}

function _finishMeditation() {
  _pauseMedTimer();
  _medRemaining = 300;

  const audio = document.getElementById('med-audio');
  const btn   = document.getElementById('med-play-btn');
  const timer = document.getElementById('med-timer');
  const msg   = document.getElementById('med-done-msg');

  if (audio) audio.pause();
  if (btn)   btn.textContent = '▶';
  if (timer) timer.textContent = '5:00';
  if (msg)   msg.classList.add('visible');
}

/* ─── CSS 변수 주입: meditation step color ──────────────────────── */
document.head.insertAdjacentHTML('beforeend', `<style>
  .meditation-steps li::before { background: var(--step-color, #888); }
</style>`);

init();
