/* KaTeX is bundled locally. TeX remains readable if scripting is disabled. */
(() => {
  document.querySelectorAll('.math-display').forEach(element => {
    katex.render(element.textContent, element, {
      displayMode: true, throwOnError: true, trust: false, strict: 'error',
      output: 'htmlAndMathml'
    });
  });
  document.documentElement.dataset.mathReady = 'true';
})();
