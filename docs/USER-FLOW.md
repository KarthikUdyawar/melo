# Melo — User Flow

> How a user moves through the app from first open to organized library.

---

## App Entry

```mermaid
flowchart TD
    A([Open localhost:3000]) --> B[Load index.html]
    B --> C{GET /health}
    C --unreachable--> D[Show API unavailable banner]
    C --ok--> E{Read window.location.hash}
    E --> F["#/ → Library"]
    E --> G["#/favorites → Favorites"]
    E --> H["#/playlists → Playlists"]
    E --> I["#/playlists/:id → Playlist Detail"]
    E --> J["(default) → Library"]
```

---

## 1. Library Page

```mermaid
flowchart TD
    A([Library page loads]) --> B["GET /songs\nsort=created_at desc, limit=50"]
    B --> C{Songs exist?}
    C --no--> D["Empty state\n'No songs yet.' + Add Song button"]
    C --yes--> E[Render song list]
    E --> F{Any pending\nor processing?}
    F --yes--> G[Start 2s poll loop]
    G --> H["GET /songs every 2s"]
    H --> I{All done\nor failed?}
    I --no--> H
    I --yes--> J[Stop poll]
    F --no--> K[Idle]
```

### 1a. Filter / Search / Sort

```mermaid
flowchart LR
    A([User types search]) --> B[Debounce 300ms]
    B --> C["GET /songs?search=query"]
    C --> D[Re-render list]

    E([User picks status filter]) --> F["GET /songs?status=value"]
    F --> D

    G([User picks sort]) --> H["GET /songs?sort_by=field&order=asc|desc"]
    H --> D
```

### 1b. Pagination

```mermaid
flowchart TD
    A([User clicks Load more]) --> B["GET /songs?after=bookmark"]
    B --> C{bookmark returned?}
    C --null--> D[Hide Load more button]
    C --has value--> E[Append songs to list]
    E --> F[Update stored bookmark]
```

---

## 2. Add Song Flow

```mermaid
flowchart TD
    A([User clicks + Add Song]) --> B[Modal opens — Step 1]
    B --> C[User pastes YouTube URL]
    C --> D{Input empty?}
    D --yes--> E[Preview button disabled]
    D --no--> F([User clicks Preview])
    F --> G["POST /songs/preview"]
    G --> H{Result}
    H --422/502--> I[Show inline error]
    I --> C
    H --200--> J[Step 2: show thumbnail\ntitle · channel · duration]
    J --> K[User adjusts start / end / speed]
    K --> L{Action}
    L --Cancel--> M[Close modal]
    L --Add to Melo--> N["POST /songs\n{ url, start?, end?, speed? }"]
    N --> O[Modal closes]
    O --> P[Song in library — status: pending]
    P --> Q[Poll: pending → processing → done]
    Q --> R[Song card becomes playable]
```

---

## 3. Play a Song

```mermaid
flowchart TD
    A([User clicks song card]) --> B{Song status}
    B --pending/processing--> C[No action — card not interactive]
    B --failed--> D[Show Retry button]
    B --done--> E["player.loadSong(song)"]
    E --> F["audio.src = /api/songs/id/stream\naudio.play()"]
    F --> G[Player bar: thumbnail + title + channel]
    G --> H[Scrubber starts moving]
    H --> I[Active card: accent border + accent title]
```

### 3a. Player Controls

```mermaid
flowchart LR
    A([Play/Pause clicked\nor Space key]) --> B{audio.paused?}
    B --yes--> C[audio.play]
    B --no--> D[audio.pause]

    E([Scrubber dragged]) --> F[audio.currentTime = scrubber.value]
    G([audio.ontimeupdate]) --> H[scrubber.value = audio.currentTime]

    I([Song ends]) --> J[Reset play button]
```

---

## 4. Favorite Toggle

```mermaid
flowchart TD
    A([User clicks heart icon]) --> B{is_favorite?}
    B --false--> C[Heart fills immediately]
    C --> D["POST /favorites/song_id"]
    D --> E{Result}
    E --success--> F[Stays filled]
    E --error--> G[Reverts to outline]

    B --true--> H[Heart empties immediately]
    H --> I["DELETE /favorites/song_id"]
    I --> J{Result}
    J --success--> K[Stays empty]
    J --error--> L[Reverts to filled]
```

