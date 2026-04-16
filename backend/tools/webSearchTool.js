const axios = require("axios");
require("dotenv").config();

async function runWebSearch(query) {
  try {
    console.log("[WebSearch] Searching Google for:", query);

    if (!process.env.SERPAPI_KEY) {
      console.warn("[WebSearch] No SERPAPI_KEY in .env, using mock");
      return [
        { title: `[MOCK] Result 1 for: ${query}`, url: "#", snippet: "Mock search result" },
        { title: `[MOCK] Result 2 for: ${query}`, url: "#", snippet: "Mock search result" }
      ];
    }

    const response = await axios.get("https://serpapi.com/search.json", {
      params: {
        q:             query,
        api_key:       process.env.SERPAPI_KEY,
        engine:        "google",
        num:           10,
        hl:            "en",
        gl:            "us"
      },
      timeout: 15000
    });

    const data = response.data;
    const results = [];

    // Knowledge graph summary
    if (data.knowledge_graph) {
      const kg = data.knowledge_graph;
      results.push({
        type:        "knowledge_graph",
        title:       kg.title,
        description: kg.description,
        source:      kg.source?.name || "Wikipedia",
        url:         kg.source?.link || "#"
      });
    }

    // Organic results
    if (data.organic_results) {
      data.organic_results.slice(0, 8).forEach(r => {
        results.push({
          type:    "organic",
          title:   r.title,
          url:     r.link,
          snippet: r.snippet,
          source:  r.source || new URL(r.link).hostname
        });
      });
    }

    // Related questions (People Also Ask)
    if (data.related_questions) {
      data.related_questions.slice(0, 3).forEach(q => {
        results.push({
          type:     "question",
          question: q.question,
          answer:   q.snippet,
          source:   q.title,
          url:      q.link
        });
      });
    }

    console.log(`[WebSearch] Found ${results.length} results`);
    return results;

  } catch (err) {
    console.error("[WebSearch] Error:", err.message);
    return [{ type: "error", title: `Search failed: ${err.message}`, url: "#", snippet: "" }];
  }
}

module.exports = { runWebSearch };
