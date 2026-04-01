import { RegistryExplorer } from "@/components/registry/RegistryExplorer";

export default function SearchPage({
  searchParams
}: {
  searchParams: { q?: string };
}) {
  return <RegistryExplorer initialQuery={searchParams.q ?? ""} />;
}

