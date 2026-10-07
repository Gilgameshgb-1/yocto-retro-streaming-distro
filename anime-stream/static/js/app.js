'use strict';

/* Anime library client.
   Five views swap in place, same shape as the movie remote: library, series
   detail, nyaa search, TV remote, phone player. Secondary actions (play on
   phone, mark watched, rename, cancel a download) live in one bottom sheet so
   the screens themselves stay as clean as the mockups. */

const VIEWS = ['library-view', 'series-view', 'download-view', 'remote-view', 'stream-view'];

const SORTS = [
    { key: 'added',   label: 'Recently added' },
    { key: 'watched', label: 'Last watched' },
    { key: 'title',   label: 'A–Z' },
];

const state = {
    library: readBootData(),   // series list, as /api/library returns it
    statusFilter: 'all',
    sort: 0,                   // index into SORTS
    flipped: null,             // slug of the grid card showing its info side
    series: null,              // series open in the detail view (with episodes)
    season: null,              // selected season tab
    playing: null,             // { path, series } loaded on the TV
    streaming: null,           // path playing in the phone player
    duration: 0,               // of what is on the TV, for the seek preview
    statusTimer: null,
    dlTimer: null,
    seeking: false,
    seekLock: 0,
    tracksOpen: readPref('tracksOpen', true),
    downloadsEnabled: document.body.dataset.downloadsEnabled === 'true',
};

/* ── Small helpers ───────────────────────────────────────────────────── */
function $(id) { return document.getElementById(id); }

function esc(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function icon(name, cls = '') {
    return `<svg${cls ? ` class="${cls}"` : ''}><use href="#i-${name}"/></svg>`;
}

function readBootData() {
    try {
        return JSON.parse($('boot-data').textContent) || [];
    } catch {
        return [];
    }
}

// Per-device UI preferences only; the app works the same without storage.
function readPref(key, fallback) {
    try {
        const raw = localStorage.getItem('anime.' + key);
        return raw == null ? fallback : JSON.parse(raw);
    } catch {
        return fallback;
    }
}

function writePref(key, value) {
    try { localStorage.setItem('anime.' + key, JSON.stringify(value)); } catch { /* ignore */ }
}

async function getJSON(url) {
    return (await fetch(url)).json();
}

async function postJSON(url, body) {
    return (await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
    })).json();
}

function posterUrl(slug) {
    return '/poster/' + encodeURIComponent(slug);
}

function initials(title) {
    return (title || '?').split(/[\s\-_.]+/).filter(Boolean).slice(0, 2)
        .map(w => w[0].toUpperCase()).join('');
}

function showView(id) {
    VIEWS.forEach(v => $(v).classList.toggle('active', v === id));
    document.querySelector('.view.active .scroll-area')?.scrollTo(0, 0);
}

function currentView() {
    return VIEWS.find(v => $(v).classList.contains('active'));
}

function toast(message, ms = 2600) {
    const el = $('toast');
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, ms);
}

/* ── Formatting ──────────────────────────────────────────────────────── */
function fmtSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let n = bytes;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${units[i]}`;
}

function fmtRate(bytesPerSecond) {
    return fmtSize(bytesPerSecond) + '/s';
}

// 14:02, or 1:04:09 past the hour — the player clock format.
function fmtClock(seconds) {
    seconds = Math.max(0, Math.round(seconds || 0));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = String(seconds % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

function fmtMinutes(seconds) {
    return `${Math.max(1, Math.round(seconds / 60))} min`;
}

function fmtEta(seconds) {
    if (seconds < 60) return `${Math.max(1, Math.round(seconds))} s left`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes} min left`;
    return `${Math.floor(minutes / 60)} h ${minutes % 60} min left`;
}

// AniList scores are out of 100; the mockups show them out of 10.
function fmtScore(score) {
    return (score / 10).toFixed(1);
}

function pad2(n) {
    return String(n).padStart(2, '0');
}

// "episode 3" in a sentence; the raw label for files with no number.
function epName(ep) {
    return ep.episode != null ? `episode ${ep.episode}` : ep.label;
}

/* ── Bottom sheet ────────────────────────────────────────────────────── */
function openSheet({ title, sub = '', actions }) {
    $('sheet-title').textContent = title;
    $('sheet-sub').textContent = sub;
    openSheet._actions = actions;
    $('sheet-actions').innerHTML = actions.map((a, i) => `
        <button class="wide-btn ${a.style || 'raised'}" data-action="sheet-pick" data-index="${i}">
            ${a.icon ? icon(a.icon) : ''}${esc(a.label)}
        </button>`).join('')
        + '<button class="wide-btn cancel" data-action="sheet-close">Cancel</button>';
    $('sheet').hidden = false;
}

function closeSheet() {
    $('sheet').hidden = true;
    openSheet._actions = null;
}

function pickSheet(index) {
    const action = (openSheet._actions || [])[index];
    closeSheet();
    if (action) action.run();
}

/* ── Modal ───────────────────────────────────────────────────────────── */
function askConfirm({ title, message, confirmLabel = 'Confirm', checkLabel = null,
                      inputValue = null }) {
    return new Promise(resolve => {
        const modal = $('modal');
        $('modal-title').textContent = title;
        $('modal-msg').textContent = message;

        const box = $('modal-check');
        box.checked = false;
        $('modal-check-row').hidden = !checkLabel;
        if (checkLabel) $('modal-check-label').textContent = checkLabel;

        const input = $('modal-input');
        $('modal-input-row').hidden = inputValue === null;
        $('modal-suggestions').innerHTML = '';
        if (inputValue !== null) input.value = inputValue;

        const confirmBtn = $('modal-confirm');
        confirmBtn.textContent = confirmLabel;

        const done = value => {
            modal.hidden = true;
            confirmBtn.onclick = null;
            askConfirm._cancel = null;
            resolve(value);
        };
        confirmBtn.onclick = () => done({
            ok: true,
            checked: box.checked,
            value: input.value.trim(),
        });
        askConfirm._cancel = () => done({ ok: false, checked: false, value: null });
        modal.hidden = false;
    });
}

/* Offer AniList's canonical titles as one-tap folder names. Scene releases
   carry episode titles the parser cannot strip, so this is how a bad guess
   gets fixed without typing. */
