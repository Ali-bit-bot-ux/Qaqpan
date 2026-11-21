import "../analyst-tools.css";
import "../analyst.css";
import { Suspense } from "react";
import RoleScreen from "../RoleScreen";
import Analyst from "../Analyst";
import { Skeleton } from "../ui";
export default function Page() {
  return (
    <RoleScreen role="analyst">
      <Suspense fallback={<Skeleton />}>
        <Analyst />
      </Suspense>
    </RoleScreen>
  );
}
