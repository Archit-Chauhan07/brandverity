import "./globals.css";
import Nav from "./Nav";

export const metadata = {
  title: "BrandVerity — Brand Governance",
  description: "Day 1 demo skeleton: draft, review, and approve brand content for Northpeak Coffee.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main>{children}</main>
      </body>
    </html>
  );
}