async function loadFolderSuggestions(parsedTitle) {
    let data;
    try {
        data = await getJSON('/api/resolve-title?q=' + encodeURIComponent(parsedTitle));
    } catch { return; }

    const container = $('modal-suggestions');
    const input = $('modal-input');
    if (!data.suggestions || !data.suggestions.length) return;

    const fresh = data.suggestions.filter(s => s && s !== input.value);
    if (!fresh.length) return;

    container.innerHTML = '<span class="label" style="width:100%;margin:2px 0 0">From AniList</span>' +
        fresh.map(s => `<button class="pill" data-name="${esc(s)}">${esc(s)}</button>`).join('');
    container.querySelectorAll('.pill').forEach(pill => {
        pill.onclick = () => { input.value = pill.dataset.name; };
    });
}

function closeModal() {
    if (askConfirm._cancel) askConfirm._cancel();
    else $('modal').hidden = true;
}

/* ── Library ─────────────────────────────────────────────────────────── */
function seriesStatus(s) {
    if (s.fully_watched) return 'done';
    return s.in_progress ? 'watching' : 'new';
}

function sortedLibrary() {
    const list = state.library.slice();
    const key = SORTS[state.sort].key;
    if (key === 'title') {
        list.sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' }));
    } else if (key === 'watched') {
        list.sort((a, b) => (b.last_watched - a.last_watched) || (b.added - a.added));
    } else {
        list.sort((a, b) => b.added - a.added);
    }
    return list;
}

function renderLibrary() {
    const needle = $('library-filter').value.trim().toLowerCase();
    const list = sortedLibrary().filter(s =>
        (state.statusFilter === 'all' || seriesStatus(s) === state.statusFilter)
        && (!needle || s.title.toLowerCase().includes(needle)
                    || s.folder.toLowerCase().includes(needle)));

    $('series-grid').innerHTML = list.map(renderCard).join('');
    document.querySelector('[data-status="all"]').textContent = `All · ${state.library.length}`;
    $('sort-label').textContent = SORTS[state.sort].label;

    const empty = $('library-empty');
    empty.hidden = list.length > 0;
    empty.innerHTML = state.library.length
        ? 'Nothing here matches.'
        : 'Nothing in the library yet.<br>Hit <b>Download anime</b> to search nyaa, '
          + 'or drop files into the library folder and reload.';

    // The continue card is a shortcut, so it only shows on the unfiltered view.
    if (!needle && state.statusFilter === 'all') renderContinue();
    else $('continue-slot').innerHTML = '';
}

function renderCard(s) {
    const meta = s.meta || {};
    const classes = ['card'];
    if (seriesStatus(s) === 'watching') classes.push('watching');
    if (state.flipped === s.slug) classes.push('flipped');

    const badge = `<span class="badge">${s.fully_watched ? icon('check') : ''}`
                + `${s.watched_count}/${s.episode_count}</span>`;
    const front = s.has_poster
        ? `<div class="card-face front"><img src="${posterUrl(s.slug)}" alt="" loading="lazy">${badge}</div>`
        : `<div class="card-face front empty"><span>${esc(s.title)}</span>${badge}</div>`;

    const facts = [meta.year, (meta.genres || [])[0]].filter(Boolean).join(' · ');
    const back = `
        <div class="card-face back">
            ${meta.score
                ? `<div class="score">${icon('star')}${fmtScore(meta.score)}</div>`
                : `<div class="score" style="font-size:14px">${esc(s.title)}</div>`}
            ${facts ? `<div class="back-facts">${esc(facts)}</div>` : ''}
            <div class="back-synopsis">${esc(meta.synopsis || `${s.episode_count} episodes on disk.`)}</div>
            <button class="back-play" data-action="resume-series" data-slug="${esc(s.slug)}">
                ${icon('play')} Play
            </button>
        </div>`;

    return `
        <article class="${classes.join(' ')}" data-action="card" data-slug="${esc(s.slug)}">
            <div class="card-inner">${front}${back}</div>
        </article>`;
}

// First tap turns a poster over to its info side; a second tap opens it.
function tapCard(card) {
    const slug = card.dataset.slug;
    if (state.flipped === slug) {
        openSeries(slug);
        return;
    }
    document.querySelectorAll('.card.flipped').forEach(c => c.classList.remove('flipped'));
    card.classList.add('flipped');
    state.flipped = slug;
}

function continueTarget() {
    if (state.playing) {
        const slug = state.playing.series.slug;
        const listed = state.library.find(s => s.slug === slug);
        const ep = findEpisode(state.playing.path, state.playing.series);
        return { series: listed || state.playing.series, episode: ep, live: true };
    }
    const candidates = state.library.filter(s => s.in_progress && s.resume);
    if (!candidates.length) return null;
    candidates.sort((a, b) => b.last_watched - a.last_watched);
    return { series: candidates[0], episode: candidates[0].resume, live: false };
}

function renderContinue() {
    const slot = $('continue-slot');
    const target = continueTarget();
    if (!target || !target.episode) { slot.innerHTML = ''; return; }

    const { series: s, episode: ep, live } = target;
    const left = ep.duration && ep.resume_time
        ? `${fmtClock(ep.duration - ep.resume_time)} left`
        : 'Up next';

    slot.innerHTML = `
        <div class="continue" data-action="open-series" data-slug="${esc(s.slug)}">
            ${s.has_poster
                ? `<img class="thumb" src="${posterUrl(s.slug)}" alt="">`
                : `<div class="thumb thumb-fallback">${esc(initials(s.title))}</div>`}
            <div class="continue-body">
                <span class="label">${live ? 'Now playing on TV' : 'Continue watching'}</span>
                <div class="continue-title">${esc(s.title)}</div>
                <div class="continue-sub">${esc(ep.label)} · ${esc(left)}</div>
                <div class="bar"><i style="width:${ep.progress_pct || 0}%"></i></div>
            </div>
            <button class="play-dot" aria-label="${live ? 'Open remote' : 'Resume on TV'}"
                    data-action="${live ? 'show-remote' : 'resume-series'}" data-slug="${esc(s.slug)}">
                ${icon('play')}
            </button>
        </div>`;
}

async function refreshLibrary() {
    try {
        state.library = await getJSON('/api/library');
    } catch { return; }
    renderLibrary();
}

function goLibrary() {
    showView('library-view');
    refreshLibrary();
    syncNowPlaying();
}

/* ── Series detail ───────────────────────────────────────────────────── */
async function loadSeries(slug) {
    const series = await getJSON(`/api/series/${encodeURIComponent(slug)}`);
    if (!series || series.error) throw new Error('not found');
    return series;
}

/* `stay` re-renders in place (after marking an episode watched, say) without
   jumping back to the top or resetting the season tab. */
