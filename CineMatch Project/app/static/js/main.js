/* ═══════════════════════════════════════════════════
   CineMatch — main.js
   ═══════════════════════════════════════════════════ */

/* ── Navbar scroll effect ─────────────────────────── */
(function () {
  const navbar = document.getElementById('cmNavbar');
  if (!navbar) return;
  const update = () =>
    navbar.classList.toggle('scrolled', window.scrollY > 40);
  window.addEventListener('scroll', update, { passive: true });
  update();
})();

/* ── Mobile menu toggle ───────────────────────────── */
(function () {
  const btn  = document.getElementById('mobileMenuBtn');
  const menu = document.getElementById('mobileMenu');
  if (!btn || !menu) return;
  btn.addEventListener('click', () => {
    menu.classList.toggle('open');
    btn.setAttribute('aria-expanded', menu.classList.contains('open'));
  });
})();

/* ── Horizontal drag-to-scroll rows ─────────────────
   Attach to every .row-scroll element.               */
(function () {
  document.querySelectorAll('.row-scroll').forEach(el => {
    let isDown = false, startX, scrollLeft;

    el.addEventListener('mousedown', e => {
      isDown = true;
      el.classList.add('dragging');
      startX = e.pageX - el.offsetLeft;
      scrollLeft = el.scrollLeft;
    });
    el.addEventListener('mouseleave', () => {
      isDown = false;
      el.classList.remove('dragging');
    });
    el.addEventListener('mouseup', () => {
      isDown = false;
      el.classList.remove('dragging');
    });
    el.addEventListener('mousemove', e => {
      if (!isDown) return;
      e.preventDefault();
      const x    = e.pageX - el.offsetLeft;
      const walk = (x - startX) * 1.5;
      el.scrollLeft = scrollLeft - walk;
    });
  });
})();

/* ── Flash message auto-dismiss ──────────────────── */
(function () {
  document.querySelectorAll('.flash-msg').forEach(msg => {
    const closeBtn = msg.querySelector('.flash-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        msg.style.opacity = '0';
        msg.style.transform = 'translateX(20px)';
        msg.style.transition = 'opacity 0.3s, transform 0.3s';
        setTimeout(() => msg.remove(), 300);
      });
    }
    setTimeout(() => {
      if (!msg.parentNode) return;
      msg.style.opacity = '0';
      msg.style.transition = 'opacity 0.5s';
      setTimeout(() => msg.remove(), 500);
    }, 5000);
  });
})();

/* ── Onboarding star ratings ─────────────────────── */
(function () {
  const form = document.getElementById('onboardingForm');
  if (!form) return;

  const ratings = {}; // movie_id -> score

  document.querySelectorAll('.star-inline').forEach(widget => {
    const movieId = widget.dataset.movieId;
    const stars = widget.querySelectorAll('.s');

    stars.forEach((star, idx) => {
      star.addEventListener('mouseenter', () => {
        stars.forEach((s, i) =>
          s.classList.toggle('hover', i <= idx));
      });
      star.addEventListener('mouseleave', () => {
        stars.forEach(s => s.classList.remove('hover'));
        const cur = ratings[movieId] || 0;
        stars.forEach((s, i) =>
          s.classList.toggle('on', i < cur));
      });
      star.addEventListener('click', () => {
        const score = idx + 1;
        ratings[movieId] = score;
        stars.forEach((s, i) => {
          s.classList.toggle('on', i < score);
          s.classList.remove('hover');
        });
        updateSubmitBtn();
      });
    });
  });

  function updateSubmitBtn() {
    const btn = document.getElementById('onboardingSubmit');
    if (!btn) return;
    const count = Object.keys(ratings).length;
    btn.textContent = count
      ? `Save ${count} rating${count > 1 ? 's' : ''} & Get Recommendations`
      : 'Rate at least 1 movie';
    btn.disabled = count === 0;
  }
  updateSubmitBtn();

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('onboardingSubmit');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    const entries = Object.entries(ratings);
    for (const [movieId, score] of entries) {
      await fetch(`/movies/${movieId}/rate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ score })
      });
    }
    window.location.reload();
  });
})();

/* ── Watchlist toggle (detail page) ─────────────────
   Expects globals: WATCHLIST_URL, IS_IN_WATCHLIST    */
function toggleWatchlist() {
  if (typeof WATCHLIST_URL === 'undefined') return;
  fetch(WATCHLIST_URL, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (!data.success) return;
      const btn = document.getElementById('watchlistBtn');
      if (!btn) return;
      if (data.in_watchlist) {
        btn.classList.add('in-list');
        btn.innerHTML = '&#10003; In My List';
      } else {
        btn.classList.remove('in-list');
        btn.innerHTML = '+ My List';
      }
    });
}

/* ── Star rating widget (detail page) ───────────────
   Expects globals: RATE_URL, currentScore            */
(function () {
  const widget = document.getElementById('starWidget');
  if (!widget) return;

  const stars = widget.querySelectorAll('.sw-star');
  if (!stars.length) return;

  let score = typeof currentScore !== 'undefined' ? currentScore : 0;

  function paint(n) {
    stars.forEach((s, i) => s.classList.toggle('on', i < n));
  }
  paint(score);

  stars.forEach((star, idx) => {
    star.addEventListener('mouseenter', () => paint(idx + 1));
    star.addEventListener('mouseleave', () => paint(score));
    star.addEventListener('click', () => {
      const newScore = idx + 1;
      fetch(RATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ score: newScore })
      })
        .then(r => r.json())
        .then(data => {
          if (!data.success) return;
          score = newScore;
          paint(score);
          const hint = document.getElementById('ratingHint');
          if (hint) hint.textContent = `Your rating: ${score}/5`;
          const avgEl = document.getElementById('avgScore');
          if (avgEl && Number.isFinite(data.avg_rating))
            avgEl.textContent = data.avg_rating.toFixed(1);
          const msg = document.getElementById('recUpdateMsg');
          if (msg) {
            msg.style.display = 'block';
            clearTimeout(msg._t);
            msg._t = setTimeout(() => { msg.style.display = 'none'; }, 6000);
          }
        });
    });
  });
})();

/* ── Dashboard watchlist remove ─────────────────── */
function removeWatchlist(movieId) {
  fetch(`/dashboard/watchlist/${movieId}/remove`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (!data.success) return;
      const el = document.getElementById('wl-' + movieId);
      if (el) {
        el.style.transition = 'opacity 0.3s, transform 0.3s';
        el.style.opacity = '0';
        el.style.transform = 'translateX(20px)';
        setTimeout(() => el.remove(), 320);
      }
    });
}

/* ── Catalog genre filter ───────────────────────── */
(function () {
  document.querySelectorAll('.genre-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.genre-pill').forEach(b =>
        b.classList.remove('active'));
      btn.classList.add('active');
      const genre = btn.dataset.genre;
      document.querySelectorAll('.movie-item').forEach(item => {
        item.style.display =
          (genre === 'all' || item.dataset.genre === genre) ? '' : 'none';
      });
    });
  });
})();
