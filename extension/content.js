// DemandRadar Scout — Content Script
// Injects a sidebar showing related painpoints when browsing supported sites.

const API_BASE = 'https://demandradar.app/api';

(function() {
  if (document.getElementById('dr-scout-sidebar')) return;

  // Create sidebar container
  const sidebar = document.createElement('div');
  sidebar.id = 'dr-scout-sidebar';
  sidebar.innerHTML = `
    <div class="dr-header">
      <span class="dr-logo">DemandRadar</span>
      <button class="dr-close" title="Close">x</button>
    </div>
    <div class="dr-body">
      <div class="dr-loading">Analyzing page context...</div>
    </div>
  `;
  document.body.appendChild(sidebar);

  // Close button
  sidebar.querySelector('.dr-close').addEventListener('click', () => {
    sidebar.classList.add('dr-collapsed');
  });

  // Extract page context
  const pageTitle = document.title || '';
  const pageText = (document.body.innerText || '').slice(0, 2000);

  // Fetch related painpoints
  fetch(`${API_BASE}/painpoints?limit=5&order=score`)
    .then(r => r.json())
    .then(data => {
      const items = data.items || [];
      if (items.length === 0) {
        sidebar.querySelector('.dr-body').innerHTML =
          '<div class="dr-empty">No insights yet. Check back after the next pipeline run.</div>';
        return;
      }
      let html = '<div class="dr-insights">';
      html += '<div class="dr-section-title">Top Pain Points</div>';
      items.forEach(pp => {
        const score = pp.total_score ? Math.round(pp.total_score) : '?';
        html += `
          <a href="https://demandradar.app/radar" target="_blank" class="dr-card">
            <div class="dr-card-score">${score}</div>
            <div class="dr-card-body">
              <div class="dr-card-pain">${escapeHtml(pp.pain)}</div>
              <div class="dr-card-meta">${escapeHtml(pp.target_user || '')} ${escapeHtml(pp.frequency_signal || '')}</div>
            </div>
          </a>
        `;
      });
      html += '</div>';
      html += `<div class="dr-footer"><a href="https://demandradar.app" target="_blank">Open DemandRadar</a></div>`;
      sidebar.querySelector('.dr-body').innerHTML = html;
    })
    .catch(() => {
      sidebar.querySelector('.dr-body').innerHTML =
        '<div class="dr-error">Unable to load insights. Try again later.</div>';
    });

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
})();
