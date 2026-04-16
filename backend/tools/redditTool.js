async function runReddit(query) {
  try {
    const lower = query.toLowerCase();

    // Extract subreddit if mentioned (e.g. r/cats, r/worldnews)
    const subredditMatch = query.match(/r\/([a-zA-Z0-9_]+)/);
    const subreddit = subredditMatch?.[1] || null;

    // Extract limit if mentioned (e.g. top 5, top 10)
    const limitMatch = query.match(/top\s+(\d+)/i);
    const limit = limitMatch ? parseInt(limitMatch[1]) : 10;

    let url;

    if (subreddit) {
      // Specific subreddit requested
      if (lower.includes("top") && lower.includes("all time")) {
        url = `https://www.reddit.com/r/${subreddit}/top.json?t=all&limit=${limit}`;
      } else if (lower.includes("top") && lower.includes("today")) {
        url = `https://www.reddit.com/r/${subreddit}/top.json?t=day&limit=${limit}`;
      } else if (lower.includes("top") && lower.includes("week")) {
        url = `https://www.reddit.com/r/${subreddit}/top.json?t=week&limit=${limit}`;
      } else if (lower.includes("top") && lower.includes("month")) {
        url = `https://www.reddit.com/r/${subreddit}/top.json?t=month&limit=${limit}`;
      } else if (lower.includes("top") && lower.includes("year")) {
        url = `https://www.reddit.com/r/${subreddit}/top.json?t=year&limit=${limit}`;
      } else if (lower.includes("new") || lower.includes("latest")) {
        url = `https://www.reddit.com/r/${subreddit}/new.json?limit=${limit}`;
      } else if (lower.includes("hot") || lower.includes("top")) {
        url = `https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}`;
      } else {
        url = `https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}`;
      }

    } else if (lower.includes("top") && lower.includes("all time")) {
      url = `https://www.reddit.com/r/all/top.json?t=all&limit=${limit}`;
    } else if (lower.includes("top") && lower.includes("today")) {
      url = `https://www.reddit.com/r/all/top.json?t=day&limit=${limit}`;
    } else if (lower.includes("top") && lower.includes("week")) {
      url = `https://www.reddit.com/r/all/top.json?t=week&limit=${limit}`;
    } else if (lower.includes("top") && lower.includes("month")) {
      url = `https://www.reddit.com/r/all/top.json?t=month&limit=${limit}`;
    } else if (lower.includes("front page") || lower.includes("home page")) {
      url = `https://www.reddit.com/.json?limit=${limit}`;
    } else if (lower.includes("new") || lower.includes("latest")) {
      url = `https://www.reddit.com/r/all/new.json?limit=${limit}`;
    } else if (lower.includes("rising")) {
      url = `https://www.reddit.com/r/all/rising.json?limit=${limit}`;
    } else if (lower.includes("hot")) {
      url = `https://www.reddit.com/r/all/hot.json?limit=${limit}`;
    } else {
      // Extract keywords for search
      const stopWords = /\b(give|show|get|find|fetch|search|me|the|a|an|on|in|about|compare|them|with|top|post|posts|from|reddit|best|worst)\b/gi;
      const keywords = query.replace(stopWords, " ").trim().split(/\s+/).filter(w => w.length > 2).slice(0, 3).join(" ");
      url = `https://www.reddit.com/search.json?q=${encodeURIComponent(keywords || query)}&sort=relevance&limit=${limit}`;
    }

    console.log("[Reddit] Fetching:", url);

    const response = await fetch(url, {
      headers: { "User-Agent": "ai-workflow-bot/1.0" }
    });

    if (!response.ok) throw new Error(`Reddit API error: ${response.status}`);

    const data  = await response.json();
    const posts = data?.data?.children?.map((c, i) => ({
      rank:      i + 1,
      title:     c.data.title,
      subreddit: c.data.subreddit_name_prefixed,
      score:     c.data.score,
      comments:  c.data.num_comments,
      url:       `https://reddit.com${c.data.permalink}`,
      type:      c.data.is_video ? "video" : c.data.post_hint || "text"
    })) || [];

    if (posts.length === 0) return [{ title: "No results found", url: "" }];

    console.log(`[Reddit] Got ${posts.length} posts from ${subreddit ? "r/" + subreddit : "r/all"}`);
    return posts;

  } catch (err) {
    console.warn("[Reddit] Error:", err.message);
    return [{ title: `[MOCK] Reddit result for: ${query}`, url: "#" }];
  }
}

module.exports = { runReddit };
