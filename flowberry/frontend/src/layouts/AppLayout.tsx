import { PropsWithChildren } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export default function AppLayout({ children }: PropsWithChildren) {
  const { role, clear } = useAuthStore();

  return (
    <div className="min-h-screen text-zinc-100">
      <header className="border-b border-zinc-700 bg-zinc-900/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-lg font-bold text-berry-700">Flowberry</p>
            <p className="text-xs text-zinc-400">Fizz AI Workflow Automation</p>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link to="/workflows" className="text-zinc-200 hover:text-white">Workflows</Link>
            <Link to="/integrations" className="text-zinc-200 hover:text-white">Integrations</Link>
            <Link to="/logs" className="text-zinc-200 hover:text-white">Logs</Link>
            <Link to="/security" className="text-zinc-200 hover:text-white">Security</Link>
            {role === "admin" ? <Link to="/admin" className="text-zinc-200 hover:text-white">Admin</Link> : null}
            <button onClick={clear} className="rounded border border-zinc-700 px-3 py-1 hover:bg-zinc-800">Logout</button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-6">{children}</main>
    </div>
  );
}
