/* Shared preview navigation, kept separate from individual game state. */
(() => {
  const skip = document.querySelector('.skip');
  const main = document.getElementById('main');
  skip?.addEventListener('click', event => {
    // A fragment-based router must not interpret the native #main skip link as
    // another game route or discard the currently displayed game.
    event.preventDefault();
    main?.focus({preventScroll: true});
    main?.scrollIntoView({block: 'start', behavior: 'instant'});
  });
})();
