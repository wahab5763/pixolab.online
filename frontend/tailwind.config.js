/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: '#090914',
        foreground: '#f8fafc',
        card: '#111122',
        border: 'rgba(255,255,255,0.12)',
        primary: '#a855f7',
        accent: '#22d3ee',
        muted: '#94a3b8',
        destructive: '#fb7185'
      },
      fontFamily: {
        inter: ['Inter', 'system-ui', 'sans-serif'],
        space: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