async function openSeries(slug, { stay = false } = {}) {
    let series;
    try {
        series = await loadSeries(slug);
    } catch {
        toast('Could not load that series');
        return;
    }

    const keepSeason = stay && state.series?.slug === series.slug
                       && series.season_numbers.includes(state.season);
    state.series = series;
    if (!keepSeason) {
        const resumeSeason = series.resume ? (series.resume.season ?? 1) : null;
        state.season = series.season_numbers.includes(resumeSeason)
            ? resumeSeason : (series.season_numbers[0] ?? 1);
    }

    renderSeries();
    if (!stay) showView('series-view');

    // No cached metadata yet (hand-copied folder) — try AniList once, quietly.
    if (!stay && (!series.meta || !series.meta.anilist_id)) fetchMeta(slug, false);
}

function seriesTags(s) {
    const eps = s.episodes || [];
    const counts = {};
    eps.forEach(e => { if (e.resolution) counts[e.resolution] = (counts[e.resolution] || 0) + 1; });
    const resolution = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];

    const subLangs = [...new Set(eps.flatMap(e => e.subs.map(sub => sub.label.toUpperCase())))];

    return [
        resolution ? (resolution === '2160p' ? '4K' : resolution) : null,
        eps.some(e => e.dual_audio) ? 'Dual audio' : null,
        eps.some(e => e.hdr) ? 'HDR' : null,
        ...subLangs.slice(0, 2).map(l => (l === 'SUBTITLES' ? 'Subtitles' : `${l} subs`)),
    ].filter(Boolean);
}

