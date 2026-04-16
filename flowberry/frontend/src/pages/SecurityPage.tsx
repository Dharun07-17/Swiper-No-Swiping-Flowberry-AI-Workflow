import { useEffect, useState } from "react";
import { api } from "../services/api";

type SetupData = {
  secret: string;
  otpauth_url: string;
};

export default function SecurityPage() {
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [setup, setSetup] = useState<SetupData | null>(null);
  const [otpCode, setOtpCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadStatus() {
    const res = await api.get("/auth/me");
    setMfaEnabled(Boolean(res.data.data?.mfa_enabled));
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function startSetup() {
    setError(null);
    setMessage(null);
    try {
      const res = await api.post<{ data: SetupData }>("/auth/mfa/setup");
      setSetup(res.data.data);
      setMessage("MFA setup created. Add it to Google Authenticator, then verify.");
    } catch (e: any) {
      setError(e?.response?.data?.error?.message ?? "Failed to start MFA setup");
    }
  }

  async function enableMfa() {
    setError(null);
    setMessage(null);
    try {
      await api.post("/auth/mfa/enable", { otp_code: otpCode });
      setSetup(null);
      setOtpCode("");
      await loadStatus();
      setMessage("MFA enabled.");
    } catch (e: any) {
      setError(e?.response?.data?.error?.message ?? "Failed to enable MFA");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Security</h2>
        <p className="text-sm text-zinc-400">Enable Google Authenticator for login MFA.</p>
      </div>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900/70 p-4 space-y-3">
        <p className="text-sm">
          Status:{" "}
          {mfaEnabled ? (
            <span className="text-emerald-300">Enabled</span>
          ) : (
            <span className="text-amber-300">Disabled</span>
          )}
        </p>

        {!mfaEnabled ? (
          <button onClick={startSetup} className="rounded bg-berry-700 px-3 py-1 text-sm font-medium text-white">
            Start MFA Setup
          </button>
        ) : null}

        {setup ? (
          <div className="space-y-2 rounded border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-200">
            <p className="text-xs text-zinc-400">
              Add this to Google Authenticator:
            </p>
            <div className="text-xs break-all">
              <span className="text-zinc-400">OTP URL:</span> {setup.otpauth_url}
            </div>
            <div className="text-xs">
              <span className="text-zinc-400">Secret:</span> {setup.secret}
            </div>
            <div className="space-y-2 pt-2">
              <input
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                maxLength={6}
                className="w-full rounded border border-zinc-700 bg-zinc-800 p-2"
                placeholder="Enter 6-digit code"
              />
              <button onClick={enableMfa} className="rounded bg-berry-700 px-3 py-1 text-sm font-medium text-white">
                Verify & Enable
              </button>
            </div>
          </div>
        ) : null}

        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
      </div>
    </div>
  );
}