---

## 5. Favorites Page

```mermaid
flowchart TD
    A([User clicks Favorites in sidebar]) --> B["GET /favorites"]
    B --> C{Songs?}
    C --none--> D["'No favorites yet.'"]
    C --yes--> E[Render song card list]
    E --> F[Same play + favorite toggle actions apply]
```

---

## 6. Playlists Page

```mermaid
flowchart TD
    A([User clicks Playlists in sidebar]) --> B["GET /playlists"]
    B --> C{Playlists?}
    C --none--> D["'No playlists yet.' + New Playlist button"]
    C --yes--> E[Render playlist card grid]
    E --> F{User action}
    F --clicks card--> G["Navigate to #/playlists/:id"]
    F --clicks + New Playlist--> H[Inline name input appears]
    H --> I[User types name + Enter]
    I --> J["POST /playlists { name }"]
    J --> K[New card added to grid]
```

---

## 7. Playlist Detail Page

```mermaid
flowchart TD
    A(["Navigate to #/playlists/:id"]) --> B["GET /playlists/:id"]
    B --> C{Found?}
    C --no--> D["'Playlist not found.' + Back link"]
    C --yes--> E[Render ordered song list]
    E --> F{User action}
    F --clicks song--> G[Play song]
    F --clicks remove--> H["DELETE /playlists/:id/songs/:song_id"]
    H --> I[Re-render playlist]
```

---

## 8. Add Song to Playlist

```mermaid
flowchart TD
    A([User clicks ⋮ on song card]) --> B[Dropdown opens]
    B --> C{User picks}
    C --existing playlist--> D["POST /playlists/:id/songs/:song_id"]
    D --> E["Toast: 'Added to playlist name'"]
    C --+ New playlist--> F[Inline name input in dropdown]
    F --> G[User types name + Enter]
    G --> H["POST /playlists { name }"]
    H --> I["POST /playlists/:new_id/songs/:song_id"]
    I --> J["Toast: 'Added to new playlist name'"]
```

---

## 9. Delete a Song

```mermaid
flowchart TD
    A([User clicks ⋮ → Delete]) --> B["Confirm dialog:\n'Delete this song?\nThis cannot be undone.'"]
    B --> C{User choice}
    C --Cancel--> D[Close dialog]
    C --Delete--> E["DELETE /songs/:id"]
    E --> F[Song removed from list]
    F --> G{Was playing?}
    G --yes--> H[Player bar clears]
    G --no--> I[Done]
```

---

## 10. Error States

```mermaid
flowchart TD
    A([Any API action fails]) --> B["Toast: error message\n(red, 3s auto-dismiss)"]

    C([Song status = failed]) --> D["Card: red 'failed' pill + Retry button"]
    D --> E([User clicks Retry])
    E --> F["POST /songs same url+params"]
    F --> G[Restart add song flow]

    H([API unreachable on load]) --> I["Red banner:\n'Cannot reach API. Is the server running?'"]
    I --> J[Banner persists until page refresh]
```

---

## Navigation Overview

```mermaid
flowchart LR
    subgraph Sidebar ["Sidebar (always visible)"]
        L[Library]
        FAV[Favorites]
        PL[Playlists]
    end

    subgraph Pages
        LibPage["#/"]
        FavPage["#/favorites"]
        PlPage["#/playlists"]
        PlDetail["#/playlists/:id"]
    end

    subgraph Persistent
        Player["Player Bar\n(never unmounts)"]
    end

    L --> LibPage
    FAV --> FavPage
    PL --> PlPage
    PlPage --> PlDetail

    LibPage -.plays.-> Player
    FavPage -.plays.-> Player
    PlDetail -.plays.-> Player
```

---

## Keyboard Shortcuts

| Key     | Action                                   |
| ------- | ---------------------------------------- |
| `Space` | Play / pause current song                |
| `Esc`   | Close modal or dropdown                  |
| `Enter` | Submit inline input (playlist name, URL) |