function renderSeries() {
    const s = state.series;
    const meta = s.meta || {};
    $('series-heading').textContent = s.title;

    const facts = [meta.year, ...(meta.genres || []).slice(0, 2)].filter(Boolean).join(' · ');
    const tags = seriesTags(s);

    $('series-hero').innerHTML = `
        ${s.has_poster
            ? `<div class="hero-poster"><img src="${posterUrl(s.slug)}" alt=""></div>`
            : `<div class="hero-poster empty">${esc(s.title)}</div>`}
        <div class="hero-info">
            ${meta.score ? `<div class="score">${icon('star')}${fmtScore(meta.score)}</div>` : ''}
            ${facts ? `<p class="hero-facts">${esc(facts)}</p>` : ''}
            ${tags.length ? `<div class="tags">${tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : ''}
            ${meta.synopsis
                ? `<p class="synopsis" data-action="toggle-synopsis">${esc(meta.synopsis)}</p>`
                : `<p class="hero-facts">${s.episode_count} episodes · ${fmtSize(s.total_bytes)}</p>`}
        </div>`;

    // One big button: resume, start, or go round again.
    const resume = s.resume;
    let label;
    let path;
    if (resume && resume.started) {
        label = `Resume ${epName(resume)} · ${fmtClock(resume.resume_time)}`;
        path = resume.path;
    } else if (resume) {
        label = `Play ${epName(resume)}`;
        path = resume.path;
    } else {
        label = 'Watch again from the start';
        path = s.episodes[0]?.path;
    }
    $('series-cta').innerHTML = path
        ? `<button class="wide-btn coral glow" data-action="play-tv" data-path="${esc(path)}">
               ${icon('play', 'sm')} ${esc(label)}
           </button>`
        : '';

    $('watched-note').textContent = `${s.watched_count} of ${s.episode_count} watched`;

    $('season-tabs').innerHTML = s.season_numbers.length > 1
        ? s.season_numbers.map(n => `
            <button class="pill ${n === state.season ? 'active' : ''}"
                    data-action="pick-season" data-season="${n}">Season ${n}</button>`).join('')
        : '';

    renderEpisodes();
}

function renderEpisodes() {
    const s = state.series;
    const meta = s.meta || {};
    const list = s.seasons[String(state.season)] || s.episodes || [];
    const current = s.resume?.path;

    $('episode-list').innerHTML = list.map(ep => {
        const isCurrent = ep.path === current;
        const runtime = ep.duration || (meta.duration ? meta.duration * 60 : 0);
        const length = runtime ? fmtMinutes(runtime) : fmtSize(ep.size_bytes);
        const position = ep.duration
            ? `${fmtClock(ep.resume_time)} / ${fmtClock(ep.duration)}`
            : fmtClock(ep.resume_time);

        let sub;
        if (ep.watched) sub = `${length} · Watched`;
        else if (ep.started) sub = position + (isCurrent ? ' · Up next' : '');
        else sub = length + (isCurrent ? ' · Up next' : '');

        const cls = ep.watched ? 'watched' : (isCurrent ? 'current' : '');
        const tile = ep.watched ? icon('check')
                   : isCurrent ? icon('play')
                   : esc(ep.episode != null ? ep.episode : '•');

        return `
            <div class="ep ${cls}" role="button" tabindex="0"
                 data-action="episode" data-path="${esc(ep.path)}">
                <div class="ep-tile">${tile}</div>
                <div class="ep-body">
                    <div class="ep-title">${esc(ep.label)}</div>
                    <div class="ep-sub">${esc(sub)}</div>
                </div>
                ${ep.started ? `<div class="bar"><i style="width:${ep.progress_pct}%"></i></div>` : ''}
            </div>`;
    }).join('') || '<p class="empty-state">No episodes in this season.</p>';
}

function findEpisode(path, series = state.series) {
    return (series?.episodes || []).find(e => e.path === path) || null;
}

function episodeSheet(path) {
    const ep = findEpisode(path);
    if (!ep) return;
    const bits = [fmtSize(ep.size_bytes), ep.filename];
    if (ep.warning) bits.unshift(ep.warning);

    openSheet({
        title: ep.label,
        sub: bits.join(' · '),
        actions: [
            {
                label: ep.started ? `Resume on TV · ${fmtClock(ep.resume_time)}` : 'Play on TV',
                icon: 'tv', style: 'coral', run: () => playOnTV(path),
            },
            { label: 'Watch on this phone', icon: 'phone', run: () => openStream(path) },
            {
                label: ep.watched ? 'Mark as unwatched' : 'Mark as watched',
                icon: 'check', run: () => toggleWatched(path, !ep.watched),
            },
            { label: 'Delete file', icon: 'x', style: 'danger', run: () => deleteEpisode(path) },
        ],
    });
}

function seriesMenu() {
    const s = state.series;
    if (!s) return;
    openSheet({
        title: s.title,
        sub: `${s.episode_count} files · ${fmtSize(s.total_bytes)} · folder “${s.folder}”`,
        actions: [
            { label: 'Rename series folder', run: renameSeries },
            { label: 'Refresh info from AniList', run: () => fetchMeta(s.slug, true) },
            { label: 'Delete series', icon: 'x', style: 'danger', run: deleteSeries },
        ],
    });
}

async function deleteEpisode(path) {
    const s = state.series;
    const ep = findEpisode(path);
    if (!s || !ep) return;
    const last = s.episodes.length === 1;

    // Files with no episode number are labelled with their whole filename,
    // which the message already shows.
    const name = ep.episode != null ? ep.label : 'this file';
    const answer = await askConfirm({
        title: `Delete ${name}?`,
        message: `${ep.filename} (${fmtSize(ep.size_bytes)}) is removed from the drive`
            + (ep.subs.length ? ', with its subtitle files' : '') + '. '
            + (last ? 'It is the last file, so the series leaves the library too. ' : '')
            + 'This cannot be undone.',
        confirmLabel: 'Delete',
    });
    if (!answer.ok) return;

    let r;
    try {
        r = await postJSON('/api/episode/delete', { file: path });
    } catch {
        toast('Could not delete that file');
        return;
    }
    if (!r.ok) { toast(r.error || 'Could not delete that file', 5000); return; }

    toast(`Deleted ${ep.episode != null ? ep.label : 'file'} · ${fmtSize(r.bytes)} freed`);
    if (r.series_gone) goLibrary();
    else await openSeries(s.slug, { stay: true });
}

async function deleteSeries() {
    const s = state.series;
    if (!s) return;

    const answer = await askConfirm({
        title: `Delete ${s.title}?`,
        message: `All ${s.episode_count} file${s.episode_count === 1 ? '' : 's'} `
            + `(${fmtSize(s.total_bytes)}) in “${s.folder}” are removed from the drive, `
            + 'along with the watch progress. This cannot be undone.',
        confirmLabel: 'Delete series',
    });
    if (!answer.ok) return;

    let r;
    try {
        r = await postJSON(`/api/series/${encodeURIComponent(s.slug)}/delete`, {});
    } catch {
        toast('Could not delete that series');
        return;
    }
    if (!r.ok) { toast(r.error || 'Could not delete that series', 5000); return; }

    toast(`Deleted ${s.title} · ${fmtSize(r.bytes)} freed`);
    state.series = null;
    state.flipped = null;
    goLibrary();
}

function pickSeason(n) {
    state.season = n;
    renderSeries();
}

async function toggleWatched(path, watched) {
    await postJSON('/api/watched', { file: path, watched: Boolean(watched) });
    await openSeries(state.series.slug, { stay: true });
}

async function fetchMeta(slug, force) {
    try {
        const r = await getJSON(`/api/meta/${encodeURIComponent(slug)}${force ? '?force=1' : ''}`);
        if (r.found) {
            if (state.series?.slug === slug && currentView() === 'series-view') {
                await openSeries(slug, { stay: true });
            }
            if (force) toast('Info refreshed from AniList');
        } else if (force) {
            toast('AniList had no match for that title');
        }
    } catch {
        if (force) toast('Could not reach AniList');
    }
}

async function renameSeries() {
    if (!state.series) return;
    const current = state.series.folder;

    const dialog = askConfirm({
        title: 'Rename series',
        message: 'Renames the folder on disk and carries watch progress and '
               + 'artwork across.',
        confirmLabel: 'Rename',
        inputValue: current,
    });
    loadFolderSuggestions(current);
    const answer = await dialog;
    if (!answer.ok || !answer.value || answer.value === current) return;

    let result;
    try {
        result = await postJSON(`/api/series/${encodeURIComponent(state.series.slug)}/rename`,
                                { name: answer.value });
    } catch {
        toast('Rename failed');
        return;
    }

    if (!result.ok) { toast(result.error || 'Rename failed', 4000); return; }
    toast(`Renamed to “${result.folder}”`);
    await openSeries(result.slug, { stay: true });
    refreshLibrary();
}

/* ── Nyaa search ─────────────────────────────────────────────────────── */
function openDownloads() {
    showView('download-view');
    refreshDownloads();
    if (!state.downloadsEnabled) {
        toast('Search works, but downloading needs python3-libtorrent', 4200);
        return;
    }
    // On the Pi: say up front if the SSD is missing, not only after a tap.
    getJSON('/api/health')
        .then(h => { if (h.storage_problem) toast(h.storage_problem, 6000); })
        .catch(() => {});
}

function closeDownloads() {
    stopDownloadPolling();
    goLibrary();
}

document.querySelectorAll('.filter-group').forEach(group => {
    group.querySelectorAll('.pill').forEach(pill => {
        pill.onclick = () => {
            group.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            if ($('nyaa-query').value.trim()) runSearch();
        };
    });
});

$('nyaa-form').addEventListener('submit', event => {
    event.preventDefault();
    $('nyaa-query').blur();          // drop the phone keyboard
    runSearch();
});

function readFilters() {
    const pick = name => {
        const group = document.querySelector(`.filter-group[data-filter="${name}"]`);
        return group?.querySelector('.pill.active')?.dataset.value ?? '';
    };
    return {
        sort: pick('sort') || 'seeders',
        resolution: pick('resolution'),
        batch: pick('batch') || 'any',
        trusted: pick('trusted'),
        min_gb: pick('min_gb'),
    };
}

async function runSearch() {
    const query = $('nyaa-query').value.trim();
    if (!query) return;

    const results = $('search-results');
    const meta = $('search-meta');
    meta.textContent = 'Searching nyaa.si…';
    results.innerHTML = '';

    const filters = readFilters();
    const params = new URLSearchParams({
        q: query, batch: filters.batch, min_seeders: '1', sort: filters.sort,
    });
    if (filters.resolution) params.set('resolution', filters.resolution);
    if (filters.trusted) params.set('trusted', '1');
    if (filters.min_gb) params.set('min_gb', filters.min_gb);

    let data;
    try {
        data = await getJSON('/api/search?' + params);
    } catch {
        meta.textContent = 'Network error reaching nyaa.si';
        return;
    }

    if (data.error) {
        meta.textContent = data.error;
        return;
    }

    const SORT_WORDS = {
        seeders: 'most seeders first', newest: 'newest first',
        smallest: 'smallest first', largest: 'largest first',
    };
    // nyaa's feed is a newest-first window of 75; we order that window.
    meta.textContent = `${data.shown} of ${data.total} results · `
        + `${SORT_WORDS[data.sort] || ''}, sorted within nyaa's latest ${data.total}`;

    results.innerHTML = data.results.length
        ? data.results.map(renderResult).join('')
        : '<p class="empty-state">Nothing matched. Try loosening the filters.</p>';
}

