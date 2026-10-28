"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearSession, getUser } from "../lib/api";

export default function Nav() {
  const router = useRouter();
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUser(getUser());
  }, []);

  function logout() {
    clearSession();
    setUser(null);
    router.push("/login");
  }

  return (
    <nav className="nav">
      <Link href="/" className="brand">BrandVerity</Link>
      <Link href="/upload">Upload</Link>
      <Link href="/queue">Queue</Link>
      <Link href="/insights">Insights</Link>
      <Link href="/brands">Brands</Link>
      <span className="spacer" />
      {user ? (
        <>
          <span className="who">
            {user.username} ({user.role})
          </span>
          <button onClick={logout}>Log out</button>
        </>
      ) : (
        <Link href="/login">Log in</Link>
      )}
    </nav>
  );
}
