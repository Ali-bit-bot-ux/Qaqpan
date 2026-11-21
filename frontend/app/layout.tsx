import AppProvider from "./AppProvider";
import localFont from "next/font/local";
import "./style.css";
import "./bank.css";
import "./presentation.css";

const inter = localFont({
  src: "./fonts/InterVariable.woff2",
  weight: "100 900",
  variable: "--bank-font",
  display: "swap",
});
export const metadata = { title: "Қақпан · Защита переводов" };
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={inter.variable}>
      <body>
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
