/** Same-origin presentation controller. No CDN HTML, iframe fetch or srcdoc. */
const $ = id => document.getElementById(id);
const panels = [...document.querySelectorAll('.panel')];
const frame = $('model');
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
let renderer, active = -1, night = false, queued = false, restoreFocus;
const state = { ready: false, error: null, activeChapter: null, schema: 'presentation-v2' };
window.__presentation = state;
for (const panel of panels) {
  const a = document.createElement('a');
  a.href = `#${panel.id}`;
  a.setAttribute('aria-label', panel.getAttribute('aria-label'));
  a.title = panel.getAttribute('aria-label');
  $('chapter').append(a);
}
const dots = [...$('chapter').children];
function applyChapter(index, force = false) {
  if (!renderer || (index === active && !force)) return;
  active = index;
  state.activeChapter = panels[index].id;
  dots.forEach((dot, n) => {
    dot.classList.toggle('active', n === index);
    if (n === index) dot.setAttribute('aria-current', 'step');
    else dot.removeAttribute('aria-current');
  });
  renderer.set('explode', panels[index].id === 'floors' ? 1 : 0);
  renderer.preset(panels[index].dataset.view || 'hero');
  if (innerWidth < 801) {
    renderer.goal.radius *= 1.18;
    if (panels[index].id !== 'energy') renderer.goal.target[1] -= 9;
  } else {
    renderer.goal.target[0] += panels[index].querySelector('.right') ? 10 : -10;
  }
  if (reduced) renderer.camera = { ...renderer.goal, target: [...renderer.goal.target] };
  renderer.dirty = true;
}
function update(force = false) {
  const max = document.documentElement.scrollHeight - innerHeight;
  $('progress').style.width = `${max > 0 ? Math.min(100, Math.max(0, scrollY / max * 100)) : 0}%`;
  let best = 0, distance = Infinity;
  panels.forEach((panel, index) => {
    const d = Math.abs(panel.getBoundingClientRect().top);
    if (d < distance) { best = index; distance = d; }
  });
  applyChapter(best, force);
}
function queueUpdate() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => { queued = false; update(); });
}
addEventListener('scroll', queueUpdate, { passive: true });
addEventListener('resize', () => update(true));
function failure(message) {
  state.error = message;
  $('load-message').textContent = message;
  $('loading').hidden = false;
}
function initialise() {
  if (state.ready) return;
  try {
    const child = frame.contentWindow;
    if (!child?.__office14__?.renderer) return;
    renderer = child.__office14__.renderer;
    if (!renderer.gl || child.document.querySelector('#error:not([hidden])')) {
      failure('อุปกรณ์นี้เปิด WebGL 2 ไม่สำเร็จ ลองเปิดใน Safari หรือ Chrome โดยตรง'); return;
    }
    const css = child.document.createElement('style');
    css.textContent = 'html,body{width:100%!important;height:100%!important;overflow:hidden!important}.topbar,.sidebar{display:none!important}.workspace{display:block!important;height:100svh!important;min-height:0!important}.viewport{height:100svh!important;min-height:0!important}.viewport>:not(canvas):not(#error){display:none!important}';
    child.document.head.append(css);
    renderer.resize();
    renderer.set('auto', false);
    renderer.onError = failure;
    state.ready = true;
    state.error = null;
    update(true);
    renderer.render();
    $('loading').hidden = true;
  } catch (error) { failure(`เปิดโมเดลไม่สำเร็จ: ${error.message}`); }
}
frame.addEventListener('load', initialise);
const start = performance.now();
const waiting = setInterval(() => {
  initialise();
  if (state.ready || state.error) clearInterval(waiting);
  else if (performance.now() - start > 30000) {
    clearInterval(waiting);
    failure('โหลดโมเดลไม่สำเร็จ กรุณาโหลดหน้าใหม่ หรือเปิดตัวดูโมเดลโดยตรง');
  }
}, 150);
initialise();
$('night').addEventListener('click', () => {
  if (!renderer) return;
  night = !night;
  renderer.set('night', night);
  $('night').textContent = night ? 'กลางวัน' : 'กลางคืน';
  $('night').setAttribute('aria-pressed', String(night));
});
function openExplore() {
  restoreFocus = document.activeElement;
  const viewer = $('full-model');
  if (!viewer.getAttribute('src')) viewer.src = viewer.dataset.src;
  $('full').hidden = false;
  $('story').inert = true;
  document.querySelector('.top').inert = true;
  $('chapter').inert = true;
  document.body.classList.add('exploring');
  $('close').focus();
}
function closeExplore() {
  $('full').hidden = true;
  $('story').inert = false;
  document.querySelector('.top').inert = false;
  $('chapter').inert = false;
  document.body.classList.remove('exploring');
  // Release the second WebGL context when not in use on mobile.
  $('full-model').removeAttribute('src');
  restoreFocus?.focus();
}
$('full3d').addEventListener('click', openExplore);
$('end-explore').addEventListener('click', openExplore);
$('close').addEventListener('click', closeExplore);
addEventListener('keydown', event => {
  if (event.key === 'Escape' && !$('full').hidden) closeExplore();
  if (event.key === 'Tab' && !$('full').hidden && event.shiftKey && document.activeElement === $('close')) {
    event.preventDefault(); $('full-model').focus();
  }
});
