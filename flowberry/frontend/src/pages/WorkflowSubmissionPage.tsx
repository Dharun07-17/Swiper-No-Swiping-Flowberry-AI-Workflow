import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

export default function WorkflowSubmissionPage() {
  const [prompt, setPrompt] = useState("");
  const [csvText, setCsvText] = useState("");
  const [csvName, setCsvName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function onSubmit() {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post<{ data: { workflow_id: string } }>("/workflows", { prompt });
      setWorkflowId(data.data.workflow_id);
      navigate(`/workflows/${data.data.workflow_id}`);
    } catch (err: any) {
      const message =
        err?.response?.data?.error?.message ||
        err?.response?.data?.message ||
        "Failed to create workflow. Please log in again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function onSubmitCsv() {
    if (!csvText.trim()) return;
    setLoading(true);
    setError(null);
    const usePrompt = prompt.trim() || "Analyze uploaded CSV";
    try {
      const { data } = await api.post<{ data: { workflow_id: string } }>("/workflows/csv", {
        prompt: usePrompt,
        csv_text: csvText,
      });
      setWorkflowId(data.data.workflow_id);
      navigate(`/workflows/${data.data.workflow_id}`);
    } catch (err: any) {
      const message =
        err?.response?.data?.error?.message ||
        err?.response?.data?.message ||
        "Failed to create CSV workflow. Please log in again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function onCsvFileChange(file: File | null) {
    if (!file) {
      setCsvText("");
      setCsvName(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setCsvText(String(reader.result || ""));
      setCsvName(file.name);
    };
    reader.readAsText(file);
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Create Workflow</h2>
      <textarea
        className="h-40 w-full rounded border border-zinc-700 bg-zinc-900 p-4 text-zinc-100"
        placeholder="Summarize today's reports, email them, and schedule a meeting tomorrow at 4 PM"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <button
        onClick={onSubmit}
        disabled={loading}
        className="rounded bg-berry-700 px-4 py-2 font-medium text-white disabled:opacity-50"
      >
        {loading ? "Submitting..." : "Run with Fizz"}
      </button>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900/70 p-4 space-y-3">
        <p className="text-sm text-zinc-300">CSV Upload (plain text)</p>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => onCsvFileChange(e.target.files?.[0] ?? null)}
          className="text-sm text-zinc-300"
        />
        {csvName ? <p className="text-xs text-zinc-400">Loaded: {csvName}</p> : null}
        <textarea
          className="h-32 w-full rounded border border-zinc-700 bg-zinc-900 p-3 text-xs text-zinc-100"
          placeholder="Or paste CSV text here"
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
        />
        <button
          onClick={onSubmitCsv}
          disabled={loading || !csvText.trim()}
          className="rounded border border-berry-700 px-4 py-2 text-sm text-berry-700 disabled:opacity-50"
        >
          {loading ? "Submitting..." : "Run CSV Analysis"}
        </button>
      </div>

      {error ? <p className="text-sm text-red-300">{error}</p> : null}
      {workflowId ? <p className="text-sm text-zinc-400">Workflow queued: {workflowId}</p> : null}
    </div>
  );
}
