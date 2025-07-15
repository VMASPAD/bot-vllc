import os
import random
import subprocess
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import tempfile
import shutil
import requests  # Add this import for downloading the video

app = Flask(__name__)
CORS(app)

# Directorio para almacenar clips generados
CLIPS_DIR = "generated_clips"
if not os.path.exists(CLIPS_DIR):
    os.makedirs(CLIPS_DIR)

# Directorios permitidos para servir archivos estáticos
ALLOWED_STATIC_DIRS = ['out', 'public', 'assets', 'src']

VIDEO_URL = "https://portfoliotavm.com/n8n/milei/video.mp4"
VIDEO_PATH = "./video.mp4"

def is_safe_path(basedir, path, follow_symlinks=True):
    """Verifica que el path sea seguro y no salga del directorio base"""
    if follow_symlinks:
        matchpath = os.path.realpath(path)
        basedir = os.path.realpath(basedir)
    else:
        matchpath = os.path.abspath(path)
        basedir = os.path.abspath(basedir)
    return basedir == os.path.commonpath((basedir, matchpath))

def get_video_duration(video_path):
    """Obtiene la duración del video en segundos usando FFprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return None

def generate_random_clip(video_path, output_path, start_time, duration):
    """Genera un clip usando FFmpeg con formato 9:16"""
    try:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-vf', 'crop=ih*9/16:ih',  # Crop to 9:16 aspect ratio (width = height * 9/16)
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'fast',
            '-y',  # Sobrescribir archivo si existe
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return True
        else:
            print(f"FFmpeg error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error generating clip: {e}")
        return False

def download_video(url, output_path):
    """Descarga un video desde una URL y lo guarda en el path especificado"""
    try:
        print(f"Iniciando descarga del video desde {url}...")
        
        # Set timeout for the request
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        block_size = 8192  # 8KB blocks
        
        print(f"Tamaño del archivo: {total_size / (1024 * 1024):.2f} MB")
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Print progress every 10MB
                    if downloaded_size % (10 * 1024 * 1024) == 0:
                        progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                        print(f"Progreso: {progress:.1f}% ({downloaded_size / (1024 * 1024):.1f} MB)")
        
        print(f"✅ Video descargado exitosamente en {output_path}")
        print(f"📊 Tamaño final: {downloaded_size / (1024 * 1024):.2f} MB")
        return True
        
    except requests.exceptions.Timeout:
        print("❌ Error: Timeout al descargar el video")
        # Clean up partial download
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión al descargar el video: {e}")
        # Clean up partial download
        if os.path.exists(output_path):
            os.remove(output_path)
        return False
    except Exception as e:
        print(f"❌ Error inesperado descargando el video: {e}")
        # Clean up partial download
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

@app.route('/files/<directory>', methods=['GET'])
def list_directory_files(directory):
    """Lista archivos en un directorio específico"""
    try:
        if directory not in ALLOWED_STATIC_DIRS:
            return jsonify({"error": f"Directorio '{directory}' no permitido"}), 403
        
        dir_path = os.path.join('.', directory)
        
        if not os.path.exists(dir_path):
            return jsonify({"error": f"Directorio '{directory}' no existe"}), 404
        
        files = []
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path):
                file_size = os.path.getsize(item_path)
                files.append({
                    "name": item,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "download_url": f"/static/{directory}/{item}"
                })
            elif os.path.isdir(item_path):
                files.append({
                    "name": item,
                    "type": "directory",
                    "list_url": f"/files/{directory}/{item}"
                })
        
        return jsonify({
            "directory": directory,
            "path": dir_path,
            "files": files,
            "count": len(files)
        })
    
    except Exception as e:
        return jsonify({"error": f"Error listando archivos: {str(e)}"}), 500

@app.route('/files/<directory>/<path:subpath>', methods=['GET'])
def list_subdirectory_files(directory, subpath):
    """Lista archivos en un subdirectorio"""
    try:
        if directory not in ALLOWED_STATIC_DIRS:
            return jsonify({"error": f"Directorio '{directory}' no permitido"}), 403
        
        full_path = os.path.join('.', directory, subpath)
        
        # Verificar que el path es seguro
        if not is_safe_path(os.path.join('.', directory), full_path):
            return jsonify({"error": "Path no seguro"}), 403
        
        if not os.path.exists(full_path):
            return jsonify({"error": f"Path '{directory}/{subpath}' no existe"}), 404
        
        if os.path.isfile(full_path):
            # Si es un archivo, devolverlo
            return send_file(full_path)
        
        # Si es un directorio, listar contenido
        files = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isfile(item_path):
                file_size = os.path.getsize(item_path)
                files.append({
                    "name": item,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "download_url": f"/static/{directory}/{subpath}/{item}"
                })
            elif os.path.isdir(item_path):
                files.append({
                    "name": item,
                    "type": "directory",
                    "list_url": f"/files/{directory}/{subpath}/{item}"
                })
        
        return jsonify({
            "directory": f"{directory}/{subpath}",
            "path": full_path,
            "files": files,
            "count": len(files)
        })
    
    except Exception as e:
        return jsonify({"error": f"Error listando archivos: {str(e)}"}), 500

@app.route('/static/<directory>/<path:filename>', methods=['GET'])
def serve_static_file(directory, filename):
    """Sirve archivos estáticos desde directorios permitidos"""
    try:
        if directory not in ALLOWED_STATIC_DIRS:
            return jsonify({"error": f"Directorio '{directory}' no permitido"}), 403
        
        dir_path = os.path.join('.', directory)
        file_path = os.path.join(dir_path, filename)
        
        # Verificar que el path es seguro
        if not is_safe_path(dir_path, file_path):
            return jsonify({"error": "Path no seguro"}), 403
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        return send_file(file_path)
    
    except Exception as e:
        return jsonify({"error": f"Error sirviendo archivo: {str(e)}"}), 500

@app.route('/out/<path:filename>', methods=['GET'])
def serve_out_file(filename):
    """Sirve archivos desde el directorio ./out"""
    try:
        return send_from_directory('./out', filename)
    except Exception as e:
        return jsonify({"error": f"Error sirviendo archivo de out: {str(e)}"}), 500

@app.route('/public/<path:filename>', methods=['GET'])
def serve_public_file(filename):
    """Sirve archivos desde el directorio ./public"""
    try:
        return send_from_directory('./public', filename)
    except Exception as e:
        return jsonify({"error": f"Error sirviendo archivo público: {str(e)}"}), 500

@app.route('/directories', methods=['GET'])
def list_allowed_directories():
    """Lista todos los directorios permitidos y su contenido"""
    try:
        directories_info = []
        
        for directory in ALLOWED_STATIC_DIRS:
            dir_path = os.path.join('.', directory)
            if os.path.exists(dir_path):
                file_count = len([f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))])
                dir_count = len([f for f in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, f))])
                
                directories_info.append({
                    "name": directory,
                    "exists": True,
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "list_url": f"/files/{directory}",
                    "static_url": f"/static/{directory}/"
                })
            else:
                directories_info.append({
                    "name": directory,
                    "exists": False,
                    "list_url": f"/files/{directory}"
                })
        
        return jsonify({
            "allowed_directories": directories_info,
            "endpoints": {
                "list_files": "/files/<directory>",
                "serve_static": "/static/<directory>/<filename>",
                "out_files": "/out/<filename>",
                "public_files": "/public/<filename>"
            }
        })
    
    except Exception as e:
        return jsonify({"error": f"Error listando directorios: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def index():
    """Endpoint de bienvenida"""
    return jsonify({
        "message": "Servidor de generación de clips de video",
        "endpoints": {
            "/generate-clip": "POST - Generar un clip aleatorio",
            "/list-clips": "GET - Listar clips generados",
            "/download-clip/<filename>": "GET - Descargar clip específico",
            "/clear-clips": "DELETE - Eliminar todos los clips",
            "/files/<directory>": "GET - Listar archivos en directorio",
            "/static/<directory>/<filename>": "GET - Servir archivo estático",
            "/out/<filename>": "GET - Servir archivo desde ./out",
            "/public/<filename>": "GET - Servir archivo desde ./public",
            "/directories": "GET - Listar directorios disponibles"
        }
    })

@app.route('/generate-clip', methods=['POST'])
def generate_clip():
    """Genera un clip aleatorio del video especificado"""
    try:
        print("🎬 Iniciando generación de clip...")
        
        # Descargar el video si no existe localmente
        if not os.path.exists(VIDEO_PATH):
            print(f"📥 Video no encontrado localmente. Descargando desde {VIDEO_URL}...")
            download_success = download_video(VIDEO_URL, VIDEO_PATH)
            if not download_success:
                return jsonify({"error": "No se pudo descargar el video"}), 500
            print("✅ Descarga completada, continuando con el proceso...")
        else:
            print("✅ Video ya existe localmente, continuando...")

        # Verificar que el archivo existe después de la descarga
        if not os.path.exists(VIDEO_PATH):
            return jsonify({"error": f"El archivo {VIDEO_PATH} no existe después de la descarga"}), 404
        
        # Verificar que es un archivo MP4
        if not VIDEO_PATH.lower().endswith('.mp4'):
            return jsonify({"error": "Solo se aceptan archivos MP4"}), 400
        
        print("🔍 Obteniendo duración del video...")
        # Obtener duración del video
        video_duration = get_video_duration(VIDEO_PATH)
        if video_duration is None:
            return jsonify({"error": "No se pudo obtener la duración del video"}), 500
        
        print(f"⏱️ Duración del video: {video_duration:.2f} segundos")
        
        # Verificar que el video es lo suficientemente largo
        if video_duration < 60:
            return jsonify({"error": "El video debe tener al menos 60 segundos"}), 400
        
        print("🎯 Generando clip...")
        # Crear directorio público si no existe
        public_dir = "./public"
        if not os.path.exists(public_dir):
            os.makedirs(public_dir)
        # Limpiar archivos previos si existen
        video_file = os.path.join(public_dir, "sample-video.mp4")
        json_file = os.path.join(public_dir, "sample-video.json")
        
        if os.path.exists(video_file):
            os.remove(video_file)
        if os.path.exists(json_file):
            os.remove(json_file)
        
        # Crear directorio único para esta sesión (temporal)
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        session_dir = os.path.join(CLIPS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Duración aleatoria entre 30-60 segundos
        clip_duration = random.randint(30, 60)
        
        # Tiempo de inicio aleatorio (asegurar que el clip no se salga del video)
        max_start_time = video_duration - clip_duration
        if max_start_time <= 0:
            return jsonify({"error": "El video es demasiado corto para generar un clip de la duración requerida"}), 400
        
        start_time = random.uniform(0, max_start_time)
        
        # Nombre del archivo temporal
        temp_filename = f"clip_temp_{random.randint(1000, 9999)}.mp4"
        temp_path = os.path.join(session_dir, temp_filename)
        
        # Generar el clip en formato 9:16
        success = generate_random_clip(VIDEO_PATH, temp_path, start_time, clip_duration)

        if success:
            # Mover el archivo generado a ./public/sample-video.mp4
            final_path = os.path.join(public_dir, "sample-video.mp4")
            shutil.move(temp_path, final_path)

            # Ejecutar transcripción (esto debería crear el archivo JSON)
            print("Ejecutando transcripción...")
            subprocess.run(["node", "./sub.mjs", "./public/sample-video.mp4"], check=True)

            # Verificar que el archivo JSON fue creado
            if not os.path.exists(json_file):
                return jsonify({"error": "El archivo de transcripción no fue generado"}), 500

            # Ejecutar remotion render
            print("Ejecutando remotion render...")
            subprocess.run(["npx", "remotion", "render"], check=True)
            
            clip_info = {
                "filename": "sample-video.mp4",
                "start_time": round(start_time, 2),
                "duration": clip_duration,
                "download_url": f"/public/sample-video.mp4",
                "file_path": final_path,
                "aspect_ratio": "9:16",
                "out": "out/CaptionedVideo.mp4"
            }
            
            # Limpiar directorio temporal de la sesión
            shutil.rmtree(session_dir)
            
            # Limpiar archivos de trabajo DESPUÉS de todo el proceso
            try:
                if os.path.exists(video_file):
                    os.remove(video_file)
                    print("Archivo sample-video.mp4 eliminado")
                if os.path.exists(json_file):
                    os.remove(json_file)
                    print("Archivo sample-video.json eliminado")
            except Exception as cleanup_error:
                print(f"Advertencia: Error al limpiar archivos: {cleanup_error}")
            
            response = {
                "success": True,
                "session_id": session_id,
                "video_path": VIDEO_PATH,
                "video_duration": round(video_duration, 2),
                "clip": clip_info,
                "message": "Clip generado en formato 9:16 y procesado exitosamente"
            }
        else:
            return jsonify({"error": "No se pudo generar el clip"}), 500
        
        return jsonify(response)
    
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Error en el proceso de transcripción o renderizado: {str(e)}"}), 500
    except Exception as e:
        print(f"❌ Error interno del servidor: {str(e)}")
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500

@app.route('/list-clips', methods=['GET'])
def list_clips():
    """Lista todas las sesiones y clips generados"""
    try:
        sessions = []
        
        if os.path.exists(CLIPS_DIR):
            for session_id in os.listdir(CLIPS_DIR):
                session_path = os.path.join(CLIPS_DIR, session_id)
                if os.path.isdir(session_path):
                    clips = []
                    for filename in os.listdir(session_path):
                        if filename.endswith('.mp4'):
                            file_path = os.path.join(session_path, filename)
                            file_size = os.path.getsize(file_path)
                            clips.append({
                                "filename": filename,
                                "size_mb": round(file_size / (1024 * 1024), 2),
                                "download_url": f"/download-clip/{session_id}/{filename}"
                            })
                    
                    sessions.append({
                        "session_id": session_id,
                        "clips_count": len(clips),
                        "clips": clips
                    })
        
        return jsonify({
            "sessions": sessions,
            "total_sessions": len(sessions)
        })
    
    except Exception as e:
        return jsonify({"error": f"Error listando clips: {str(e)}"}), 500

@app.route('/download-clip/<session_id>/<filename>', methods=['GET'])
def download_clip(session_id, filename):
    """Descarga un clip específico"""
    try:
        file_path = os.path.join(CLIPS_DIR, session_id, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        return jsonify({"error": f"Error descargando archivo: {str(e)}"}), 500

@app.route('/clear-clips', methods=['DELETE'])
def clear_clips():
    """Elimina todos los clips generados"""
    try:
        if os.path.exists(CLIPS_DIR):
            shutil.rmtree(CLIPS_DIR)
            os.makedirs(CLIPS_DIR)
        
        return jsonify({"message": "Todos los clips han sido eliminados"})
    
    except Exception as e:
        return jsonify({"error": f"Error eliminando clips: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Verifica que FFmpeg esté disponible"""
    try:
        # Verificar FFmpeg
        ffmpeg_result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        ffmpeg_available = ffmpeg_result.returncode == 0
        
        # Verificar FFprobe
        ffprobe_result = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True)
        ffprobe_available = ffprobe_result.returncode == 0
        
        return jsonify({
            "server": "running",
            "ffmpeg_available": ffmpeg_available,
            "ffprobe_available": ffprobe_available,
            "clips_directory": CLIPS_DIR,
            "clips_directory_exists": os.path.exists(CLIPS_DIR)
        })
    
    except Exception as e:
        return jsonify({
            "server": "running",
            "ffmpeg_available": False,
            "ffprobe_available": False,
            "error": str(e)
        })

if __name__ == '__main__':
    print("🎬 Servidor de generación de clips iniciado")
    print("📋 Endpoints disponibles:")
    print("   GET  /              - Información del servidor")
    print("   POST /generate-clip  - Generar un clip aleatorio")
    print("   GET  /list-clips     - Listar clips generados")
    print("   GET  /download-clip/<session_id>/<filename> - Descargar clip")
    print("   DELETE /clear-clips  - Eliminar todos los clips")
    print("   GET  /health         - Estado del servidor y FFmpeg")
    print("   GET  /directories    - Listar directorios disponibles")
    print("   GET  /files/<dir>    - Listar archivos en directorio")
    print("   GET  /static/<dir>/<file> - Servir archivo estático")
    print("   GET  /out/<file>     - Servir archivo desde ./out")
    print("   GET  /public/<file>  - Servir archivo desde ./public")
    print("\n🔧 Asegúrate de tener FFmpeg instalado en tu sistema")
    print("💡 Ejemplos de uso:")
    print('   curl http://localhost:5000/directories')
    print('   curl http://localhost:5000/files/out')
    print('   curl http://localhost:5000/out/CaptionedVideo.mp4')
    app.run(debug=True, host='0.0.0.0', port=7930)
