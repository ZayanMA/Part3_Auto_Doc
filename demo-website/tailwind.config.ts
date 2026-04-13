import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        atlassian: {
          blue: '#0052CC',
          'blue-hover': '#0065FF',
          'bg': '#F4F5F7',
          'border': '#DFE1E6',
          'text': '#172B4D',
          'subtle': '#6B778C',
        }
      }
    },
  },
  plugins: [],
}
export default config
