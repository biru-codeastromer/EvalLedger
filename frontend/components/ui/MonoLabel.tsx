import { PropsWithChildren } from "react";

export function MonoLabel({ children }: PropsWithChildren) {
  return <span className="mono">{children}</span>;
}

