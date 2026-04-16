import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { IntegrationSummary } from "../types/integrations";

const PROVIDERS = [
  "Google Drive",
  "Gmail",
  "Google Calendar",
  "NewsAPI",
  "Notion",
  "SERP API",
];

const MOCK_KEYS: Record<string, { api_key?: string; oauth_json?: string }> = {
  "NewsAPI": { api_key: "mock-newsapi-key" },
  "Notion": { api_key: "mock-notion-key" },
  "SERP API": { api_key: "mock-serp-key" },
  "Google Drive": { oauth_json: "{\"type\":\"service_account\",\"project_id\":\"mock\"}" },
  "Gmail": { oauth_json: "{\"type\":\"service_account\",\"project_id\":\"mock\"}" },
  "Google Calendar": { oauth_json: "{\"type\":\"service_account\",\"project_id\":\"mock\"}" },
};

export default function IntegrationsPage() {
  const [items, setItems] = useState<IntegrationSummary[]>([]);
  const [provider, setProvider] = useState(PROVIDERS[0]);
  const [displayName, setDisplayName] = useState("My Integration");
  const [oauthJson, setOauthJson] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const [checkErrors, setCheckErrors] = useState<string[]>([]);
  const [deletePassword, setDeletePassword] = useState("");
  const [connectingId, setConnectingId] = useState<string | null>(null);

  async function refresh() {
    const res = await api.get<{ data: IntegrationSummary[] }>("/integrations");
    setItems(res.data.data);
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const defaults = MOCK_KEYS[provider] || {};
    setOauthJson(defaults.oauth_json ?? "");
    setApiKey(defaults.api_key ?? "");
  }, [provider]);

  async function onCreate() {
    setLoading(true);
    setError(null);
    setCheckResult(null);
    setCheckErrors([]);
    try {
      await api.post("/integrations", {
        provider,
        display_name: displayName,
        oauth_json: oauthJson,
        api_key: apiKey,
      });
      await refresh();
    } catch (e: any) {
      setError(e?.response?.data?.error?.message ?? "Create failed");
    } finally {
      setLoading(false);
    }
  }

  async function onCheck() {
    setLoading(true);
    setError(null);
    setCheckResult(null);
    setCheckErrors([]);
    try {
      const res = await api.post<{ success: boolean; errors: string[] }>("/integrations/check", {
        provider,
        oauth_json: oauthJson,
        api_key: apiKey,
      });
      if (res.data.success) {
        setCheckResult("Integration settings look valid.");
      } else {
        setCheckErrors(res.data.errors || ["Validation failed."]);
      }
    } catch (e: any) {
      setError(e?.response?.data?.error?.message ?? "Check failed");
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(id: string) {
    if (!deletePassword) {
      setError("Password required to delete");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.delete(`/integrations/${id}`, { data: { password: deletePassword } });
      setDeletePassword("");
      await refresh();
    } catch (e: any) {
      setError(e?.response?.data?.error?.message ?? "Delete failed");
    } finally {
      setLoading(false);
    }
  }

  async function onConnect(id: string) {
    setConnectingId(id);
    setError(null);
    try {
      const res = await api.post<{ data: { auth_url: string } }>(`/integrations/${id}/oauth/start`);
      const url = res.data.data.auth_url;
      window.open(url, "_blank", "width=520,height=720");
      setTimeout(() => {
        refresh();
        setConnectingId(null);
      }, 3000);
    } catch (e: any) {
      setError(e?.response?.data?.error?.message ?? "Failed to start OAuth flow.");
      setConnectingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Integrations</h2>
        <p className="text-sm text-zinc-400">Store OAuth JSON or API keys. Secrets are encrypted and never returned to the UI.</p>
      </div>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900/70 p-4 space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="text-xs text-zinc-400">Provider</label>
            <select className="w-full rounded border border-zinc-700 bg-zinc-800 p-2" value={provider} onChange={(e) => setProvider(e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-400">Display name</label>
            <input className="w-full rounded border border-zinc-700 bg-zinc-800 p-2" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="text-xs text-zinc-400">OAuth JSON (optional)</label>
            <textarea className="h-32 w-full rounded border border-zinc-700 bg-zinc-800 p-2" value={oauthJson} onChange={(e) => setOauthJson(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-zinc-400">API Key (optional)</label>
            <input className="w-full rounded border border-zinc-700 bg-zinc-800 p-2" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button disabled={loading} onClick={onCheck} className="rounded border border-berry-700 px-4 py-2 text-sm text-berry-700 disabled:opacity-50">
            {loading ? "Checking..." : "Check Integration"}
          </button>
          <button disabled={loading} onClick={onCreate} className="rounded bg-berry-700 px-4 py-2 font-medium text-white disabled:opacity-50">
            {loading ? "Saving..." : "Add Integration"}
          </button>
        </div>
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        {checkResult ? <p className="text-sm text-green-400">{checkResult}</p> : null}
        {checkErrors.length > 0 ? (
          <div className="text-sm text-red-400 space-y-1">
            {checkErrors.map((msg, idx) => (
              <p key={idx}>{msg}</p>
            ))}
          </div>
        ) : null}
      </div>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900/70 p-4">
        <div className="flex items-center gap-3">
          <input
            type="password"
            autoComplete="current-password"
            placeholder="Password required to delete"
            className="flex-1 rounded border border-zinc-700 bg-zinc-800 p-2"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
          />
        </div>
        <div className="mt-4 space-y-2">
          {items.map((item) => (
            <div key={item.id} className="flex items-center justify-between rounded border border-zinc-800 p-3">
              <div>
                <p className="text-sm font-medium">{item.display_name}</p>
                <p className="text-xs text-zinc-400">{item.provider}</p>
              </div>
              <div className="flex items-center gap-2">
                {item.has_oauth_token ? (
                  <span className="rounded bg-emerald-900/40 px-2 py-1 text-xs text-emerald-200">Connected</span>
                ) : null}
                {item.has_oauth_json && ["Google Drive", "Gmail", "Google Calendar"].includes(item.provider) ? (
                  <button
                    onClick={() => onConnect(item.id)}
                    className="rounded bg-berry-700 px-2 py-1 text-xs text-white"
                    disabled={connectingId === item.id}
                  >
                    {connectingId === item.id ? "Connecting..." : "Connect"}
                  </button>
                ) : null}
                <button
                  onClick={() => onDelete(item.id)}
                  className="rounded border border-red-600 px-3 py-1 text-xs text-red-400 hover:bg-red-950"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
