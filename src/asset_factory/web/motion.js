// Animate visual state changes, without changing the request or storage flow.
(() => {
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const animations = new Set();
  const running = new WeakMap();
  preference.addEventListener('change', () => {
    if (preference.matches) for (const animation of animations) animation.cancel();
  });
  const animate = (element, frames, duration = 320) => {
    if (!element || preference.matches || !element.animate) return Promise.resolve();
    running.get(element)?.cancel();
    const animation = element.animate(frames, {
      duration, easing: 'cubic-bezier(.22,1,.36,1)'
    });
    animations.add(animation);
    running.set(element, animation);
    return animation.finished.catch(() => {}).finally(() => {
      animations.delete(animation);
      if (running.get(element) === animation) running.delete(element);
    });
  };
  window.studioMotion = {
    enter: element => animate(element, [
      {opacity: 0, transform: 'translateY(14px) scale(.985)'},
      {opacity: 1, transform: 'translateY(0) scale(1)'}
    ]),
    swap: element => animate(element, [
      {opacity: .5, transform: 'translateY(5px)'},
      {opacity: 1, transform: 'translateY(0)'}
    ], 240),
    leave: element => animate(element, [
      {opacity: 1, transform: 'translateY(0) scale(1)'},
      {opacity: 0, transform: 'translateY(8px) scale(.985)'}
    ], 170),
    error: element => animate(element, [
      {transform: 'translateX(0)'}, {transform: 'translateX(-4px)'},
      {transform: 'translateX(4px)'}, {transform: 'translateX(0)'}
    ], 240),
    button: (element, state, text) => {
      element.classList.toggle('submit-pending', state === 'pending');
      element.classList.toggle('submit-success', state === 'success');
      element.setAttribute('aria-busy', String(state === 'pending'));
      element.textContent = text;
    }
  };
})();
