# Media Worker (spellcheck)

This is the Cloudflare Worker that looks up books, movies, TV shows, and songs for the Currently fields (Reading, Watching, Listening). It keeps the API keys out of the public repo and out of the app.

The file here, `spellcheck-media-worker.js`, is a copy of what is deployed. If the two ever differ, the deployed version is what runs. Check before you edit.

## Where it runs

- Cloudflare dashboard, Workers & Pages, Worker name `spellcheck`.
- Address: `https://spellcheck.nnirema.workers.dev`. The app has this in `MEDIA_WORKER_BASE` in `index.html`.
- It is a separate Worker from the push Worker (`spellcheck-push`). Do not mix them up.
- It has no cron trigger. It only answers requests.

## Endpoints

All three are GET requests with a `?q=` search text. They return `{ "result": { title, subtitle, url, image } }`, or `{ "result": null }` when nothing matches.

- `/spotify?q=` returns the best matching track.
- `/tmdb?q=` returns the best matching movie or TV show.
- `/googlebooks?q=` returns the best matching book.

The app calls these from `fetchMediaMatch` in `index.html`, using the kind for each field: Reading uses `googlebooks`, Watching uses `tmdb`, Listening uses `spotify`.

## Secrets

Four secrets, set in Cloudflare under Settings > Variables and Secrets:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `TMDB_API_KEY`
- `GOOGLE_BOOKS_API_KEY`

Never put any of these in this repo. The repo is public. The code only refers to them by name.

If `GOOGLE_BOOKS_API_KEY` is missing, book search still works but shares Google's lower, shared rate limit, which caused 429 errors before.

## Known risk: the endpoints are public

The Worker allows requests from anywhere (`Access-Control-Allow-Origin: *`) and has no rate limit. The address is in this public repo, so anyone who finds it can use up the Spotify, TMDb, and Google Books quotas. It is unlikely, but possible.

Cheap fixes, when we choose to do them:

1. Only answer requests whose `Origin` is `https://ninaprojects.github.io`.
2. Add a Cloudflare rate limit on the Worker.
3. Cache results for repeat searches, so the same title never hits the services twice.

Any change here must be tested from the real app before it ships. The app does not send credentials, so an Origin check must still allow the app's own address.

## How to change it

1. Edit `spellcheck-media-worker.js` in this repo.
2. In Cloudflare, open the Worker, click Edit code, select everything, paste the new file, and click Deploy.
3. Test by searching for a book, a movie, and a song in a profile's Currently fields.

Tell Nina before deploying.

## Rollback

Paste the previous version of `spellcheck-media-worker.js` from this repo's history into Edit code and click Deploy.
