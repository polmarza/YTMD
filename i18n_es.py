"""Traducción al español. Clave = texto en inglés del código; valor = texto en español.

Los {marcadores} deben ser los mismos en ambos lados. Comprueba que no falte nada con:
    python tools/check_i18n.py
"""

TEXTS = {
    # --- descargas y registro
    "   source: {codec} · {abr} kbps · {note}": "   origen: {codec} · {abr} kbps · {note}",
    "Downloading… {speed}": "Descargando… {speed}",
    "Converting and tagging…": "Convirtiendo y etiquetando…",
    "Anti-block pause: {secs} s…": "Pausa anti-bloqueo: {secs} s…",
    "Analyzing {url}": "Analizando {url}",
    "Couldn't read the link (private? try with cookies).": "No se pudo leer el enlace (¿privado? prueba con cookies).",
    "Album «{title}» · {songs}": "Álbum «{title}» · {songs}",
    "Playlist «{title}» · {songs}": "Lista «{title}» · {songs}",
    "Cancelled.": "Cancelado.",
    "Retrying the {n} that failed…": "Reintentando {n} que fallaron…",
    "↷ Already downloaded, skipping: {name}": "↷ Ya descargada, se salta: {name}",
    "↷ You already have it: {path}": "↷ Ya la tienes: {path}",
    "↷ You already had every song: nothing to download.": "↷ Ya tenías todas las canciones: no hay nada que descargar.",
    "↷ {n} already in your library: not downloaded again": "↷ {n} ya las tenías: no se descargan otra vez",
    " ({n} linked from other folders)": " ({n} enlazadas desde otras carpetas)",
    "↻ {n} song(s) failed (YouTube sometimes answers 403). Retry {k}/{total} in {secs} s…":
        "↻ {n} canción(es) fallaron (YouTube a veces responde 403). Reintento {k}/{total} en {secs} s…",
    "＋ {n} link(s) added to the queue": "＋ {n} enlace(s) añadidos a la cola",
    "⚠ Ignored {n} links that aren't from YouTube.": "⚠ Ignorados {n} enlaces que no son de YouTube.",
    "✖ Player: {msg}": "✖ Reproductor: {msg}",
    "✖ Doesn't exist: {path}": "✖ No existe: {path}",
    "Updating «{title}»…": "Actualizando «{title}»…",
    "Queue restored: {n} pending. Press «Resume».": "Cola restaurada: {n} pendiente(s). Pulsa «Reanudar».",
    "«Skip already downloaded» turned on so songs aren't duplicated.":
        "«Saltar ya descargadas» activado para no duplicar canciones.",

    # --- formatos y opciones
    "FLAC (lossless)": "FLAC (sin pérdida)",
    "WAV (uncompressed PCM)": "WAV (PCM sin comprimir)",
    "Original (no re-encoding)": "Original (sin recodificar)",
    "No pauses": "Sin pausa",
    "Careful (3–8 s)": "Prudente (3–8 s)",
    "Safe (10–20 s)": "Segura (10–20 s)",
    "None": "Ninguno",
    "Format": "Formato",
    "Cookies": "Cookies",
    "Pauses": "Pausas",
    "FLAC: lossless, with cover art and tags (recommended).": "FLAC: sin pérdida y con portada/etiquetas (recomendado).",
    "WAV: raw PCM, the easiest to decode on a microcontroller; cover art as a separate .jpg.":
        "WAV: PCM puro, el más fácil de decodificar en un microcontrolador; portada como .jpg aparte.",
    "MP3 320: maximum compatibility (DFPlayer, VS1053…), but re-encodes with loss.":
        "MP3 320: máxima compatibilidad (DFPlayer, VS1053…), pero recodifica con pérdida.",
    "Original: the Opus/AAC exactly as YouTube serves it, untouched.":
        "Original: el Opus/AAC tal cual lo sirve YouTube, sin tocar.",
    "Uses the YouTube Music session of that browser.": "Usa la sesión de YouTube Music de ese navegador.",
    "With Premium it unlocks AAC 256 kbps and lets you download your private playlists.":
        "Con Premium desbloquea AAC 256 kbps y permite bajar tus listas privadas.",
    "Random wait before each song so YouTube doesn't throttle you.":
        "Espera aleatoria antes de cada canción para que YouTube no te frene.",
    "For big playlists, or if you use your account's cookies, «Safe» is better.":
        "Para listas grandes o si usas cookies de tu cuenta, mejor «Segura».",
    "CD format: the most compatible with I2S DACs and decoders.":
        "Formato de CD: el más compatible con DACs I2S y decodificadores.",
    "ASCII-only names": "Nombres solo ASCII",
    "No accents, ñ or spaces: in case your firmware reads the SD card without long names.":
        "Sin tildes, ñ ni espacios: por si tu firmware lee la SD sin nombres largos.",
    "Cover as separate .jpg": "Portada .jpg aparte",
    "Skip already downloaded": "Saltar ya descargadas",
    "Doesn't download again what you already have (nor another video of the same song).":
        "No vuelve a bajar lo que ya tienes (ni otro vídeo de la misma canción).",
    "Folder": "Carpeta",
    "Music folder": "Carpeta de música",
    "Change…": "Cambiar…",
    "Open": "Abrir",

    # --- navegación y pantallas
    "My Music": "Mi Música",
    "Home": "Inicio",
    "Songs": "Canciones",
    "Downloads": "Descargas",
    "Downloads ({n})": "Descargas ({n})",
    "Settings": "Configuración",
    "Download": "Descargar",
    "Your library": "Tu biblioteca",
    "Search your playlists, albums and artists": "Buscar en tus listas, álbumes y artistas",
    "Nothing here yet. Go to <b>Downloads</b> and paste a YouTube Music link.":
        "Aún no hay nada. Ve a <b>Descargas</b> y pega un enlace de YouTube Music.",
    "All": "Todo",
    "Playlists": "Listas",
    "Albums": "Álbumes",
    "Loose": "Sueltas",
    "Loose songs": "Canciones sueltas",
    "Library": "Biblioteca",
    "Album": "Álbum",
    "Playlist": "Lista",
    "ALBUM": "ÁLBUM",
    "PLAYLIST": "LISTA",
    "SONG": "CANCIÓN",
    "Automatic playlist": "Lista automática",
    "Liked Music": "Música que me gusta",
    "Classify this collection as a playlist or an album": "Clasifica esta colección como lista o como álbum",
    "Update: downloads only the new songs of the playlist": "Actualizar: descarga solo las canciones nuevas de la lista",
    "Search this collection": "Buscar en esta colección",
    "by {artist}": "de {artist}",
    "Your whole library": "Toda tu biblioteca",
    "Songs downloaded on their own": "Canciones descargadas sueltas",
    "Play": "Reproducir",
    "Shuffle": "Aleatorio",
    "Show in {app}": "Mostrar en {app}",
    "Explorer": "el Explorador",
    "the file manager": "el gestor de archivos",
    "Mute": "Silenciar",
    "Repeat": "Repetir",
    "Nothing playing": "Nada sonando",
    "Pick a song from your library": "Elige una canción de tu biblioteca",

    # --- cola de descargas
    "Import from my account": "Importar desde mi cuenta",
    "Choose playlists (private ones too), Liked Music and saved albums from your YouTube Music. Uses the browser selected in «Cookies».":
        "Elige listas (también privadas), «Música que me gusta» y álbumes guardados de tu YouTube Music. Usa el navegador de «Cookies».",
    "Queue": "Cola",
    "Pause": "Pausar",
    "Resume": "Reanudar",
    "Clear": "Limpiar",
    "Removes finished or cancelled downloads from the list": "Quita de la lista las descargas terminadas o canceladas",
    "The queue is empty. Add links with the form or import from your account.":
        "La cola está vacía. Añade enlaces con el formulario o importa desde tu cuenta.",
    "Show log": "Mostrar registro",
    "Hide log": "Ocultar registro",
    "Add links": "Añadir enlaces",
    "Paste one or more YouTube Music links, one per line: songs, albums or playlists (your private ones too, with cookies).":
        "Pega uno o varios enlaces de YouTube Music, uno por línea: canciones, álbumes o listas (también las tuyas privadas, con cookies).",
    "Add to queue": "Añadir a la cola",
    "Queued": "En cola",
    "Retry": "Reintentar",
    "Remove from the queue / cancel": "Quitar de la cola / cancelar",
    "Cancelling…": "Cancelando…",
    "Analyzing link…": "Analizando enlace…",
    "{n} item pending": "{n} pendiente",
    "{n} items pending": "{n} pendientes",
    " · paused": " · en pausa",
    "Error: {error}": "Error: {error}",
    "Cancelled · {n} downloaded": "Cancelado · {n} descargadas",
    "Couldn't download ({n} errors, see the log)": "No se pudo descargar ({n} errores, mira el registro)",
    "Done · {n} new": "Hecho · {n} nuevas",
    " · {n} with errors": " · {n} con error",
    " · {n} already in your library": " · {n} ya las tenías",
    "Starts in {secs} s (anti-block pause)": "Empieza en {secs} s (pausa anti-bloqueo)",
    "YouTube has throttled the downloads": "YouTube ha frenado las descargas",
    "YouTube has started rejecting requests (too many in a row).":
        "YouTube ha empezado a rechazar peticiones (demasiadas seguidas).",
    "I've paused the queue. Wait a while (30–60 min), set the pauses to «Safe» and resume: what's already downloaded is skipped.":
        "He pausado la cola. Espera un rato (30–60 min), pon las pausas en «Segura» y reanuda: lo ya descargado se salta.",

    # --- importar
    "Import from YouTube Music": "Importar desde YouTube Music",
    "Choose your browser": "Elige tu navegador",
    "To read your library, choose in «Cookies» the browser where you're signed in to YouTube Music (for example, chrome) and press Import again.":
        "Para leer tu biblioteca, elige en «Cookies» el navegador donde tienes abierta tu sesión de YouTube Music (por ejemplo, chrome) y vuelve a pulsar Importar.",
    "There is no YouTube session signed in on {browser}. Sign in at music.youtube.com with your account and try again.":
        "No hay una sesión de YouTube iniciada en {browser}. Entra en music.youtube.com con tu cuenta y vuelve a probar.",
    "Reading your library with the {browser} session…": "Leyendo tu biblioteca con la sesión de {browser}…",
    "Couldn't read your library: {error}": "No se pudo leer tu biblioteca: {error}",
    "Name": "Nombre",
    "Details": "Detalle",
    "In your library": "En tu biblioteca",
    "Select what I don't have": "Marcar lo que no tengo",
    "Clear selection": "Desmarcar todo",
    "Cancel": "Cancelar",
    "Add {n} to queue": "Añadir {n} a la cola",
    "Yes · {songs}": "Sí · {songs}",
    "Not supported": "No compatible",
    "You already have it: if you select it, only what's new will be downloaded.":
        "Ya la tienes: si la marcas, solo se descargará lo nuevo.",
    "YouTube doesn't allow reading this kind of automatic playlist (Recaps, YouTube Music playlists, mixes). Tip: add its songs to a playlist of your own.":
        "YouTube no deja leer este tipo de lista automática (Recaps, listas de YouTube Music, mixes). Truco: añade sus canciones a una lista tuya.",
    "{playlists} and {albums} in your account. Select what you want to download: songs you already have aren't downloaded again (if they're in another folder, the playlist links them).":
        "{playlists} y {albums} en tu cuenta. Marca lo que quieras descargar: las canciones que ya tengas no se vuelven a bajar (si están en otra carpeta, la lista las enlaza).",
    "{selected} selected · {songs}": "{selected} seleccionadas · {songs}",
    " + {n} without a count (YouTube doesn't give the number of songs of albums)":
        " + {n} sin recuento (YouTube no da el nº de canciones de los álbumes)",
    " · up to ~{gb} GB (less if you already have part of it)": " · hasta ~{gb} GB (menos si ya tienes parte)",
    "⚠ That's a lot: it will take hours. Use «Safe» pauses and let the queue work through it; you can pause it whenever you like.":
        "⚠ Son muchas: tardará horas. Usa pausas «Segura» y deja que la cola vaya haciendo; puedes pausarla cuando quieras.",

    # --- configuración y actualizaciones
    "Language": "Idioma",
    "The app restarts to apply the change.": "La app se reinicia para aplicar el cambio.",
    "Change language": "Cambiar idioma",
    "The app will restart to apply the language.": "La app se reiniciará para aplicar el idioma.",
    "The download queue will be kept, paused, so you can resume it.":
        "La cola de descargas se conservará en pausa, para que puedas reanudarla.",
    "Updates": "Actualizaciones",
    "YT Music Downloader {version}": "YT Music Downloader {version}",
    "Check for updates": "Buscar actualizaciones",
    "Update yt-dlp": "Actualizar yt-dlp",
    "If downloads stop working, updating yt-dlp almost always fixes it (YouTube changes often).":
        "Si las descargas dejan de funcionar, casi siempre se arregla actualizando yt-dlp (YouTube cambia a menudo).",
    "Restart now": "Reiniciar ahora",
    "Looking for updates only asks GitHub for the latest published version, at most once a day. Nothing about you is sent.":
        "Buscar actualizaciones solo le pregunta a GitHub cuál es la última versión publicada, como mucho una vez al día. No se envía nada tuyo.",
    "Update to {version}": "Actualizar a {version}",
    "Download {version}": "Descargar {version}",
    "See what's new": "Ver novedades",
    "Update": "Actualizar",
    "Not now": "Ahora no",
    "A new version is available: <b>{tag}</b> (you have {current}).":
        "Hay una versión nueva: <b>{tag}</b> (tienes la {current}).",
    "Version {tag} is available.": "Hay una versión nueva: {tag}.",
    "This copy has no repository configured (GITHUB_REPO in version.py).":
        "Esta copia no tiene un repositorio configurado (GITHUB_REPO en version.py).",
    "Checking…": "Buscando…",
    "Couldn't check: {error}": "No se pudo comprobar: {error}",
    "You're up to date (version {version}).": "Estás al día (versión {version}).",
    "Wait for the current download to finish before updating.":
        "Espera a que termine la descarga en curso para actualizar.",
    "Updating…": "Actualizando…",
    "Couldn't update: {error}": "No se pudo actualizar: {error}",
    "Already up to date.": "Ya estás al día.",
    "Updated ({old} → {new}). Restart to use the new version.":
        "Actualizada ({old} → {new}). Reinicia para usar la versión nueva.",
    "Updating yt-dlp…": "Actualizando yt-dlp…",
    "Couldn't update yt-dlp: {error}": "No se pudo actualizar yt-dlp: {error}",
    "yt-dlp is already on the latest version ({version}).": "yt-dlp ya está en la última versión ({version}).",
    "yt-dlp updated: {before} → {after}. Restart to use it.":
        "yt-dlp actualizado: {before} → {after}. Reinicia para usarlo.",
    "This copy wasn't installed with git, so it can't update itself.":
        "Esta copia no se instaló con git, así que no puede actualizarse sola.",
    "git pull failed": "Ha fallado git pull",
    "exit code {code}": "código {code}",

    # --- plurales y duraciones
    "{n} song": "{n} canción",
    "{n} songs": "{n} canciones",
    "{n} track": "{n} pista",
    "{n} tracks": "{n} pistas",
    "{n} album": "{n} álbum",
    "{n} albums": "{n} álbumes",
    "{n} playlist": "{n} lista",
    "{n} playlists": "{n} listas",
    "{n} minute": "{n} minuto",
    "{n} minutes": "{n} minutos",
    "{n} hour": "{n} hora",
    "{n} hours": "{n} horas",
    "{hours} and {minutes}": "{hours} y {minutes}",
}
