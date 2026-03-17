/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        vtex: {
          pink: '#F71963',
          dark: '#142032',
        },
      },
    },
  },
  plugins: [],
}