function renderResult(r) {
    const tags = [
        r.resolution ? `<span class="tag ${r.resolution === '2160p' ? 'hi' : ''}">${r.resolution === '2160p' ? '4K' : esc(r.resolution)}</span>` : '',
        r.codec ? `<span class="tag">${esc(r.codec)}</span>` : '',
        r.is_batch ? '<span class="tag">Batch</span>' : '',
        r.trusted ? '<span class="tag">Trusted</span>' : '',
        r.dual_audio ? '<span class="tag">Dual audio</span>' : '',
        r.hdr ? '<span class="tag">HDR</span>' : '',
        r.size_warning ? `<span class="tag warn">${esc(r.size_text)}</span>` : '',
    ].filter(Boolean).join('');

    const episode = r.ep_start != null
        ? `episodes ${r.ep_start}–${r.ep_end}`
        : (r.episode != null ? `episode ${r.episode}` : (r.is_batch ? 'full season' : 'single file'));

    const notes = [];
    if (r.warning) notes.push(`<p class="note ${r.codec === 'AV1' && r.resolution === '2160p' ? 'danger' : ''}">${esc(r.warning)}</p>`);
    if (r.likely_subs_only) notes.push(`<p class="note">Only ${esc(r.size_text)} — almost certainly a subtitle pack, not video.</p>`);
    if (r.size_warning) notes.push(`<p class="note">${esc(r.size_text)} is a large download. Check you have the space first.</p>`);

    const payload = esc(JSON.stringify({
        magnet: r.magnet, series: r.series_folder, release: r.raw_title,
    }));

    return `
        <article class="panel result">
            <div class="result-title">${esc(r.raw_title)}</div>
            <div class="result-series">→ ${esc(r.series_folder)} · ${esc(episode)}</div>
            ${tags ? `<div class="tags">${tags}</div>` : ''}
            ${notes.join('')}
            <div class="result-foot">
                <div class="result-stats">
                    <span class="seeds">▲ ${r.seeders}</span>
                    <span>▼ ${r.leechers}</span>
                    <span>${esc(r.size_text)}</span>
                    ${r.group ? `<span>${esc(r.group)}</span>` : ''}
                </div>
                <button class="get-btn" data-action="download" data-payload="${payload}"
                        ${state.downloadsEnabled ? '' : 'disabled'}>
                    ${icon('download')}${state.downloadsEnabled ? 'Get' : 'Off'}
                </button>
            </div>
        </article>`;
}

async function startDownload(button) {
    let payload;
    try {
        payload = JSON.parse(button.dataset.payload);
    } catch { return; }

    // The folder is a guess from the release name — let it be corrected before
    // anything is written to disk, so the library stays tidy.
    const dialog = askConfirm({
        title: 'Download this release?',
        message: payload.release,
        confirmLabel: 'Start download',
        inputValue: payload.series,
    });
    // Fire the lookup while the dialog is open, not after it resolves.
    loadFolderSuggestions(payload.series);
    const answer = await dialog;
    if (!answer.ok) return;
    if (answer.value) payload.series = answer.value;

    const original = button.innerHTML;
    button.disabled = true;
    button.textContent = 'Starting…';

    try {
        const r = await postJSON('/api/download', payload);
        if (r.error) {
            toast(r.error, 5000);
            button.disabled = false;
            button.innerHTML = original;
            return;
        }
        button.innerHTML = icon('check') + 'Queued';
        toast(`Downloading into “${r.series}”`);
        refreshDownloads();
    } catch {
        toast('Could not start the download');
        button.disabled = false;
        button.innerHTML = original;
    }
}

/* ── Downloads ───────────────────────────────────────────────────────── */
function dlKind(d) {
    if (d.state === 'error') return 'error';
    if (d.state === 'finished') return 'finished';
    return 'active';
}

const DL_STATES = {
    starting: 'Starting…',
    downloading_metadata: 'Finding peers…',
    checking_files: 'Checking files…',
    checking_resume_data: 'Checking files…',
    allocating: 'Allocating space…',
};

function dlBody(d) {
    const title = esc(d.series) + (d.detail ? ` · ${esc(d.detail)}` : '');
    const kind = dlKind(d);
    if (kind === 'finished') {
        return `<div class="dl-title">${title}</div>
                <div class="dl-foot"><span>Finished · added to library</span></div>`;
    }
    if (kind === 'error') {
        return `<div class="dl-title">${title}</div>
                <div class="dl-foot"><span>Error: ${esc(d.error || 'unknown')}</span></div>`;
    }

    const pct = Math.floor(d.progress || 0);
    let left = `${pct}%`;
    let right = '';
    if (d.paused) {
        left += ' · Paused';
    } else if (DL_STATES[d.state]) {
        left = DL_STATES[d.state];
    } else {
        left += ` · ${d.download_rate > 0 ? fmtRate(d.download_rate) : `${d.num_peers} peers`}`;
        if (d.eta_seconds) right = fmtEta(d.eta_seconds);
    }
    return `<div class="dl-title">${title}</div>
            <div class="bar"><i style="width:${d.progress || 0}%"></i></div>
            <div class="dl-foot"><span>${esc(left)}</span><span>${esc(right)}</span></div>`;
}

function dlEnd(d) {
    const kind = dlKind(d);
    if (kind === 'finished') return `<span class="dl-side">${icon('check')}</span>`;
    if (kind === 'error') return `<span class="dl-side">${icon('x')}</span>`;
    return `<button class="dl-side btn" data-action="dl-pause" data-id="${d.id}"
                    data-paused="${d.paused ? 'true' : 'false'}"
                    aria-label="${d.paused ? 'Resume' : 'Pause'}">${icon(d.paused ? 'play' : 'pause')}</button>`;
}

/* Rows are updated in place rather than re-rendered, so the poster thumbnail
   is not reloaded on every 2 s poll. */
