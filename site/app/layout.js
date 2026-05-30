import "./globals.css";

export const metadata = {
  title: "YouTube Auto Uploader — Кабинет",
  description: "Личный кабинет, статистика и рейтинги",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
