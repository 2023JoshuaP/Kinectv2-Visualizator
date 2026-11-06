# Letras y aplicaciones por señas

La pestaña **Recognize signs** muestra la letra reconocida en grande y sobre la cámara. Los modelos base **LSP** y **ASL** son experimentales: reconocen 24 letras estáticas, no J, Z ni Ñ. **LSE** requiere muestras personales. No es un traductor de lengua de señas ni un reconocimiento validado; las letras parecidas, como M/N/T, pueden confundirse.

## Reconocer una letra

1. Pulsa **Start recognition**. Se activa color y detección de manos automáticamente.
2. Elige el perfil de alfabeto y muestra **una sola mano**, bien iluminada y completamente visible.
3. Consulta **Recognized letter · live result**: es el resultado de la cámara, no la letra seleccionada para configurar una acción. `—` indica que no hay una coincidencia clara.
4. Si una letra falla, selecciónala y pulsa **Record current pose** al menos tres veces, variando ligeramente la pose con la misma mano. Estas muestras tienen prioridad sobre el modelo base y se guardan localmente en `sign-templates.json`, en el directorio de datos de la aplicación Qt. Graba también la otra mano si quieres usarla.

## Abrir aplicaciones

Las acciones están **desactivadas al iniciar**. Primero comprueba que las letras se reconocen correctamente.

| Letra | Acción inicial |
| --- | --- |
| T | Terminal |
| N | Navegador predeterminado |
| C | Calculadora, si está instalada |
| E | Editor de texto, si está instalado |
| F | Archivos, si está instalado |
| V | VS Code o VSCodium, si está instalado |

Para cambiar una asignación, selecciona la **Letter** y la acción en **Action for this session**. Puedes asignar cualquier aplicación detectada a otra letra. **none** elimina la asignación.

**Choose another application…** permite elegir un ejecutable (por ejemplo, `/usr/bin/code` o un AppImage ejecutable), no un archivo `.desktop` ni una línea de comandos. Se asigna a la letra seleccionada y desactiva las acciones para que puedas comprobar el cambio. Los programas se lanzan sin evaluar comandos de shell y sin argumentos adicionales.

Activa **Enable actions**, mantén la letra durante **0,8 segundos** y retira la mano al menos **0,5 segundos** antes del siguiente comando. Hay un mínimo de dos segundos entre ejecuciones. Las asignaciones duran la sesión; las muestras personales sí persisten.

## Dispositivos inteligentes (Tuya / Smart Life)

Los enchufes y focos Tuya se controlan **en la red local** con `tinytuya`, sin pasar por la nube al enviar comandos. La configuración no depende de la máquina: no hay IP, interfaz ni ruta fijas en el código.

### Preparar una máquina nueva

1. Instala las dependencias: `micromamba env update -n kinectv2-dev -f environment.yml` (incluye `tinytuya`). Si usas `.venv`, instala `tinytuya>=1.13` en ese entorno.
2. Obtén el `id` y la `local key` de cada dispositivo, con [tuya-local-key](https://github.com/vineetchoudhary/tuya-local-key) o con `python -m tinytuya wizard` (incluido en `tinytuya`; requiere una cuenta de Tuya IoT Platform). Solo hace falta hacerlo una vez: la clave cambia únicamente si vuelves a emparejar el dispositivo en la app.
3. Copia `smart-devices.example.json` como `smart-devices.json`, en la raíz del repositorio, y rellena `id` y `key`. Deja `"ip": "auto"`. También se acepta el `devices.json` que genera `tinytuya wizard`; el tipo se deduce de su `category`. Para usar otra ruta, define `KINECT_SMART_DEVICES=/ruta/archivo.json`.
4. Ejecuta `sh run.sh` y pulsa **Find devices on network** en el panel **Smart devices**.

`smart-devices.json` está en `.gitignore`: **no lo subas**, porque las claves permiten controlar los dispositivos. Copia el archivo de forma privada a cada máquina que vaya a usarlos.

### Cómo encuentra las IP (sin nmap)

1. Escucha durante unos 8 s los anuncios UDP que los dispositivos Tuya envían por sí solos (puertos 6666, 6667 y 7000).
2. Si alguno no aparece, por ejemplo porque el cortafuegos bloquea UDP entrante, prueba el puerto TCP 6668 en la subred de la interfaz con salida a Internet, detectada automáticamente. Ignora Docker, libvirt y VPN, y limita la búsqueda a una /22 como máximo. Una subred /23 tarda unos 20 s. Puedes fijar las subredes con `"scan_networks": ["192.168.1.0/24"]` en `smart-devices.json`.
3. Guarda en el archivo la IP y la versión encontradas. Si un comando falla porque la IP cambió, repite la búsqueda (como mucho una vez cada 30 s) y reintenta una sola vez.

El PC y los dispositivos deben estar en la misma red local. Para que la detección UDP funcione desde el primer intento, abre esos puertos:

```bash
# Fedora (firewalld)
sudo firewall-cmd --permanent --add-port=6666-6667/udp --add-port=7000/udp && sudo firewall-cmd --reload
# Ubuntu (ufw, solo si está activo)
sudo ufw allow 6666:6667/udp && sudo ufw allow 7000/udp
```

Una **reserva DHCP** en el router evita que la IP cambie, pero no es obligatoria.

### Letras y acciones

`bindings` asigna letras: `"L": "toggle"`. Acciones: `toggle`, `on` y `off` en enchufes y focos; además `brighter`, `dimmer`, `next colour` y `white` en focos. Todas aparecen también en **Action for this session**.

| Letra (ejemplo) | Acción |
| --- | --- |
| P | Enchufe: alternar |
| L | Foco: alternar |
| B / D | Foco: más / menos brillo |
| R | Foco: siguiente color |

Los comandos se ejecutan en un hilo aparte, con un tiempo de espera de 2 s por conexión; el resultado aparece en el panel **Smart devices**. Si no existe `smart-devices.json` o los dispositivos no están en la red, la aplicación funciona igual y muestra el error en ese panel. Algunos dispositivos solo aceptan una conexión local a la vez: cierra la app Smart Life si no responden.

## Profundidad e integración

El filtro opcional **Require wrist distance 0.5–2.5 m**, en las herramientas avanzadas, requiere ambos flujos y **Extended registration**. Si no hay profundidad válida, rechaza la acción. La distancia a la muñeca es aproximada, no geometría precisa de los dedos.

`ActionRegistry` en `sign_commands.py` separa las acciones del reconocimiento. Los adaptadores de red deben usar un worker con tiempos de espera para no bloquear la interfaz. La inferencia de manos procesa el frame más reciente en un hilo independiente.
