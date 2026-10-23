/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        tg: {
          bg: '#0a0e17',
          surface: '#111827',
          panel: '#1e293b',
          border: '#334155',
          accent: '#10b981', // emerald
          cyan: '#06b6d4',
          danger: '#ef4444',
          warning: '#f59e0b',
          muted: '#94a3b8',
          text: '#f8fafc',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
