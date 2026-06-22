import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#F6F7F9',
        card: '#FFFFFF',
        border: '#E9E9EE',
      },
      borderRadius: {
        '2xl': '1rem',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};

export default config;
