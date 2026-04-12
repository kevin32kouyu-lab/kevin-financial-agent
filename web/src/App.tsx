import { TerminalView } from "./views/Terminal";
import { WorkbenchView } from "./views/Workbench";

export default function App() {
  if (window.location.pathname.startsWith("/debug")) {
    return <WorkbenchView />;
  }
  return <TerminalView />;
}
