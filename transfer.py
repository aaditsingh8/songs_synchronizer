import warnings
import os

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
import pandas as pd

warnings.filterwarnings("ignore")
load_dotenv()

# --- CONFIG ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# --- AUTH ---
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-library-read playlist-read-private playlist-read-collaborative"
))

ytmusic = YTMusic("browser.json")

# --- FETCH ALL SPOTIFY LIKED SONGS ---
print("Fetching Spotify liked songs...")
liked_songs = []
results = sp.current_user_saved_tracks(limit=50)

while results:
    for item in results['items']:
        track = item['track']
        liked_songs.append({
            "title": track['name'],
            "artist": track['artists'][0]['name']
        })
    results = sp.next(results) if results['next'] else None

print(f"Found {len(liked_songs)} songs on Spotify.")

# --- TRANSFER TO YOUTUBE MUSIC ---
log = []

for i, song in enumerate(liked_songs):
    query = f"{song['title']} {song['artist']}"
    print(f"[{i+1}/{len(liked_songs)}] Searching: {query}")

    try:
        search_results = ytmusic.search(query, filter="songs", limit=1)
        if search_results:
            video_id = search_results[0]['videoId']
            ytmusic.rate_song(video_id, "LIKE")
            log.append({**song, "status": "success", "yt_id": video_id})
            print(f"  ✓ Found and liked")
        else:
            log.append({**song, "status": "not_found", "yt_id": None})
            print(f"  ✗ Not found")
    except Exception as e:
        log.append({**song, "status": f"error: {e}", "yt_id": None})
        print(f"  ✗ Error: {e}")

# --- EXPORT REPORT ---
df = pd.DataFrame(log)
df.to_csv("transfer_report.csv", index=False)

success = df[df['status'] == 'success'].shape[0]
print(f"\nDone! {success}/{len(liked_songs)} songs transferred.")
print("Report saved to transfer_report.csv")