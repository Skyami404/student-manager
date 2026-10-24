"use client";
import { useCallback, useEffect, useState } from "react";
import { authApi, type FreeGaps, type FriendsData, type Me, type Schedule } from "@/lib/api";
import { setToken, useToken } from "@/lib/session";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const input = "rounded border border-line bg-surface p-2 text-sm";
const btn = "rounded border border-line bg-surface px-3 py-1.5 text-sm";

export default function FriendsPanel({ schedule }: { schedule: Schedule }) {
  const token = useToken();
  const [me, setMe] = useState<Me | null>(null);
  const [friends, setFriends] = useState<FriendsData | null>(null);
  const [msg, setMsg] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [addEmail, setAddEmail] = useState("");
  const [gaps, setGaps] = useState<{ id: number; data: FreeGaps } | null>(null);

  const refresh = useCallback(async (t: string) => {
    const [m, f] = await Promise.all([authApi<{ user: Me }>("GET", "/me", t), authApi<FriendsData>("GET", "/friends", t)]);
    setMe(m.user);
    setFriends(f);
  }, []);

  useEffect(() => {
    if (!token) return;
    let live = true;
    Promise.all([authApi<{ user: Me }>("GET", "/me", token), authApi<FriendsData>("GET", "/friends", token)])
      .then(([m, f]) => {
        if (!live) return;
        setMe(m.user);
        setFriends(f);
      })
      .catch(() => {
        if (!live) return;
        setToken(null);
        setMsg("Session expired. Please sign in again.");
      });
    return () => void (live = false);
  }, [token]);

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setMsg("");
    try {
      await fn();
      if (ok) setMsg(ok);
      if (token) await refresh(token);
    } catch (e) {
      setMsg((e as Error).message);
    }
  };

  async function auth(kind: "register" | "login") {
    setMsg("");
    try {
      const r = await authApi<{ token: string }>("POST", `/auth/${kind}`, null, { email, password, display_name: name || null });
      setPassword("");
      setToken(r.token);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  const box = "rounded border border-line p-4";
  const note = <p className="text-xs opacity-70">Email ownership is not verified: anyone can register any @bu.edu address, so only accept people you know. Friends see only shared free-time windows, never course names.</p>;

  if (!token) {
    return (
      <section aria-labelledby="fr" className={box}>
        <h2 id="fr" className="text-lg font-semibold">Friends</h2>
        <form className="mt-2 flex max-w-sm flex-col gap-2" onSubmit={(e) => { e.preventDefault(); auth("login"); }}>
          <label className="text-sm">BU email (must end in @bu.edu)<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={`${input} mt-1 w-full`} autoComplete="email" /></label>
          <label className="text-sm">Password (8+ characters)<input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className={`${input} mt-1 w-full`} autoComplete="current-password" /></label>
          <label className="text-sm">Display name (optional, for registering)<input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} className={`${input} mt-1 w-full`} /></label>
          <div className="flex gap-2">
            <button type="submit" className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white dark:text-black">Sign in</button>
            <button type="button" onClick={() => auth("register")} className={btn}>Create account</button>
          </div>
        </form>
        {msg && <p role="alert" className="mt-2 text-sm text-warn"><span aria-hidden="true">⚠</span> {msg}</p>}
        <div className="mt-2">{note}</div>
      </section>
    );
  }

  return (
    <section aria-labelledby="fr" className={`${box} space-y-4`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="fr" className="text-lg font-semibold">Friends</h2>
        <button type="button" className={btn} onClick={async () => { await authApi("POST", "/auth/logout", token).catch(() => {}); setToken(null); setMe(null); setFriends(null); }}>Sign out</button>
      </div>
      {me && (
        <div className="space-y-2 text-sm">
          <p>Signed in as <span className="font-medium">{me.display_name ?? me.email}</span> ({me.email}) · <span className="text-warn"><span aria-hidden="true">⚠</span> email not verified</span></p>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={me.share_free_time} onChange={(e) => run(() => authApi("POST", "/me/settings", token, { share_free_time: e.target.checked }))} />
            Share my free-time windows with friends (off by default)
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className={btn} onClick={() => run(() => authApi("POST", "/me/schedule", token, { schedule_id: schedule.id }), "Schedule synced. Only your free times are used.")}>
              <span aria-hidden="true">↻</span> Sync this schedule
            </button>
            <span className="text-xs">{me.has_schedule ? "✓ A schedule is synced." : "No schedule synced yet; free windows need one."}</span>
          </div>
        </div>
      )}

      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); run(async () => { await authApi("POST", "/friends/request", token, { email: addEmail }); setAddEmail(""); }, "If that @bu.edu address has an account, a request was sent."); }}>
        <label className="text-sm">Add a friend by BU email<input type="email" required value={addEmail} onChange={(e) => setAddEmail(e.target.value)} className={`${input} mt-1 block`} /></label>
        <button type="submit" className={btn}>Send request</button>
      </form>

      {friends && friends.incoming.length > 0 && (
        <div>
          <h3 className="text-sm font-medium">Requests for you</h3>
          <ul className="mt-1 space-y-1 text-sm">
            {friends.incoming.map((r) => (
              <li key={r.request_id} className="flex items-center gap-2">
                {r.display_name ?? r.email} ({r.email})
                <button type="button" className={btn} onClick={() => run(() => authApi("POST", "/friends/accept", token, { request_id: r.request_id }))}><span aria-hidden="true">✓</span> Accept</button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {friends && friends.outgoing.length > 0 && <p className="text-xs opacity-80">Waiting for: {friends.outgoing.map((o) => o.email).join(", ")}</p>}

      {friends && (
        <div>
          <h3 className="text-sm font-medium">Your friends ({friends.friends.length})</h3>
          <ul className="mt-1 space-y-2 text-sm">
            {friends.friends.map((f) => (
              <li key={f.id}>
                <div className="flex flex-wrap items-center gap-2">
                  {f.display_name ?? f.email}
                  <span className="text-xs opacity-70">{f.shares_free_time ? "✓ shares free time" : "○ not sharing"}</span>
                  <button type="button" className={btn} onClick={() => run(async () => setGaps({ id: f.id, data: await authApi<FreeGaps>("GET", `/friends/free-gaps?friend_id=${f.id}`, token) }))}>Shared free windows</button>
                </div>
                {gaps?.id === f.id && (
                  <table className="mt-2 text-xs">
                    <caption className="sr-only">Windows when you are both free</caption>
                    <tbody>
                      {DAYS.map((d) => (
                        <tr key={d}>
                          <th scope="row" className="pr-3 text-left font-medium">{d}</th>
                          <td>{gaps.data.windows[d]?.length ? gaps.data.windows[d].map((w) => `${w.start}–${w.end}`).join(", ") : "none"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </li>
            ))}
            {friends.friends.length === 0 && <li className="text-xs opacity-70">No friends yet.</li>}
          </ul>
        </div>
      )}
      {msg && <p role="status" className="text-sm"><span aria-hidden="true">ℹ</span> {msg}</p>}
      {note}
    </section>
  );
}