function renderDownloads(list) {
    const container = $('downloads-list');
    state.downloads = list;
    if (!list.length) {
        container.innerHTML = '<p class="dl-empty">No active downloads</p>';
        return;
    }
    container.querySelector('.dl-empty')?.remove();

    const seen = new Set();
    list.forEach(d => {
        const id = String(d.id);
        seen.add(id);
        let row = container.querySelector(`[data-dl="${id}"]`);
        if (!row) {
            row = document.createElement('div');
            row.dataset.dl = id;
            row.dataset.action = 'download-row';
            row.dataset.id = id;
            row.innerHTML = `
                <img class="thumb" src="${posterUrl(d.slug)}" alt=""
                     data-fallback="${esc(initials(d.series))}">
                <div class="dl-body"></div>
                <div class="dl-end"></div>`;
            container.appendChild(row);
        }
        row.className = `dl ${dlKind(d)}`;
        row.querySelector('.dl-body').innerHTML = dlBody(d);
        row.querySelector('.dl-end').innerHTML = dlEnd(d);
    });
    container.querySelectorAll('[data-dl]').forEach(row => {
        if (!seen.has(row.dataset.dl)) row.remove();
    });
}

async function refreshDownloads() {
    let list;
    try {
        list = await getJSON('/api/downloads');
    } catch { return; }
    if (!Array.isArray(list)) return;

    renderDownloads(list);

    if (list.some(d => dlKind(d) === 'active')) {
        if (!state.dlTimer) state.dlTimer = setInterval(refreshDownloads, 2000);
    } else {
        stopDownloadPolling();
    }
}

function stopDownloadPolling() {
    if (state.dlTimer) { clearInterval(state.dlTimer); state.dlTimer = null; }
}

async function setPaused(id, paused) {
    const r = await postJSON('/api/downloads/pause', { id, paused });
    if (r && r.ok === false) toast(r.error || 'Could not change that download');
    refreshDownloads();
}

function downloadSheet(id) {
    const d = (state.downloads || []).find(x => x.id === id);
    if (!d) return;
    const kind = dlKind(d);
    const actions = [];

    if (kind === 'active') {
        actions.push({
            label: d.paused ? 'Resume download' : 'Pause download',
            icon: d.paused ? 'play' : 'pause', run: () => setPaused(id, !d.paused),
        });
        actions.push({ label: 'Cancel download', icon: 'x', style: 'danger', run: () => cancelDownload(id, d.series) });
    } else if (kind === 'finished') {
        actions.push({ label: 'Open series', icon: 'play', style: 'coral', run: () => openSeries(d.slug) });
        actions.push({ label: 'Remove from list', icon: 'x', run: () => removeDownload(id) });
    } else {
        actions.push({ label: 'Remove from list', icon: 'x', run: () => removeDownload(id) });
    }

    openSheet({ title: d.series, sub: d.release, actions });
}

async function cancelDownload(id, label) {
    const answer = await askConfirm({
        title: 'Cancel download?',
        message: `Stop downloading “${label}”.`,
        confirmLabel: 'Cancel download',
        checkLabel: 'Also delete the partial files it wrote',
    });
    if (!answer.ok) return;
    await postJSON('/api/downloads/cancel', { id, delete_files: answer.checked });
    refreshDownloads();
}

// Finished and errored entries: dropping them from the list deletes nothing.
async function removeDownload(id) {
    await postJSON('/api/downloads/cancel', { id, delete_files: false });
    refreshDownloads();
}

async function clearFinished() {
    await fetch('/api/downloads/clear', { method: 'POST' });
    refreshDownloads();
}

/* ── TV playback ─────────────────────────────────────────────────────── */
async function playOnTV(path, series = state.series) {
    let result;
    try {
        result = await getJSON('/api/play?file=' + encodeURIComponent(path));
    } catch {
        toast('Could not reach the player');
        return;
    }
    if (result.error) { toast(result.error, 5000); return; }

    state.playing = { path, series };
    if (result.resumed_at > 30) toast(`Resuming at ${fmtClock(result.resumed_at)}`);
    showRemote();
    setTimeout(loadTracks, 1200);     // give mpv a moment to open the file
}

// The Play button on a grid card and the continue card: resume where you were.
async function resumeSeries(slug) {
    let series;
    try {
        series = await loadSeries(slug);
    } catch {
        toast('Could not load that series');
        return;
    }
    const target = series.resume || series.episodes[0];
    if (!target) return;
    state.series = series;
    await playOnTV(target.path, series);
}

function episodeMeta(ep) {
    if (!ep) return '';
    const code = ep.episode != null ? `S${pad2(ep.season ?? 1)}E${pad2(ep.episode)}` : null;
    const quality = [ep.source, ep.resolution === '2160p' ? '4K' : ep.resolution].filter(Boolean).join(' ');
    const video = [ep.codec === 'H264' ? 'H.264' : ep.codec, ep.ten_bit ? '10-bit' : null].filter(Boolean).join(' ');
    return [code, quality, video, ep.dual_audio ? 'Dual audio' : null].filter(Boolean).join(' · ');
}

function renderRemote() {
    const { path, series } = state.playing;
    const ep = findEpisode(path, series);
    const episodes = series.episodes || [];
    const index = episodes.findIndex(e => e.path === path);

    $('remote-title').textContent = series.title;
    $('remote-episode').textContent = ep ? ep.label : '';
    $('remote-meta').textContent = episodeMeta(ep);

    const poster = $('remote-poster');
    poster.classList.toggle('empty', !series.has_poster);
    poster.innerHTML = series.has_poster
        ? `<img src="${posterUrl(series.slug)}" alt="">`
        : esc(series.title);

    document.querySelector('[data-action="prev-episode"]').disabled = index <= 0;
    document.querySelector('[data-action="next-episode"]').disabled =
        index < 0 || index >= episodes.length - 1;

    $('track-panel').hidden = !state.tracksOpen;
    $('cc-btn').classList.toggle('on', state.tracksOpen);
    setSeek(ep?.progress_pct || 0);
    $('remote-time').textContent = fmtClock(ep?.resume_time || 0);
    $('remote-duration').textContent = ep?.duration ? fmtClock(ep.duration) : '--:--';
}

function showRemote() {
    if (!state.playing) return;
    renderRemote();
    showView('remote-view');
    startStatusPolling();
    if (state.tracksOpen) loadTracks();
}

function stepEpisode(delta) {
    if (!state.playing) return;
    const { path, series } = state.playing;
    const episodes = series.episodes || [];
    const next = episodes[episodes.findIndex(e => e.path === path) + delta];
    if (next) playOnTV(next.path, series);
}

function sendCmd(action) {
    fetch('/files/' + action).catch(() => {});
}

