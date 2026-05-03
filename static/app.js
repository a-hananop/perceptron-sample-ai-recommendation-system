/* ── State ──────────────────────────────────────────────── */
const state = {
  interests: [],
  mood: '',
};

/* ── DOM refs ────────────────────────────────────────────── */
const loadingState  = document.getElementById('loadingState');
const emptyState    = document.getElementById('emptyState');
const errorState    = document.getElementById('errorState');
const resultsSection= document.getElementById('resultsSection');
const cardsGrid     = document.getElementById('cardsGrid');
const generateBtn   = document.getElementById('generateBtn');
const regenerateBtn = document.getElementById('regenerateBtn');
const interestCount = document.getElementById('interestCount');

/* ── Show initial empty state ────────────────────────────── */
showState('empty');

/* ── Pills ───────────────────────────────────────────────── */
document.querySelectorAll('.pill').forEach(pill => {
  pill.addEventListener('click', () => {
    const group = pill.dataset.group;
    const val   = pill.dataset.val;

    if (group === 'mood') {
      document.querySelectorAll('.pill[data-group="mood"]').forEach(p => p.classList.remove('active'));
      pill.classList.toggle('active');
      state.mood = pill.classList.contains('active') ? val : '';
    } else {
      pill.classList.toggle('active');
      if (pill.classList.contains('active')) {
        state.interests.push(val);
      } else {
        state.interests = state.interests.filter(i => i !== val);
      }
      interestCount.textContent = state.interests.length
        ? `${state.interests.length} selected`
        : '0 selected';
    }
  });
});

/* ── Generate ────────────────────────────────────────────── */
generateBtn.addEventListener('click', fetchRecommendations);
regenerateBtn.addEventListener('click', fetchRecommendations);

async function fetchRecommendations() {
  if (!state.interests.length && !state.mood) {
    showError('Please select at least one interest or mood.');
    return;
  }

  showState('loading');
  generateBtn.disabled = true;

  try {
    const res  = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interests: state.interests, mood: state.mood }),
    });
    const data = await res.json();

    if (!res.ok || data.error) {
      showError(data.error || 'Something went wrong. Try again.');
      return;
    }

    renderCards(data.recommendations, data.model);
    showState('results');

  } catch (err) {
    showError('Could not connect to the server. Is Flask running?');
  } finally {
    generateBtn.disabled = false;
  }
}

/* ── Render cards ────────────────────────────────────────── */
function renderCards(recs, model) {
  cardsGrid.innerHTML = '';

  if (model) {
    document.getElementById('modelBadge').textContent = model;
  }

  recs.forEach((r, i) => {
    const card = document.createElement('div');
    card.className = 'rec-card';
    card.style.animationDelay = `${i * 0.07}s`;

    const tags = (r.tags || []).map(t => `<span class="card-tag">${t}</span>`).join('');
    const score = Math.min(99, Math.max(60, parseInt(r.matchScore) || 80));

    card.innerHTML = `
      <div class="card-cat">${r.category || 'General'}</div>
      <div class="card-title">${r.title || 'Untitled'}</div>
      <div class="card-desc">${r.description || ''}</div>
      ${tags ? `<div class="card-tags">${tags}</div>` : ''}
      <div class="card-score">
        <span class="score-label">${score}%</span>
        <div class="score-bar">
          <div class="score-fill" data-score="${score}"></div>
        </div>
        <span style="font-size:0.72rem;color:var(--muted)">match</span>
      </div>
    `;
    cardsGrid.appendChild(card);
  });

  /* Animate score bars after paint */
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.querySelectorAll('.score-fill').forEach(bar => {
        bar.style.width = bar.dataset.score + '%';
      });
    });
  });
}

/* ── State helper ────────────────────────────────────────── */
function showState(which) {
  [loadingState, emptyState, errorState, resultsSection].forEach(el => {
    el.classList.remove('visible');
  });
  if (which === 'loading')  loadingState.classList.add('visible');
  if (which === 'empty')    emptyState.classList.add('visible');
  if (which === 'error')    errorState.classList.add('visible');
  if (which === 'results')  resultsSection.classList.add('visible');
}

function showError(msg) {
  document.getElementById('errorMsg').textContent = msg;
  showState('error');
}
