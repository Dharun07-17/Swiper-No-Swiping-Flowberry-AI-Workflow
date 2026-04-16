const axios = require("axios");

const TOOL_LIST = `Available tools:
- reddit: fetches Reddit posts (ONLY when "reddit" or "r/something" mentioned)
- x: searches X/Twitter (ONLY when "twitter", "tweet", "x posts" mentioned)
- hackernews: searches Hacker News (ONLY when "hacker news", "hackernews", "tech news" mentioned)
- websearch: searches Google for any topic (use for general web searches, news, facts)
- csv: analyzes CSV files (ONLY when a .csv file path is mentioned)
- calendar: schedules meetings (ONLY when schedule/meeting/appointment mentioned)
- email: sends emails (ONLY when send/email explicitly mentioned)
- ollama: AI summarization and Q&A (always last before email)

Rules:
- Reply with ONLY a JSON array of tool names in order
- Use "websearch" for general questions, news, facts, current events
- Use "reddit" ONLY if reddit is mentioned
- Use "hackernews" ONLY if hacker news or tech news is mentioned
- ollama ALWAYS comes last (except email which comes after)
- DO NOT add tools not explicitly needed
- Examples:
  "Search Google for AI news" → ["websearch", "ollama"]
  "What is quantum computing" → ["websearch", "ollama"]
  "Latest news about Tesla" → ["websearch", "ollama"]
  "give top 5 posts from r/cats" → ["reddit", "ollama"]
  "summarize tech news" → ["hackernews", "ollama"]
  "analyze ./data/sample.csv" → ["csv", "ollama"]
  "schedule meeting tomorrow" → ["calendar", "ollama"]
  "search web and email me results" → ["websearch", "ollama", "email"]
- No explanation, just the JSON array.`;

async function planWithOllama(prompt) {
  const response = await axios.post(
    "http://localhost:11434/api/generate",
    {
      model:  "llama2",
      prompt: `${TOOL_LIST}\n\nUser: "${prompt}"\n\nJSON array:`,
      stream: false
    },
    { timeout: 60000 }
  );

  const raw = response.data?.response?.trim() || "";
  console.log("[Planner] Ollama raw response:", raw);

  const match = raw.match(/\[.*?\]/s);
  if (!match) throw new Error("No JSON array found");

  const tools = JSON.parse(match[0]);
  if (!Array.isArray(tools) || tools.length === 0) throw new Error("Empty array");

  const validTools = [
    "reddit", "x", "twitter", "hackernews", "hn",
    "websearch", "search", "google",
    "csv", "calendar", "schedule", "email", "ollama"
  ];

  let steps = tools
    .map(t => String(t).toLowerCase().trim())
    .filter(t => validTools.includes(t))
    .map(t => {
      if (t === "twitter") return "x";
      if (t === "hn") return "hackernews";
      if (t === "schedule") return "calendar";
      if (t === "search" || t === "google") return "websearch";
      return t;
    });

  steps = [...new Set(steps)];

  const hasEmail = steps.includes("email");
  steps = steps.filter(t => t !== "ollama" && t !== "email");
  steps.push("ollama");
  if (hasEmail) steps.push("email");

  const finalSteps = steps.map(tool => ({ tool, input: prompt }));
  if (finalSteps.length === 0) throw new Error("No valid tools");

  console.log("[Planner] Selected tools:", finalSteps.map(s => s.tool));
  return { steps: finalSteps };
}

function keywordFallback(prompt) {
  const lower = prompt.toLowerCase();
  const steps = [];

  // CSV
  if (lower.includes(".csv") && (lower.includes("./") || lower.includes("data/"))) {
    steps.push({ tool: "csv", input: prompt });
  }

  // Calendar
  if (
    (lower.includes("schedule") || lower.includes("meeting") || lower.includes("appointment")) &&
    !lower.includes("news")
  ) {
    steps.push({ tool: "calendar", input: prompt });
  }

  // Hacker News
  if (lower.includes("hacker news") || lower.includes("hackernews") || lower.includes("tech news")) {
    steps.push({ tool: "hackernews", input: prompt });
  }

  // Reddit
  if (lower.includes("reddit") || lower.match(/r\/[a-z]/i)) {
    steps.push({ tool: "reddit", input: prompt });
  }

  // X/Twitter
  if (lower.includes("twitter") || lower.includes("tweet") || lower.includes("x post")) {
    steps.push({ tool: "x", input: prompt });
  }

  // Web Search
  if (
    lower.includes("search") ||
    lower.includes("google") ||
    lower.includes("look up") ||
    lower.includes("find info") ||
    lower.includes("what is") ||
    lower.includes("who is") ||
    lower.includes("how to") ||
    lower.includes("latest news") ||
    lower.includes("current")
  ) {
    if (!steps.some(s => ["reddit", "hackernews", "x"].includes(s.tool))) {
      steps.push({ tool: "websearch", input: prompt });
    }
  }

  const needsEmail =
    lower.includes("send to ")       ||
    lower.includes("email to ")      ||
    lower.includes("send via email") ||
    lower.includes("email me")       ||
    lower.includes("send me")        ||
    lower.includes("notify");

  // If nothing matched, use websearch as default (better than ollama alone)
  if (steps.length === 0) {
    steps.push({ tool: "websearch", input: prompt });
  }

  steps.push({ tool: "ollama", input: prompt });
  if (needsEmail) steps.push({ tool: "email", input: prompt });

  console.log("[Planner] Keyword fallback tools:", steps.map(s => s.tool));
  return { steps };
}

async function planWorkflow(prompt) {
  if (!prompt || typeof prompt !== "string" || prompt.trim() === "") {
    return { steps: [] };
  }

  try {
    return await planWithOllama(prompt);
  } catch (err) {
    console.warn("[Planner] Ollama failed, using keyword fallback:", err.message);
    return keywordFallback(prompt);
  }
}

module.exports = { planWorkflow };