function setPlayIcon(paused) {
    const button = document.querySelector('.play-big');
    button.classList.toggle('paused', paused);
    $('play-pause-icon').innerHTML = `<use href="#i-${paused ? 'play' : 'pause'}"/>`;
}

function togglePause() {
    sendCmd('play-pause');
    setPlayIcon(!document.querySelector('.play-big').classList.contains('paused'));
}

function startStatusPolling() {
    stopStatusPolling();
    const tick = async () => {
        if (currentView() !== 'remote-view') return;
        let s;
        try {
            s = await getJSON('/api/status');
        } catch { return; }
        if (!s.playing) return;
        state.duration = s.duration || 0;
        setPlayIcon(Boolean(s.paused));
        if (state.seeking || Date.now() < state.seekLock) return;

        setSeek(s.percent || 0);
        $('remote-time').textContent = fmtClock(s.position);
        $('remote-duration').textContent = s.duration ? fmtClock(s.duration) : '--:--';
    };
    tick();
    state.statusTimer = setInterval(tick, 1000);
}

function stopStatusPolling() {
    if (state.statusTimer) { clearInterval(state.statusTimer); state.statusTimer = null; }
}

function setSeek(pct) {
    $('seek-fill').style.width = pct + '%';
    $('seek-thumb').style.left = pct + '%';
}

/* Drag the thumb (or tap the track) to scrub. The poll is held off while the
   finger is down and for a moment after, so it does not snap the thumb back. */
(function wireSeek() {
    const seek = $('seek');
    const move = event => {
        const rect = seek.getBoundingClientRect();
        const pct = Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100));
        setSeek(pct);
        if (state.duration) $('remote-time').textContent = fmtClock((pct / 100) * state.duration);
        return pct;
    };
    seek.addEventListener('pointerdown', event => {
        state.seeking = true;
        seek.setPointerCapture(event.pointerId);
        move(event);
    });
    seek.addEventListener('pointermove', event => {
        if (state.seeking) move(event);
    });
    seek.addEventListener('pointerup', event => {
        if (!state.seeking) return;
        state.seeking = false;
        const pct = move(event);
        state.seekLock = Date.now() + 2500;
        fetch('/api/seek?pct=' + pct.toFixed(2)).catch(() => {});
    });
    seek.addEventListener('pointercancel', () => { state.seeking = false; });
})();

/* ── Audio and subtitle tracks ───────────────────────────────────────── */
const LANGUAGES = {
    jpn: 'Japanese', ja: 'Japanese', eng: 'English', en: 'English',
    spa: 'Spanish', es: 'Spanish', por: 'Portuguese', pt: 'Portuguese',
    fre: 'French', fra: 'French', fr: 'French', ger: 'German', deu: 'German',
    de: 'German', ita: 'Italian', it: 'Italian', rus: 'Russian', ru: 'Russian',
    ara: 'Arabic', ar: 'Arabic', chi: 'Chinese', zho: 'Chinese', zh: 'Chinese',
    kor: 'Korean', ko: 'Korean', hin: 'Hindi', hi: 'Hindi',
};

const CODECS = {
    eac3: 'E-AC-3', ac3: 'AC-3', aac: 'AAC', flac: 'FLAC', opus: 'Opus',
    truehd: 'TrueHD', dts: 'DTS', mp3: 'MP3', vorbis: 'Vorbis',
};

function audioLabel(t) {
    const lang = LANGUAGES[(t.lang || '').toLowerCase()] || (t.lang ? t.lang.toUpperCase() : t.title);
    const codec = CODECS[(t.codec || '').toLowerCase()] || (t.codec || '').toUpperCase();
    return [lang || `Track ${t.id}`, codec].filter(Boolean).join(' · ');
}

function subLabel(t) {
    const parts = [t.lang ? t.lang.toUpperCase() : null, t.title || null];
    if (t.forced && !/forced/i.test(t.title || '')) parts.push('Forced');
    return parts.filter(Boolean).join(' · ') || `Track ${t.id}`;
}

async function loadTracks() {
    let tracks;
    try {
        tracks = await getJSON('/api/tracks');
    } catch { return; }

    const render = (list, kind, labelFor, allowOff) => {
        const labels = list.map(labelFor);
        // Two tracks that would read the same get their title appended.
        const rows = list.map((t, i) => {
            const clash = labels.indexOf(labels[i]) !== labels.lastIndexOf(labels[i]);
            const text = clash ? `${labels[i]} · ${t.title || '#' + t.id}` : labels[i];
            return `<button class="pill ${t.selected ? 'selected' : ''}" data-action="set-track"
                            data-kind="${kind}" data-track="${t.id}">${esc(text)}</button>`;
        });
        if (allowOff) {
            const anySelected = list.some(t => t.selected);
            rows.unshift(`<button class="pill ${anySelected ? '' : 'selected'}" data-action="set-track"
                                  data-kind="${kind}" data-track="no">Off</button>`);
        }
        return rows.join('') || '<span class="muted">None in this file</span>';
    };

    $('sub-tracks').innerHTML = render(tracks.sub || [], 'sub', subLabel, true);
    $('audio-tracks').innerHTML = render(tracks.audio || [], 'audio', audioLabel, false);
}

function toggleTracks() {
    state.tracksOpen = !state.tracksOpen;
    writePref('tracksOpen', state.tracksOpen);
    $('track-panel').hidden = !state.tracksOpen;
    $('cc-btn').classList.toggle('on', state.tracksOpen);
    if (state.tracksOpen) loadTracks();
}

async function setTrack(kind, id) {
    await postJSON('/api/track', { kind, id });
    loadTracks();
}

async function stopPlayback() {
    await fetch('/api/stop');
    const series = state.playing?.series;
    state.playing = null;
    stopStatusPolling();
    if (series) await openSeries(series.slug);
    else goLibrary();
}

async function quitPlayer() {
    await fetch('/api/quit');
    state.playing = null;
    stopStatusPolling();
    goLibrary();
}

function closeRemote() {
    stopStatusPolling();
    if (state.series) openSeries(state.series.slug);
    else goLibrary();
}

/* Keep the "Now playing on TV" card honest: pick the remote back up if the
   phone reloaded mid-episode, and drop it once the TV has stopped. */
async function syncNowPlaying() {
    let s;
    try {
        s = await getJSON('/api/status');
    } catch { return; }

    if (!s.playing || !s.file) {
        if (!state.playing) return;
        state.playing = null;
    } else if (state.playing?.path !== s.file) {
        const folder = s.file.split('/')[0];
        const listed = state.library.find(x => x.folder === folder);
        if (!listed) return;
        try {
            state.playing = { path: s.file, series: await loadSeries(listed.slug) };
        } catch { return; }
    } else {
        return;
    }
    if (currentView() === 'library-view') renderLibrary();
}

