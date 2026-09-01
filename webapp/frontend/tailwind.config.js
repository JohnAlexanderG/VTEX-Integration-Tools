/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Alias legado. No borrar hasta que `grep -rn "vtex-pink" src` esté vacío:
        // mantiene funcionando lo que todavía no migró a los tokens semánticos.
        vtex: {
          pink: '#F71963',
          dark: '#142032',
        },

        // Único color de acción de la app.
        accent: {
          DEFAULT: '#F71963',
          hover: '#D4104F',
          soft: 'rgba(247, 25, 99, 0.14)',
          fg: '#FFFFFF',
        },

        // Superficies, bordes y texto. Nombres deliberados: una clave
        // `colors.border.DEFAULT` colisionaría con la utilidad `border`
        // (border-width) de Tailwind.
        surface: {
          0: '#030712', // fondo de la app      (gray-950)
          1: '#111827', // sidebar, cards       (gray-900)
          2: '#1F2937', // inputs, botón sec.   (gray-800)
          3: '#374151', // hover elevado        (gray-700)
        },
        line: {
          1: '#1F2937', // borde por defecto    (gray-800)
          2: '#374151', // borde de control     (gray-700)
          3: '#4B5563', // borde hover          (gray-600)
        },
        ink: {
          1: '#F3F4F6', // texto principal      (gray-100)
          2: '#D1D5DB', // texto secundario     (gray-300)
          3: '#9CA3AF', // texto terciario      (gray-400)
          4: '#6B7280', // metadatos            (gray-500)
        },
      },

      borderRadius: {
        control: '8px', // botones, inputs, badges cuadrados
        card: '12px',   // cards, paneles, modales
      },

      keyframes: {
        'toast-in': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'toast-in': 'toast-in 150ms ease-out',
      },
    },
  },
  plugins: [],
}
