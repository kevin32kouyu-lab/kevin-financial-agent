import { LandingView } from "./views/Landing";
import { TerminalView } from "./views/Terminal";
import { WorkbenchView } from "./views/Workbench";

export default function App() {
  const path = window.location.pathname;
  if (path.startsWith("/debug")) {
    return <WorkbenchView />;
  }
  if (path.startsWith("/terminal")) {
    return <TerminalView />;
  }
  return <LandingView />;
}
