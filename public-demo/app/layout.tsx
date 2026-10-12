import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'GridFlex GB | Nouman Sameer',description:'Live GB carbon-intensity forecasts and constrained charging plans, with open evaluation evidence.'};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en-GB"><body>{children}</body></html>;}
