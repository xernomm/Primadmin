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
                    50: '#fef2f2',  // Red 50
                    100: '#fee2e2', // Red 100
                    200: '#fecaca', // Red 200
                    300: '#fca5a5', // Red 300
                    400: '#f87171', // Red 400
                    500: '#ef4444', // Red 500
                    600: '#dc2626', // Red 600 (Darker red for primary actions)
                    700: '#b91c1c', // Red 700
                    800: '#991b1b', // Red 800
                    900: '#7f1d1d', // Red 900
                },
                hr: {
                    dark: '#0a0a0a',      // Very dark background
                    darker: '#000000',    // Pure black
                    accent: '#181818',    // Requested dark gray
                    card: '#222222',      // Slightly lighter card background
                    highlight: '#dc2626', // Sharp dark red highlight
                    text: '#ffffff',      // Pure white text
                    muted: '#a3a3a3'      // Neutral gray (Neutral 400)
                }
            }
        },
    },
    plugins: [
        typography,
    ],
}
