import type { Metadata } from "next";

export const metadata: Metadata = { title: "About and limitations · Compass" };

const items: { id: string; title: string; body: React.ReactNode }[] = [
  {
    id: "privacy",
    title: "Privacy",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>Your profile (dorm, required courses, target credits, completed Hub areas), your selected schedule, and your theme and pet choices are stored in this browser (localStorage).</li>
        <li>Schedules you generate are also saved on the server (section times and your dorm code only) so that leave-by, meal windows, and calendar export can work. No name, grades, or course history is collected.</li>
        <li>Accounts are optional and used only for friends. We store your @bu.edu email, an optional display name, a salted password hash, and hashed session tokens.</li>
        <li>Sharing free time is off by default. When on, a friend can see only the windows when you are both free. Course names, buildings, and section details are never sent to friends. Note that shared free windows still imply when you are busy.</li>
      </ul>
    ),
  },
  {
    id: "email",
    title: "Email is not verified",
    body: <p>Nobody is sent a confirmation message. Anyone can register any address ending in @bu.edu, including one that is not theirs. Only accept friend requests from people you know, and do not rely on an email address as proof of identity.</p>,
  },
  {
    id: "api",
    title: "Non-production API data",
    body: <p>Shuttle and dining data come from a BU API gateway that is a non-production environment. It may be incomplete, change shape, be unavailable, or be wrong. When it cannot be reached the app falls back to cached data and says so. Dining hours and menus are published for today only; other days use hours last seen on that weekday, or are marked unavailable. Shuttle alerts are not tagged by route, so route alerts are derived from live vehicle and route status.</p>,
  },
  {
    id: "transit",
    title: "Small transit sample",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>The delay model learns from shuttle predictions logged every 2 minutes. Until it has at least 500 trips over 3 days it trains on synthetic placeholder delays, and the app labels this wherever delay estimates appear.</li>
        <li>The gateway does not publish when a bus actually arrived, so the &quot;actual&quot; delay is the last prediction seen before arrival.</li>
        <li>Walking-time spread (about ±20%) is an assumption, not a measurement. Probabilities are rounded and are never 0% or 100%.</li>
      </ul>
    ),
  },
  {
    id: "catalog",
    title: "Course catalog",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>Courses and sections are read from the BU course catalog database (read-only) for Spring 2027. The header badge shows whether the catalog is live, or cached from the last successful read. If the database cannot be reached and nothing is cached, the app falls back to a fictional <strong>sample catalog</strong> and says so in the badge.</li>
        <li>Only some of the catalog is listed: undergraduate courses on the Charles River campus, regular full-term sessions, with a weekday meeting time. Independent and directed study, applied music, unscheduled sections, weekend meetings, courses with zero or fractional credits, and courses whose lab or discussion cannot be placed are left out, so a course you expect may be missing.</li>
        <li>The catalog has no Hub or prerequisite fields. Hub areas are read from the sentence in each course description (&quot;fulfills a single unit in … BU Hub areas&quot;), and prerequisites are shown as the description&apos;s own text and are not checked against what you have taken. Either can be missed or out of date.</li>
        <li>The catalog has no seat counts, so full sections are not excluded. It also does not say which discussion or lab belongs to which lecture, so the optimizer may pair a lecture with a discussion section you cannot actually register for together. Check the official registration system.</li>
        <li>A section that meets at more than one time (for example a regular lecture plus an evening session) is scheduled with all of its meetings.</li>
        <li>Using a different catalog source means implementing one adapter (<code>DbCatalogSource</code> in <code>backend/clients/catalog.py</code>) that maps it to the same course and section models.</li>
      </ul>
    ),
  },
  {
    id: "coords",
    title: "Approximate building coordinates",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>Building, dorm, and dining hall locations come from a list that has not been verified. Walking times (straight-line distance with a detour factor, adjusted for pace) and leave-by times are estimates and can be off, especially for short walks.</li>
        <li>If a section&apos;s building is missing from the buildings table, or its coordinates are unverified, the walking time is still estimated but marked approximate (≈).</li>
        <li>Most Spring 2027 sections have no room assigned in the catalog yet, so most classes show as location unknown for now.</li>
        <li>Sections on the medical campus, sections with no building, and sections listed as “No Room” have no walking time. They are marked “location unknown” and are left out of transition-risk, tight-transition, and travel calculations. Leave-by times, meal-fit checks, and calendar alarms are not given for them.</li>
      </ul>
    ),
  },
  {
    id: "advising",
    title: "Not a replacement for academic advising",
    body: <p>Schedules, Hub suggestions, credit ranges, and prerequisite notes are planning aids. They do not check degree requirements, holds, or registration rules. Confirm your plan with your academic advisor and the official degree audit before registering.</p>,
  },
  {
    id: "dietary",
    title: "Dietary information",
    body: (
      <>
        <p className="font-medium">Dietary info may be outdated; confirm with dining staff.</p>
        <p className="mt-1">Filters use the vegetarian, vegan, gluten-free, and halal flags in the dining data. There is no allergen data, so allergens cannot be filtered. If you have a food allergy, speak with BU Dining staff before ordering.</p>
      </>
    ),
  },
];

export default function AboutPage() {
  return (
    <article aria-labelledby="h" className="mx-auto max-w-2xl space-y-6">
      <h1 id="h" className="text-2xl font-semibold">About and limitations</h1>
      <p className="text-sm">Compass is a hackathon prototype. Please read these limits before relying on it.</p>
      <nav aria-label="On this page">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {items.map((i) => (
            <li key={i.id}><a href={`#${i.id}`} className="text-accent underline">{i.title}</a></li>
          ))}
        </ul>
      </nav>
      {items.map((i) => (
        <section key={i.id} id={i.id} aria-labelledby={`${i.id}-h`} className="scroll-mt-4 space-y-1 text-sm leading-relaxed">
          <h2 id={`${i.id}-h`} className="text-lg font-semibold">{i.title}</h2>
          {i.body}
        </section>
      ))}
    </article>
  );
}
