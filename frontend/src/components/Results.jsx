export default function Results({ results, theme }) {
  if (!results || results.length === 0) return null;

  const toolColors = {
    reddit:     "#ff6314",
    ollama:     "#4d9fff",
    x:          "#1da1f2",
    twitter:    "#1da1f2",
    hackernews: "#ff6600",
    hn:         "#ff6600",
    csv:        "#28a745",
    calendar:   "#ffc107",
    email:      "#dc3545",
    websearch:  "#4285f4"
  };

  function formatScore(n) {
    if (!n && n !== 0) return "";
    return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
  }

  function renderWebSearch(output) {
    if (!Array.isArray(output)) return null;

    return (
      <div>
        {output.map((item, i) => (
          <div key={i} style={{ borderBottom: i < output.length - 1 ? `1px solid ${theme.border}` : "none", padding: "12px 0" }}>
            {item.type === "knowledge_graph" && (
              <div style={{ background: "#111", borderRadius: 6, padding: 12, marginBottom: 4 }}>
                <span style={{ fontSize: 10, color: "#4285f4", fontFamily: "monospace", textTransform: "uppercase" }}>Knowledge Graph</span>
                <p style={{ color: theme.text, fontSize: 15, fontWeight: 700, margin: "4px 0" }}>{item.title}</p>
                <p style={{ color: theme.muted, fontSize: 13, margin: 0, lineHeight: 1.5 }}>{item.description}</p>
                {item.url && item.url !== "#" && (
                  <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "#4285f4", fontSize: 12, textDecoration: "none" }}>
                    {item.source} →
                  </a>
                )}
              </div>
            )}

            {item.type === "question" && (
              <div style={{ padding: "4px 0" }}>
                <p style={{ color: theme.accent, fontSize: 14, fontWeight: 600, margin: "0 0 4px 0" }}>❓ {item.question}</p>
                <p style={{ color: theme.text, fontSize: 13, margin: 0, lineHeight: 1.5 }}>{item.answer}</p>
                {item.url && (
                  <a href={item.url} target="_blank" rel="noreferrer" style={{ color: theme.muted, fontSize: 11, textDecoration: "none" }}>
                    {item.source} →
                  </a>
                )}
              </div>
            )}

            {item.type === "organic" && (
              <div>
                <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "#4285f4", fontSize: 14, textDecoration: "none", display: "block", marginBottom: 4 }}>
                  {item.title}
                </a>
                <p style={{ color: "#4caf50", fontSize: 11, margin: "0 0 4px 0", fontFamily: "monospace" }}>{item.source}</p>
                <p style={{ color: theme.muted, fontSize: 13, margin: 0, lineHeight: 1.5 }}>{item.snippet}</p>
              </div>
            )}

            {!item.type && item.title && (
              <div>
                <a href={item.url} target="_blank" rel="noreferrer" style={{ color: "#4285f4", fontSize: 14, textDecoration: "none" }}>
                  {item.title}
                </a>
                {item.snippet && <p style={{ color: theme.muted, fontSize: 13, margin: "4px 0 0 0" }}>{item.snippet}</p>}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  function renderCSVOutput(output) {
    if (!output) return <p style={{ color: theme.muted, fontSize: 14 }}>No data</p>;

    if (output.error) {
      return (
        <div style={{ padding: 12, background: "#2a1010", borderRadius: 6 }}>
          <p style={{ color: theme.error, margin: 0, fontSize: 14 }}>{output.error}</p>
          {output.suggestion && <p style={{ color: theme.muted, margin: "8px 0 0 0", fontSize: 13 }}>{output.suggestion}</p>}
          {output.samplePath && <p style={{ color: theme.muted, margin: "4px 0 0 0", fontSize: 12, fontFamily: "monospace" }}>Try: {output.samplePath}</p>}
        </div>
      );
    }

    return (
      <div>
        <div style={{ display: "flex", gap: 20, marginBottom: 16, padding: "12px 16px", background: "#111", borderRadius: 6 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span style={{ fontSize: 11, color: theme.muted, textTransform: "uppercase", letterSpacing: 1 }}>Rows</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: theme.success, fontFamily: "monospace" }}>{output.rowCount}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span style={{ fontSize: 11, color: theme.muted, textTransform: "uppercase", letterSpacing: 1 }}>Columns</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: theme.accent, fontFamily: "monospace" }}>{output.columns?.length}</span>
          </div>
        </div>

        {output.columns && (
          <p style={{ color: theme.muted, fontSize: 13, marginBottom: 12 }}>
            Fields: <span style={{ color: theme.text }}>{output.columns.join(", ")}</span>
          </p>
        )}

        {output.statistics && (
          <div style={{ marginBottom: 16, overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: `2px solid ${theme.border}` }}>
                  <th style={{ padding: "8px 12px", textAlign: "left", color: theme.muted }}>Column</th>
                  <th style={{ padding: "8px 12px", textAlign: "left", color: theme.muted }}>Type</th>
                  <th style={{ padding: "8px 12px", textAlign: "left", color: theme.muted }}>Count</th>
                  <th style={{ padding: "8px 12px", textAlign: "left", color: theme.muted }}>Stats</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(output.statistics).map(([col, stats]) => (
                  <tr key={col} style={{ borderBottom: `1px solid ${theme.border}` }}>
                    <td style={{ padding: "8px 12px" }}><code style={{ color: theme.accent, fontSize: 12 }}>{col}</code></td>
                    <td style={{ padding: "8px 12px" }}>
                      <span style={{ color: stats.min !== undefined ? "#28a745" : "#888", fontSize: 12, fontFamily: "monospace" }}>
                        {stats.min !== undefined ? "numeric" : "text"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 12px", color: theme.muted, fontSize: 12 }}>{stats.count}</td>
                    <td style={{ padding: "8px 12px", color: theme.muted, fontSize: 12 }}>
                      {stats.min !== undefined
                        ? `min: ${stats.min} / max: ${stats.max} / avg: ${stats.avg}`
                        : `${stats.unique} unique values`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {output.sample && output.sample.length > 0 && (
          <div>
            <p style={{ color: theme.muted, fontSize: 12, marginBottom: 8 }}>Sample ({output.sample.length} rows):</p>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#111" }}>
                    {output.columns.map(col => (
                      <th key={col} style={{ padding: "6px 10px", textAlign: "left", color: theme.muted, borderBottom: `1px solid ${theme.border}`, whiteSpace: "nowrap" }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {output.sample.map((row, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${theme.border}` }}>
                      {output.columns.map(col => (
                        <td key={col} style={{ padding: "6px 10px", color: theme.text, whiteSpace: "nowrap" }}>
                          {row[col] || "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  }

  function renderCalendarOutput(output) {
    if (!output) return null;
    return (
      <div style={{ fontSize: 14, lineHeight: 2 }}>
        <p style={{ margin: 0, color: theme.text }}><span style={{ color: theme.muted }}>Title: </span>{output.title}</p>
        <p style={{ margin: 0, color: theme.text }}><span style={{ color: theme.muted }}>Date: </span>{output.date}</p>
        <p style={{ margin: 0, color: theme.text }}><span style={{ color: theme.muted }}>Time: </span>{output.time}</p>
        <p style={{ margin: 0, color: theme.muted, fontSize: 12 }}>{output.status}</p>
        {output.calendarURL && (
          <a href={output.calendarURL} target="_blank" rel="noreferrer"
            style={{ color: theme.accent, fontSize: 13, textDecoration: "none", display: "inline-block", marginTop: 8 }}>
            📅 Open in Google Calendar →
          </a>
        )}
      </div>
    );
  }

  function renderEmailOutput(output) {
    if (!output) return null;
    return (
      <div style={{ fontSize: 14, lineHeight: 2 }}>
        <p style={{ margin: 0, color: theme.text }}><span style={{ color: theme.muted }}>To: </span>{output.to}</p>
        <p style={{ margin: 0, color: theme.text }}><span style={{ color: theme.muted }}>Subject: </span>{output.subject}</p>
        <p style={{ margin: 0, color: theme.text }}><span style={{ color: theme.muted }}>Sent: </span>{output.timestamp}</p>
        <p style={{ margin: 0, color: theme.muted, fontSize: 12 }}>{output.status}</p>
        {output.preview && (
          <div style={{ marginTop: 10, padding: 10, background: "#111", borderRadius: 6, fontSize: 13, color: theme.muted }}>
            {output.preview}
          </div>
        )}
      </div>
    );
  }

  function renderOutput(result) {
    const { tool, output, error } = result;

    if (error) return <p style={{ color: theme.error, margin: 0, fontSize: 14 }}>{error}</p>;

    if (tool === "csv")       return renderCSVOutput(output);
    if (tool === "calendar" || tool === "schedule") return renderCalendarOutput(output);
    if (tool === "email")     return renderEmailOutput(output);
    if (tool === "websearch" || tool === "search" || tool === "google") return renderWebSearch(output);

    if (Array.isArray(output)) {
      return (
        <div>
          {output.map((item, j) => (
            <div key={j} style={{ display: "flex", gap: 12, padding: "10px 0", alignItems: "flex-start", borderBottom: j < output.length - 1 ? `1px solid ${theme.border}` : "none" }}>
              {item.rank && <span style={{ fontSize: 12, fontWeight: 700, minWidth: 28, paddingTop: 2, fontFamily: "monospace", flexShrink: 0, color: theme.muted }}>#{item.rank}</span>}
              <div style={{ flex: 1 }}>
                {item.title && (
                  <a href={item.url} target="_blank" rel="noreferrer" style={{ color: theme.accent, textDecoration: "none", fontSize: 14, lineHeight: 1.4, display: "block", marginBottom: 4 }}>
                    {item.title}
                  </a>
                )}
                {item.text && !item.title && (
                  <p style={{ color: theme.text, fontSize: 14, lineHeight: 1.5, margin: "0 0 6px 0" }}>{item.text}</p>
                )}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                  {item.subreddit && <span style={{ fontSize: 11, fontFamily: "monospace", color: "#ff6314" }}>{item.subreddit}</span>}
                  {item.score !== undefined && <span style={{ fontSize: 11, fontFamily: "monospace", color: theme.muted }}>▲ {formatScore(item.score)}</span>}
                  {item.comments !== undefined && <span style={{ fontSize: 11, fontFamily: "monospace", color: theme.muted }}>💬 {formatScore(item.comments)}</span>}
                  {item.points !== undefined && <span style={{ fontSize: 11, fontFamily: "monospace", color: theme.muted }}>▲ {formatScore(item.points)}</span>}
                  {item.author && <span style={{ fontSize: 11, fontFamily: "monospace", color: theme.muted }}>{item.author}</span>}
                  {item.source && <span style={{ fontSize: 10, fontFamily: "monospace", color: theme.muted }}>{item.source}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      );
    }

    return (
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.8, whiteSpace: "pre-wrap", color: theme.text, fontFamily: "system-ui, sans-serif" }}>
        {String(output)}
      </p>
    );
  }

  return (
    <div style={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 8, padding: 20, marginTop: 24, marginBottom: 60 }}>
      <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, marginTop: 0, fontFamily: "system-ui, sans-serif", color: theme.text }}>Results</h2>

      {results.map((result, i) => (
        <div key={i} style={{ background: theme.bg, border: `1px solid ${theme.border}`, borderRadius: 6, padding: 16, marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <span style={{ color: "#fff", background: toolColors[result.tool] || theme.accent, borderRadius: 4, padding: "3px 8px", fontSize: 11, fontWeight: 700, fontFamily: "monospace" }}>
              {result.tool.toUpperCase()}
            </span>
            {result.error && (
              <span style={{ background: "#2a1010", color: theme.error, borderRadius: 4, padding: "3px 8px", fontSize: 11, fontWeight: 700 }}>FAILED</span>
            )}
          </div>
          {renderOutput(result)}
        </div>
      ))}
    </div>
  );
}
