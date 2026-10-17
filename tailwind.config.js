/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#292b3a',
        muted: '#777b8e',
        canvas: '#f7f5f1',
        card: '#fbfaf7',
        lavender: '#efedfa',
        violet: '#7568c7',
        mint: '#e6f3ed',
        peach: '#f8ede5',
        line: '#eae7e0',
      },
      boxShadow: {
        soft: '0 12px 32px rgba(52, 47, 70, .06)',
      },
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        display: ['Manrope', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
