import BuildPage from "./build/page";

// "/" renders the Build tab directly (no redirect), so Next.js can render and validate this segment.
export default function Home() {
  return <BuildPage />;
}
