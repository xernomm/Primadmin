/** @type {import('tailwindcss').Config} */
import typography from '@tailwindcss/typography';

export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    50: '#fff1f2',
                    100: '#ffe4e6',
                    200: '#fecdd3',
                    300: '#fda4af',
                    400: '#fb7185',
                    500: '#f43f5e',
                    600: '#e11d48',
                    700: '#be123c',
                    800: '#9f1239',
                    900: '#881337',
                },
                hr: {
                    dark: '#09090b',    // Zinc 950
                    darker: '#000000',  // Black
                    accent: '#18181b',  // Zinc 900
                    card: '#27272a',    // Zinc 800
                    highlight: '#f43f5e', // Rose 500
                    text: '#e4e4e7',      // Zinc 200
                    muted: '#a1a1aa'      // Zinc 400
                }
            }
        },
    },
    plugins: [
        typography,
    ],
}
