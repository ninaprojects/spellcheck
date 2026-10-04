// Spell Check media search proxy.
// Three endpoints, all take a ?q= query string:
//   GET /spotify?q=...      -> best-matching track from Spotify
//   GET /tmdb?q=...         -> best-matching movie or TV show from TMDb
//   GET /googlebooks?q=...  -> best-matching book from Google Books
//
// Needs four secrets set in the Worker's Settings > Variables and Secrets:
//   SPOTIFY_CLIENT_ID
//   SPOTIFY_CLIENT_SECRET
//   TMDB_API_KEY
//   GOOGLE_BOOKS_API_KEY

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders() },
  });
}

// Cached in module scope, so it survives across requests on a warm
// isolate and avoids re-authenticating with Spotify every single call.
// Worst case it just re-fetches, no harm done.
let cachedSpotifyToken = null;
let cachedSpotifyTokenExpiry = 0;

async function getSpotifyToken(env) {
  const now = Date.now();
  if (cachedSpotifyToken && now < cachedSpotifyTokenExpiry) {
    return cachedSpotifyToken;
  }
  const creds = btoa(`${env.SPOTIFY_CLIENT_ID}:${env.SPOTIFY_CLIENT_SECRET}`);
  const res = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      "Authorization": `Basic ${creds}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });
  if (!res.ok) throw new Error(`Spotify token request failed: ${res.status}`);
  const data = await res.json();
  cachedSpotifyToken = data.access_token;
  cachedSpotifyTokenExpiry = now + (data.expires_in - 60) * 1000;
  return cachedSpotifyToken;
}

async function searchSpotify(query, env) {
  const token = await getSpotifyToken(env);
  const url = `https://api.spotify.com/v1/search?q=${encodeURIComponent(query)}&type=track&limit=1`;
  const res = await fetch(url, { headers: { "Authorization": `Bearer ${token}` } });
  if (!res.ok) throw new Error(`Spotify search failed: ${res.status}`);
  const data = await res.json();
  const track = data.tracks && data.tracks.items && data.tracks.items[0];
  if (!track) return null;
  return {
    title: track.name,
    subtitle: track.artists.map(a => a.name).join(", "),
    url: track.external_urls.spotify,
    image: (track.album.images && track.album.images[0]) ? track.album.images[0].url : null,
  };
}

async function searchGoogleBooks(query, env) {
  // A key gives you your own quota instead of sharing Cloudflare's pool,
  // which is what was causing the 429 errors. Falls back to unauthenticated
  // if the key's ever missing, just at the old lower, shared rate limit.
  const keyParam = env.GOOGLE_BOOKS_API_KEY ? `&key=${env.GOOGLE_BOOKS_API_KEY}` : "";
  const url = `https://www.googleapis.com/books/v1/volumes?q=${encodeURIComponent(query)}&maxResults=1${keyParam}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Google Books search failed: ${res.status}`);
  const data = await res.json();
  const item = data.items && data.items[0];
  if (!item) return null;
  const info = item.volumeInfo || {};
  const authors = info.authors ? info.authors.join(", ") : null;
  // Google sometimes returns http:// thumbnails, force https so they
  // don't get blocked by the page loading over https.
  const thumb = info.imageLinks && (info.imageLinks.thumbnail || info.imageLinks.smallThumbnail);
  return {
    title: info.title || query,
    subtitle: authors || "Book",
    url: info.infoLink || info.previewLink || `https://books.google.com/books?id=${item.id}`,
    image: thumb ? thumb.replace(/^http:/, "https:") : null,
  };
}

async function searchTmdb(query, env) {
  const url = `https://api.themoviedb.org/3/search/multi?api_key=${env.TMDB_API_KEY}&query=${encodeURIComponent(query)}&include_adult=false`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`TMDb search failed: ${res.status}`);
  const data = await res.json();
  const match = (data.results || []).find(r => r.media_type === "movie" || r.media_type === "tv");
  if (!match) return null;
  const isMovie = match.media_type === "movie";
  const title = isMovie ? match.title : match.name;
  const dateStr = isMovie ? match.release_date : match.first_air_date;
  const year = dateStr ? dateStr.slice(0, 4) : null;
  return {
    title: year ? `${title} (${year})` : title,
    subtitle: isMovie ? "Movie" : "TV Show",
    url: `https://www.themoviedb.org/${match.media_type}/${match.id}`,
    image: match.poster_path ? `https://image.tmdb.org/t/p/w200${match.poster_path}` : null,
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
    }

    const query = url.searchParams.get("q");
    if (!query || !query.trim()) {
      return jsonResponse({ error: "Missing q parameter" }, 400);
    }

    try {
      if (url.pathname === "/spotify") {
        return jsonResponse({ result: await searchSpotify(query.trim(), env) });
      }
      if (url.pathname === "/tmdb") {
        return jsonResponse({ result: await searchTmdb(query.trim(), env) });
      }
      if (url.pathname === "/googlebooks") {
        return jsonResponse({ result: await searchGoogleBooks(query.trim(), env) });
      }
      return jsonResponse({ error: "Unknown endpoint" }, 404);
    } catch (err) {
      return jsonResponse({ error: err.message }, 500);
    }
  },
};
