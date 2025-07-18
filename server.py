from flask import Flask, send_from_directory
import subprocess
import requests
import os
import random
from pathlib import Path
import time
import threading
import shutil

app = Flask(__name__)

VIDEO_URL = "https://portfoliotavm.com/n8n/milei/video.mp4"
ROUTE_CLIP = "./clip/"
WHISPER_JSON = "./public/"

def delete_files_after_delay(file_base_name, delay_minutes=5):
    """
    Elimina archivos con el nombre base especificado después de un tiempo determinado
    """
    def delete_files():
        try:
            time.sleep(delay_minutes * 60)  # Convertir minutos a segundos
            
            # Archivos a eliminar
            mp4_file = os.path.join(WHISPER_JSON, f"{file_base_name}.mp4")
            json_file = os.path.join(WHISPER_JSON, f"{file_base_name}.json")
            out_dir = "./out/"
            
            files_deleted = []
            
            # Eliminar archivo MP4
            if os.path.exists(mp4_file):
                os.remove(mp4_file)
                files_deleted.append(f"{file_base_name}.mp4")
                print(f"Archivo eliminado: {mp4_file}")
            
            # Eliminar archivo JSON
            if os.path.exists(json_file):
                os.remove(json_file)
                files_deleted.append(f"{file_base_name}.json")
                print(f"Archivo eliminado: {json_file}")

            # Eliminar la carpeta ./out/ si existe
            """if os.path.exists(out_dir) and os.path.isdir(out_dir):
                try:
                    # Elimina todos los archivos dentro de la carpeta ./out/
                    for filename in os.listdir(out_dir):
                        file_path = os.path.join(out_dir, filename)
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    # Elimina la carpeta ./out/
                    os.rmdir(out_dir)
                    print(f"Carpeta eliminada: {out_dir}")
                    files_deleted.append("out/")
                except Exception as e:
                    print(f"Error eliminando carpeta {out_dir}: {e}") """
            
            if files_deleted:
                print(f"Limpieza automática completada después de {delay_minutes} minutos. Archivos eliminados: {', '.join(files_deleted)}")
            else:
                print(f"No se encontraron archivos para eliminar: {file_base_name}")
                
        except Exception as e:
            print(f"Error durante la limpieza automática: {e}")
    
    # Ejecutar en un hilo separado para no bloquear la aplicación
    cleanup_thread = threading.Thread(target=delete_files, daemon=True)
    cleanup_thread.start()
    print(f"Programada eliminación automática de archivos '{file_base_name}' en {delay_minutes} minutos")

def download_video(url, destination_path):
    try:
        print(f"Descargando video desde: {url}")
        
        # Realizar la petición con streaming para archivos grandes
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Lanza excepción si hay error HTTP
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        # Escribir el archivo en chunks para manejar archivos grandes
        with open(destination_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        
        print(f"Video descargado exitosamente: {destination_path}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar: {e}")
        return False

def get_video_duration(video_path):
    """
    Obtiene la duración del video en segundos usando ffprobe
    """
    try:
        result = subprocess.run([
            'ffprobe', 
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            print(f"Duración del video: {duration} segundos")
            return duration
        else:
            print(f"Error obteniendo duración: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_random_clip(input_video, output_clip, min_duration=30, max_duration=60):
    """
    Genera un clip aleatorio del video usando FFmpeg
    """
    try:
        # Obtener duración del video original
        total_duration = get_video_duration(input_video)
        if not total_duration:
            return False
        
        # Generar duración aleatoria del clip
        clip_duration = random.randint(min_duration, max_duration)
        
        # Calcular tiempo de inicio aleatorio
        # Asegurar que el clip no se salga del video
        max_start_time = total_duration - clip_duration
        if max_start_time <= 0:
            print(f"El video es muy corto. Duración: {total_duration}s, clip requerido: {clip_duration}s")
            # Si el video es más corto que el clip mínimo, usar todo el video
            start_time = 0
            clip_duration = min(total_duration, max_duration)
        else:
            start_time = random.uniform(0, max_start_time)
        
        print(f"Generando clip: inicio={start_time:.2f}s, duración={clip_duration}s")
        
        # Crear directorio de salida si no existe
        os.makedirs(os.path.dirname(output_clip), exist_ok=True)
        
        # Comando FFmpeg para extraer el clip
        command = [
            'ffmpeg',
            '-i', input_video,              # archivo de entrada
            '-ss', str(start_time),         # tiempo de inicio
            '-t', str(clip_duration),       # duración del clip
            '-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0',  # filtro de crop 9:16 centrado
            '-c:v', 'libx264',              # codec de video
            '-c:a', 'aac',                  # codec de audio
            '-preset', 'fast',              # preset de codificación
            '-y',                           # sobrescribir archivo si existe
            output_clip                     # archivo de salida
        ]
        
        # Ejecutar comando
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Clip generado exitosamente: {output_clip}")
            return True
        else:
            print(f"Error generando clip: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False

@app.route('/generate-clip', methods=['POST'])
def generate_clip():
        video_file = "./video.mp4"
        
        # Primero descargar el video si no existe
        if not os.path.exists(video_file):
            print("Video no encontrado, descargando...")
            if not download_video(VIDEO_URL, video_file):
                return {
                    "status": "error",
                    "message": "Error al descargar el video"
                }
        
        clip_filename = f"sample-video.mp4"
        clip_path = os.path.join(ROUTE_CLIP, clip_filename)
        
        # Generar clip aleatorio
        if generate_random_clip(video_file, clip_path):
            print("generando subtitulos")
            # Mover el clip al directorio public con la ruta completa
            public_clip_path = os.path.join(WHISPER_JSON, clip_filename)
            os.rename(clip_path, public_clip_path)
            print(public_clip_path)
            # Generar transcripción (usando la ruta correcta)
            generate_transcription = subprocess.run([
                'node', './sub.mjs', public_clip_path
            ], capture_output=True, text=True)
            print("Transcripción:", generate_transcription.stdout)
            if generate_transcription.stderr:
                print("Error transcripción:", generate_transcription.stderr)

            # Renderizar con Remotion
            remotionClip = subprocess.run([
                'npm', 'run', "render"
            ], capture_output=True, text=True)
            print("Remotion:", remotionClip.stdout)
            if remotionClip.stderr:
                print("Error Remotion:", remotionClip.stderr)
            
            # Programar eliminación automática de archivos después de 5 minutos
            delete_files_after_delay("sample-video", 5)
                
            return {
                "status": "success",
                "message": "Clip generado exitosamente",
                "clip_path": public_clip_path,
                "clip_filename": clip_filename
            }
        else:
            return {
                "status": "error",
                "message": "Error al generar el clip"
            }
            
    
@app.route('/out/<path:filename>', methods=['GET'])
def serve_captioned_video(filename):
    """
    Sirve el archivo CaptionedVideo.mp4 desde la carpeta ./out/
    """
    try:
        # Ruta de la carpeta donde está el archivo
        folder_path = './out'
        
        return send_from_directory(folder_path, filename)
    except Exception as e:
        return {"error": str(e)}, 500
@app.route('/metadata', methods=['GET'])
def metadata():
    return {
        "name": "PETTOVELLO EXPLOTÓ CON FEINMANN QUE NO PARABA DE CUESTIONARLA"
    }


@app.route('/')
def home():
    return {
        "status": "ready"
    }

if __name__ == '__main__':
    Path("clip").mkdir(exist_ok=True)
    Path("public").mkdir(exist_ok=True)
    app.run(host='0.0.0.0', port=7243)