import yt_dlp

def descargar_video(url, path_salida='.'):
    opciones = {
        'outtmpl': f'{path_salida}/%(title)s.%(ext)s',
        'format': 'best[height<=720]/bestvideo[height<=720]+bestaudio/best',
        'merge_output_format': 'mp4'
    }

    with yt_dlp.YoutubeDL(opciones) as ydl:
        try:
            print(f"📥 Descargando desde: {url}")
            ydl.download([url])
            print("✅ Descarga completa")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    url = input("📥 Ingresá la URL del video de YouTube: ")
    descargar_video(url)