/* ── Phone player ────────────────────────────────────────────────────── */
async function openStream(path) {
    const video = $('stream-player');
    const episode = findEpisode(path);

    $('stream-title').textContent = state.series?.title || 'Streaming';
    $('stream-episode').textContent = episode?.label || '';
    state.streaming = path;

    video.querySelectorAll('track').forEach(t => t.remove());
    video.src = '/stream/' + path.split('/').map(encodeURIComponent).join('/');

    // Browsers can only use sidecar subtitle files; anything muxed into the
    // mkv needs a remux, so say so instead of silently offering nothing.
    const notes = [];
    if (episode?.codec === 'HEVC' || episode?.codec === 'AV1') {
        notes.push(`${episode.codec} often will not decode in a phone browser — if the picture stays black, play it on the TV instead.`);
    }
    if (episode && !episode.subs.length) {
        notes.push('No sidecar subtitle files here. Subtitles muxed inside the video are only selectable on TV playback.');
    }
    $('stream-note').textContent = notes.join(' ');

    try {
        const subs = await getJSON('/api/subtitles?file=' + encodeURIComponent(path));
        subs.forEach((sub, i) => {
            const track = document.createElement('track');
            track.kind = 'subtitles';
            track.label = sub.label;
            track.src = sub.url;
            if (i === 0) track.default = true;
            video.appendChild(track);
        });
    } catch { /* subtitles are optional */ }

    try {
        const r = await getJSON('/api/resume?file=' + encodeURIComponent(path));
        if (r.pos > 30) {
            const seek = () => { video.currentTime = r.pos; };
            if (video.readyState >= 1) seek();
            else video.addEventListener('loadedmetadata', seek, { once: true });
            toast(`Resuming at ${fmtClock(r.pos)}`);
        }
    } catch { /* start from zero */ }

    showView('stream-view');
}

async function closeStream() {
    const video = $('stream-player');
    if (state.streaming && video.currentTime > 30) {
        await postJSON('/api/resume', {
            file: state.streaming,
            pos: video.currentTime,
            dur: video.duration || 0,
        }).catch(() => {});
    }
    video.pause();
    video.removeAttribute('src');
    video.load();
    state.streaming = null;

    if (state.series) await openSeries(state.series.slug);
    else goLibrary();
}

// Save position periodically too, in case the tab is closed outright.
setInterval(() => {
    const video = $('stream-player');
    if (!state.streaming || video.paused || video.currentTime < 30) return;
    postJSON('/api/resume', {
        file: state.streaming, pos: video.currentTime, dur: video.duration || 0,
    }).catch(() => {});
}, 15000);

/* ── Event delegation ────────────────────────────────────────────────────
   Every interactive element declares data-action plus its data, and this
   one listener dispatches. Nothing is interpolated into an inline onclick:
   a path like "Frieren - Beyond Journey's End/ep01.mkv" would have its
   &#39; decoded back to an apostrophe before the JS was parsed, ending the
   string literal early and throwing SyntaxError. dataset values are read,
   never evaluated, so any character is safe.                              */
document.addEventListener('click', event => {
    const el = event.target.closest('[data-action]');
    if (!el) return;
    const d = el.dataset;

    switch (d.action) {
        // library
        case 'card':            tapCard(el); break;
        case 'open-series':     openSeries(d.slug); break;
        case 'resume-series':   resumeSeries(d.slug); break;
        case 'status-filter':
            state.statusFilter = d.status;
            document.querySelectorAll('[data-action="status-filter"]')
                .forEach(p => p.classList.toggle('active', p === el));
            renderLibrary();
            break;
        case 'cycle-sort':
            state.sort = (state.sort + 1) % SORTS.length;
            renderLibrary();
            break;
        case 'open-downloads':  openDownloads(); break;
        case 'go-library':      goLibrary(); break;

        // series
        case 'series-menu':     seriesMenu(); break;
        case 'episode':         episodeSheet(d.path); break;
        case 'play-tv':         playOnTV(d.path); break;
        case 'pick-season':     pickSeason(Number(d.season)); break;
        case 'toggle-synopsis': el.classList.toggle('open'); break;

        // downloads
        case 'close-downloads': closeDownloads(); break;
        case 'download':        startDownload(el); break;
        case 'download-row':    downloadSheet(Number(d.id)); break;
        case 'dl-pause':        setPaused(Number(d.id), d.paused !== 'true'); break;
        case 'clear-finished':  clearFinished(); break;

        // remote
        case 'show-remote':     showRemote(); break;
        case 'close-remote':    closeRemote(); break;
        case 'toggle-tracks':   toggleTracks(); break;
        case 'set-track':       setTrack(d.kind, d.track === 'no' ? 'no' : Number(d.track)); break;
        case 'play-pause':      togglePause(); break;
        case 'prev-episode':    stepEpisode(-1); break;
        case 'next-episode':    stepEpisode(1); break;
        case 'cmd':             sendCmd(d.cmd); break;
        case 'stop-playback':   stopPlayback(); break;
        case 'quit-player':     quitPlayer(); break;

        // phone player
        case 'close-stream':    closeStream(); break;

        // overlays
        case 'sheet-pick':      pickSheet(Number(d.index)); break;
        case 'sheet-close':     closeSheet(); break;
        case 'sheet-dismiss':   if (event.target === el) closeSheet(); break;
        case 'modal-cancel':    closeModal(); break;
    }
});

document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
        if (!$('modal').hidden) closeModal();
        else if (!$('sheet').hidden) closeSheet();
    }
    // Episode rows are role="button" divs; make Enter work like a tap.
    if (event.key === 'Enter' && event.target.matches?.('[role="button"][data-action]')) {
        event.target.click();
    }
});

// Missing download thumbnails fall back to initials. Error events do not
// bubble, hence the capture phase.
document.addEventListener('error', event => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || !img.dataset.fallback) return;
    const box = document.createElement('div');
    box.className = 'thumb thumb-fallback';
    box.textContent = img.dataset.fallback;
    img.replaceWith(box);
}, true);

$('library-filter').addEventListener('input', renderLibrary);

/* ── Boot ────────────────────────────────────────────────────────────── */
renderLibrary();
showView('library-view');
syncNowPlaying();
