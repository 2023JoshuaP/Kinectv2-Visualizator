# Guía de instalación y diagnóstico: Kinect v2 en Linux

Esta guía cubre dependencias, compilación y acceso USB para **Kinect v2 / Xbox One** (`045e:02c4`). Para ejecutar la aplicación y conocer sus controles, consulta el [README](README.md).

Ejecuta los comandos desde la **raíz de este repositorio**, en orden. Los bloques de instalación usan Bash; los comandos con `sudo` piden la contraseña en tu terminal. La aplicación y las bibliotecas se instalan localmente, sin privilegios de administrador.

## Índice

- [Preflight USB](#preflight-usb)
- [Instalación y compilación](#instalación-y-compilación)
- [Permisos USB persistentes](#permisos-usb-persistentes)
- [Validación de captura](#validación-de-captura)
- [Resolución de problemas](#resolución-de-problemas)
- [Comenzar a desarrollar](#comenzar-a-desarrollar)

## Preflight USB

Conecta el sensor directamente a un puerto USB 3 SuperSpeed:

```bash
lsusb -d 045e:02c4
lsusb -t
```

Debe aparecer `Microsoft Corp. Xbox NUI Sensor` con enlace a **5000M o más**. Si muestra `480M`, cambia el cable o puerto; no uses un concentrador USB 2. Los números de bus y dispositivo cambian al reconectar: no los fijes en scripts.

## Instalación y compilación

### 1. Instalar dependencias del sistema

Se requiere **Python 3.10, 3.11 o 3.12** (recomendado 3.12; MediaPipe y NumPy 1.x aún no tienen soporte completo en Python 3.13), además de compilador C++, CMake y bibliotecas para USB y JPEG:

**Ubuntu / Debian:**

```bash
sudo apt update
sudo apt install cmake g++ make pkg-config libusb-1.0-0-dev libturbojpeg0-dev libglfw3-dev git python3-dev python3-venv python3-pip
```
> [!NOTE]
> Si tu distribución viene por defecto con Python 3.13 (por ejemplo Ubuntu 24.10+), instala Python 3.12 explícitamente: `sudo apt install python3.12 python3.12-dev python3.12-venv`.

**Fedora:**

```bash
sudo dnf install cmake gcc-c++ make pkgconf-pkg-config libusb1-devel libjpeg-turbo-devel turbojpeg-devel glfw-devel git python3-devel python3-pip
```

**Arch Linux / Manjaro:**

```bash
sudo pacman -S cmake gcc make pkgconf libusb libjpeg-turbo glfw git python python-pip
```

---

### 2. Compilar libfreenect2

Desde la raíz del repositorio:

```bash
# Clonar y compilar libfreenect2 localmente (sin sudo)
git clone https://github.com/OpenKinect/libfreenect2.git libfreenect2
cmake -S libfreenect2 -B libfreenect2/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PWD/libfreenect2/install" -DENABLE_CUDA=OFF
cmake --build libfreenect2/build --parallel
cmake --install libfreenect2/build
```

---

### 3. Preparar el binding Python (`pylibfreenect2`)

Aplica los parches de compatibilidad para Python 3.12 y la API extendida de este proyecto:

```bash
git clone https://github.com/r9y9/pylibfreenect2.git pylibfreenect2
git -C pylibfreenect2 apply ../patches/pylibfreenect2-python312.patch
git -C pylibfreenect2 apply ../patches/pylibfreenect2-extra-api.patch
```

> [!IMPORTANT]
> **No repitas clones ni parches** si esos directorios ya existen.

---

### 4. Configurar el entorno Python

Elige una de las dos opciones según tus preferencias. `run.sh` detecta `.venv` de forma automática.

#### Opción A: Entorno virtual estándar (`venv`) [Recomendado]

No necesitas herramientas externas. Usa el módulo `venv` integrado de Python:

```bash
# 1. Crear el entorno virtual en .venv (usa python3.12 si tu python3 por defecto es 3.13)
python3 -m venv .venv
source .venv/bin/activate

# 2. Actualizar herramientas base e instalar dependencias del proyecto
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 3. Compilar e instalar pylibfreenect2 vinculando a la compilación local
env LIBFREENECT2_INSTALL_PREFIX="$PWD/libfreenect2/install" pip install --no-build-isolation --no-deps ./pylibfreenect2
```

*(Si utilizas `uv`, el proceso equivalente es: `uv venv --python 3.12 .venv && uv pip install -r requirements.txt && env LIBFREENECT2_INSTALL_PREFIX="$PWD/libfreenect2/install" uv pip install --no-build-isolation --no-deps ./pylibfreenect2`)*

#### Opción B: Con Micromamba / Conda

Si prefieres gestionar el entorno con [Micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html):

```bash
# Crear entorno desde environment.yml
micromamba create -y -f environment.yml

# Instalar pylibfreenect2 en el entorno
env LIBFREENECT2_INSTALL_PREFIX="$PWD/libfreenect2/install" micromamba run -n kinectv2-dev python -m pip install --no-build-isolation --no-deps ./pylibfreenect2
```

Si el entorno `kinectv2-dev` ya existía previamente, actualízalo con:

```bash
micromamba env update -n kinectv2-dev -f environment.yml
```

La configuración usa CPU y, cuando está disponible, OpenGL. CUDA requiere un toolkit compatible con tu compilador y no es necesario para comenzar. Los parches adaptan el binding antiguo a Python 3.12/Cython 3 y exponen funciones C++ adicionales.

## Permisos USB persistentes

Que el sensor aparezca en `lsusb` no garantiza que tu usuario pueda abrirlo. Instala la regla oficial una sola vez:

```bash
sudo install -m 644 libfreenect2/platform/linux/udev/90-kinect2.rules /etc/udev/rules.d/90-kinect2.rules
sudo udevadm control --reload-rules
```

**Desconecta y vuelve a conectar físicamente el USB del Kinect** para aplicar la regla. Esta mantiene el acceso en las siguientes conexiones. No ejecutes la aplicación con `sudo` ni cambies manualmente los permisos de un número de bus/dispositivo.

## Validación de captura

Cierra la aplicación antes de probar `Protonect`: solo un programa puede usar el sensor a la vez.

```bash
env LD_LIBRARY_PATH="$PWD/libfreenect2/install/lib:$PWD/.local-deps/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" timeout --signal=INT --kill-after=5s 30s libfreenect2/build/bin/Protonect
```

Una captura sana abre el dispositivo y muestra color, infrarrojo y profundidad. Los registros deben indicar `TurboJpegRgbPacketProcessor` para RGB y el procesador de profundidad seleccionado. El código `124` es esperado si la prueba termina por el límite de tiempo.

`Protonect` se ejecuta desde el directorio de compilación; `cmake --install` no lo instala. Si falla, consulta el diagnóstico siguiente; si funciona, continúa con [Ejecutar](README.md#ejecutar).

## Resolución de problemas

| Problema | Qué revisar |
| --- | --- |
| El Kinect no aparece o muestra `480M` | Alimentación, cable y conexión directa USB 3; repite el [preflight USB](#preflight-usb). |
| CMake no encuentra `libusb` o `turbojpeg.h` | Instala los paquetes de desarrollo de [dependencias](#instalar-dependencias) y vuelve a configurar CMake. |
| `LIBUSB_ERROR_ACCESS` / `Access denied` | Aplica los [permisos USB](#permisos-usb-persistentes) y reconecta físicamente el sensor. |
| `LIBUSB_ERROR_BUSY` | Cierra otras capturas; si persiste en `IrInterfaceId`, consulta el procedimiento de abajo. |
| Error al cargar `libfreenect2.so` | Usa `sh run.sh`, que configura las rutas de bibliotecas locales. |

### `LIBUSB_ERROR_BUSY` en `IrInterfaceId`

Solo si aparece ese error y no hay otra captura abierta, `snd-usb-audio` puede haber tomado interfaces del Kinect. Ejecuta este **bloque completo en Bash**: detecta un único sensor, desvincula temporalmente sus interfaces de audio y las restaura al salir. No afecta de forma permanente a los controladores.

```bash
(
mapfile -t KINECT_PATHS < <(
  for device in /sys/bus/usb/devices/*; do
    [ -r "$device/idVendor" ] && [ -r "$device/idProduct" ] || continue
    [ "$(tr -d '\n' < "$device/idVendor")" = "045e" ] || continue
    [ "$(tr -d '\n' < "$device/idProduct")" = "02c4" ] || continue
    basename "$device"
  done
)

if [ "${#KINECT_PATHS[@]}" -ne 1 ]; then
  printf 'Se esperaba exactamente una Kinect 045e:02c4; se encontraron: %s\n' "${#KINECT_PATHS[@]}" >&2
  exit 1
fi

KINECT_PATH="${KINECT_PATHS[0]}"
mapfile -t AUDIO_INTERFACES < <(
  for interface in /sys/bus/usb/devices/"${KINECT_PATH}":1.*; do
    [ -e "$interface" ] || continue
    driver="$(readlink -f "$interface/driver" 2>/dev/null || true)"
    [ "$(basename "$driver")" = "snd-usb-audio" ] && basename "$interface"
  done
)

printf 'Ruta USB detectada: %s\n' "$KINECT_PATH"
printf 'Interfaces snd-usb-audio: %s\n' "${AUDIO_INTERFACES[*]:-ninguna}"
[ "${#AUDIO_INTERFACES[@]}" -gt 0 ] || { printf 'No hay interfaces de audio para desvincular.\n' >&2; exit 1; }

sudo -v || exit 1
restore_audio() {
  for interface in "${AUDIO_INTERFACES[@]}"; do
    printf '%s' "$interface" | sudo tee /sys/bus/usb/drivers/snd-usb-audio/bind >/dev/null
  done
}
trap restore_audio EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for interface in "${AUDIO_INTERFACES[@]}"; do
  printf '%s' "$interface" | sudo tee /sys/bus/usb/drivers/snd-usb-audio/unbind >/dev/null || exit 1
done

env LD_LIBRARY_PATH="$PWD/libfreenect2/install/lib:$PWD/.local-deps/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" timeout --signal=INT --kill-after=5s 30s libfreenect2/build/bin/Protonect
)
```

### Otros errores USB o relacionados con U1

Tras confirmar SuperSpeed, recopila un diagnóstico acotado:

```bash
lspci -nnk
env LIBUSB_DEBUG=3 LD_LIBRARY_PATH="$PWD/libfreenect2/install/lib:$PWD/.local-deps/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" timeout --signal=INT --kill-after=5s 30s libfreenect2/build/bin/Protonect
```

Elimina datos sensibles antes de compartir los registros. No atribuyas el fallo a U1 u otro componente solo por un mensaje aislado.

## Comenzar a desarrollar

- **Python:** el ejemplo `pylibfreenect2/examples/multiframe_listener.py` usa el mismo binding que la interfaz, sin servidor intermedio. Copia los datos de `Frame.asarray()` antes de `listener.release(frames)` si vas a conservarlos.
- **Capturas:** abre los `.npz` con `numpy.load("archivo.npz")`. Incluyen arrays originales (`Color`/`Registered` en BGRA uint8; IR/profundidad en float32), metadatos y calibración. Los timestamps crudos usan unidades de 0,125 ms.
- **C++:** la instalación local deja encabezados en `libfreenect2/install/include`, bibliotecas en `libfreenect2/install/lib` y la configuración CMake en `libfreenect2/install/lib/cmake/freenect2`. Pasa este último directorio como `-Dfreenect2_DIR` al configurar un proyecto externo.
- **Gestos:** `GestureThread.results_ready` entrega gestos, puntuaciones, puntos 2D y coordenadas 3D relativas a la mano, no posiciones absolutas del Kinect. MediaPipe usa RGB; la profundidad solo complementa el resultado. El reconocedor ya incluye detección de manos: no ejecutes ambos modelos sobre la misma imagen.
- **API avanzada:** consulta `pylibfreenect2/pylibfreenect2/libfreenect2.pyx`. No cambies parámetros de fábrica sin calibración válida. El replay nativo de paquetes `.depth` está incompleto y no reproduce los `.npz` exportados.
