"use client";
import { useDataStatus } from "@/lib/useDataStatus";

/** Names the catalog behind the page: "BU course catalog, Spring 2027", or the sample catalog if that is what is loaded. */
export default function CatalogTag() {
  const { status } = useDataStatus();
  if (!status) return <>catalog</>; // neutral wording until /data-status answers
  return <>{status.catalog.synthetic ? "sample (synthetic) catalog" : status.catalog.label}</>;
}
