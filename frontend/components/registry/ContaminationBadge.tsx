import { StatusPill } from "@/components/ui/StatusPill";
import { ContaminationStatus } from "@/lib/types";

export function ContaminationBadge({ status }: { status: ContaminationStatus }) {
  return <StatusPill status={status} />;
}

