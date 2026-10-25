/** Tailwind (compilado, sin CDN: la app funciona en intranets sin internet).
 *  Recompilar tras cambiar clases en las vistas:
 *    npx tailwindcss@3.4.17 -c tailwind.config.js -i frontend/tailwind.input.css -o app/static/css/tailwind.css --minify
 */
module.exports = {
  content: ['./app/static/index.html', './app/static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        marca: { 50: '#fbeef0', 100: '#f5d3d8', 500: '#c42a42', 600: '#A6192E', 700: '#8a1426', 800: '#6d0f1e' },
      },
      fontFamily: { sans: ['Roboto', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'] },
    },
  },
  plugins: [],
};
