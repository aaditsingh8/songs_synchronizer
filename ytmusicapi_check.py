from ytmusicapi import YTMusic

ytmusic = YTMusic("browser.json")
liked = ytmusic.get_liked_songs(limit=5)
for song in liked['tracks']:
    print(song['title'], '-', song['artists'][0]['name'])