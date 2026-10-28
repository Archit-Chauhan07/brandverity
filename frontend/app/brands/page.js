"use client";

import { useEffect, useState } from "react";
import { api, getUser } from "../../lib/api";

function groupByCode(rules) {
  const groups = {};
  for (const r of rules || []) {
    (groups[r.rule_code] = groups[r.rule_code] || []).push(r);
  }
  for (const code of Object.keys(groups)) {
    groups[code].sort((a, b) => a.id - b.id);
  }
  return groups;
}

// Real diff between a rule's two latest versions, computed from the
// stored rows: which fields changed, old value -> new value.
function VersionDiff({ versions }) {
  if (!versions || versions.length < 2) return null;
  const prev = versions[versions.length - 2];
  const curr = versions[versions.length - 1];
  const changes = [];
  if (prev.text !== curr.text)
    changes.push({ field: "text", old: prev.text, new: curr.text });
  if (prev.kind !== curr.kind)
    changes.push({ field: "kind", old: prev.kind, new: curr.kind });
  const prevParams = JSON.stringify(prev.params || {});
  const currParams = JSON.stringify(curr.params || {});
  if (prevParams !== currParams)
    changes.push({ field: "params", old: prevParams, new: currParams });
  if (changes.length === 0)
    return (
      <p className="muted">
        No changes from {prev.version} to {curr.version}.
      </p>
    );
  return (
    <div>
      <p className="muted">
        Changes from {prev.version} to {curr.version}:
      </p>
      <ul>
        {changes.map((c) => (
          <li key={c.field}>
            <strong>{c.field}:</strong> {c.old} → {c.new}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function BrandsPage() {
  const [user, setUser] = useState(null);
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [rules, setRules] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [brandName, setBrandName] = useState("");
  const [createdBrand, setCreatedBrand] = useState(null);

  const [ruleCode, setRuleCode] = useState("");
  const [ruleKind, setRuleKind] = useState("forbidden_words");
  const [ruleText, setRuleText] = useState("");
  const [wordsInput, setWordsInput] = useState("");
  const [yearInput, setYearInput] = useState("");
  const [hexInput, setHexInput] = useState("#123456");
  const [toleranceInput, setToleranceInput] = useState("100");
  const [versionInput, setVersionInput] = useState("");
  const [ruleMsg, setRuleMsg] = useState("");

  useEffect(() => {
    const u = getUser();
    setUser(u);
    if (u?.tenant_id) {
      setTenantId(String(u.tenant_id));
      api
        .listTenants()
        .then((list) => {
          const arr = Array.isArray(list) ? list : list.tenants || [];
          const mine = arr.find((t) => String(t.id) === String(u.tenant_id));
          if (mine) setTenantName(mine.name);
        })
        .catch(() => {});
      loadRules(u.tenant_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadRules(tid) {
    api
      .listCustomRules(tid)
      .then(setRules)
      .catch((err) => setError(err.message));
  }

  async function onCreateBrand(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const brand = await api.createTenant(brandName);
      setCreatedBrand(brand);
      setBrandName("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onCreateRule(e) {
    e.preventDefault();
    setError("");
    setRuleMsg("");
    setBusy(true);
    try {
      let params;
      if (ruleKind === "forbidden_words") {
        params = {
          words: wordsInput
            .split(",")
            .map((w) => w.trim())
            .filter(Boolean),
        };
      } else if (ruleKind === "fact_year") {
        params = { year: parseInt(yearInput, 10) };
      } else {
        params = {
          hex: hexInput,
          tolerance: parseFloat(toleranceInput) || 100,
        };
      }
      const row = await api.createCustomRule(tenantId, {
        rule_code: ruleCode,
        kind: ruleKind,
        params,
        text: ruleText,
        version: versionInput || undefined,
      });
      setRuleMsg(`Saved ${row.rule_code} ${row.version}.`);
      setRuleCode("");
      setRuleText("");
      setWordsInput("");
      setYearInput("");
      setVersionInput("");
      loadRules(tenantId);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const isAdmin = user?.role === "Admin";
  const groups = groupByCode(rules);

  return (
    <>
      <h1>Brands</h1>
      {!user && (
        <p className="error">
          You are not logged in. Log in first — otherwise the backend will
          reject these requests.
        </p>
      )}
      {error && <p className="error">{error}</p>}

      <section className="card">
        <h2>Your brand&apos;s rule library</h2>
        {tenantName && (
          <p>
            Brand: <strong>{tenantName}</strong>
          </p>
        )}
        {Object.keys(groups).length === 0 && (
          <p className="muted">
            No custom rules yet. Northpeak&apos;s built-in library still
            applies; add a rule below to extend it, or create a new brand
            with its own library.
          </p>
        )}
        {Object.entries(groups).map(([code, versions]) => {
          const latest = versions[versions.length - 1];
          return (
            <div key={code}>
              <h3>
                {code} — latest {latest.version} ({latest.kind})
              </h3>
              <p>{latest.text}</p>
              <p className="muted">
                Params: {JSON.stringify(latest.params || {})} · Versions:{" "}
                {versions.map((v) => v.version).join(", ")}
              </p>
              <VersionDiff versions={versions} />
            </div>
          );
        })}
      </section>

      {isAdmin && (
        <section className="card">
          <h2>Add a rule to your brand</h2>
          <p className="muted">
            Only your brand&apos;s admin can add rules, and rules apply only
            to your brand&apos;s drafts. Leave version blank to auto-assign
            (v1, then v2, v3…).
          </p>
          <form onSubmit={onCreateRule}>
            <label htmlFor="rule-code">Rule code</label>
            <input
              id="rule-code"
              type="text"
              value={ruleCode}
              onChange={(e) => setRuleCode(e.target.value)}
              placeholder="HB-TONE-01"
              required
            />
            <label htmlFor="rule-kind">Kind</label>
            <select
              id="rule-kind"
              value={ruleKind}
              onChange={(e) => setRuleKind(e.target.value)}
            >
              <option value="forbidden_words">Banned words</option>
              <option value="fact_year">Founding year</option>
              <option value="palette">Brand colour</option>
            </select>
            <label htmlFor="rule-text">Rule wording</label>
            <input
              id="rule-text"
              type="text"
              value={ruleText}
              onChange={(e) => setRuleText(e.target.value)}
              placeholder="No hype words."
              required
            />
            {ruleKind === "forbidden_words" && (
              <>
                <label htmlFor="rule-words">Banned words (comma-separated)</label>
                <input
                  id="rule-words"
                  type="text"
                  value={wordsInput}
                  onChange={(e) => setWordsInput(e.target.value)}
                  placeholder="amazing, incredible"
                  required
                />
              </>
            )}
            {ruleKind === "fact_year" && (
              <>
                <label htmlFor="rule-year">Founding year</label>
                <input
                  id="rule-year"
                  type="number"
                  value={yearInput}
                  onChange={(e) => setYearInput(e.target.value)}
                  placeholder="2020"
                  required
                />
              </>
            )}
            {ruleKind === "palette" && (
              <>
                <label htmlFor="rule-hex">Brand colour</label>
                <input
                  id="rule-hex"
                  type="color"
                  value={hexInput}
                  onChange={(e) => setHexInput(e.target.value)}
                />
                <span className="muted"> {hexInput}</span>
                <label htmlFor="rule-tolerance">Tolerance</label>
                <input
                  id="rule-tolerance"
                  type="number"
                  value={toleranceInput}
                  onChange={(e) => setToleranceInput(e.target.value)}
                />
              </>
            )}
            <label htmlFor="rule-version">Version (optional)</label>
            <input
              id="rule-version"
              type="text"
              value={versionInput}
              onChange={(e) => setVersionInput(e.target.value)}
              placeholder="Leave blank for auto"
            />
            <button type="submit" disabled={busy || !tenantId}>
              {busy ? "Saving…" : "Save rule"}
            </button>
          </form>
          {ruleMsg && <p>{ruleMsg}</p>}
        </section>
      )}

      {isAdmin && (
        <section className="card">
          <h2>Create a new brand</h2>
          <p className="muted">
            A new brand gets its own demo accounts. You manage this brand
            from your current account; the new brand&apos;s own admin manages
            its rules after logging in with its demo account.
          </p>
          <form onSubmit={onCreateBrand}>
            <label htmlFor="brand-name">Brand name</label>
            <input
              id="brand-name"
              type="text"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Harbor Roasters"
              required
            />
            <button type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create brand"}
            </button>
          </form>
          {createdBrand && (
            <div>
              <p>
                Created <strong>{createdBrand.name}</strong>. Its demo
                accounts (password <code>demo123</code>):
              </p>
              <ul>
                {createdBrand.demo_users.map((u) => (
                  <li key={u.username}>
                    <code>{u.username}</code> ({u.role})
                  </li>
                ))}
              </ul>
              <p className="muted">
                Log out and log in as the new brand&apos;s admin to add its
                rules.
              </p>
            </div>
          )}
        </section>
      )}
    </>
  );
}
